import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Dict, Optional, Set
from fastapi import HTTPException, Request, status

SECRET_KEY = os.getenv("SECRET_KEY", "luxe_dev_secret_key_change_in_prod_998877665544332211")
TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")) * 60

# Revoked token blacklist (for explicit logout)
REVOKED_TOKENS: Set[str] = set()

# Simple in-memory sliding-window rate limiter per IP + route bucket
RATE_LIMIT_BUCKETS: Dict[str, list] = {}

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hashes password using Argon2id if argon2-cffi is installed, or
    PBKDF2-HMAC-SHA256 with 310,000 OWASP-recommended iterations.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 310000)
    return f"pbkdf2_sha256$310000${salt}${dk.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations, salt, digest = stored_hash.split("$", 3)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False

def create_access_token(user_id: int, email: str, role: str, permissions: list) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "perms": permissions,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "jti": secrets.token_hex(12),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def decode_access_token(token: str) -> dict:
    if token in REVOKED_TOKENS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token has been revoked")
    try:
        raw, sig = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token")

def revoke_token(token: str) -> None:
    REVOKED_TOKENS.add(token)

def check_rate_limit(key: str, max_requests: int, window_seconds: int = 60) -> None:
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < window_seconds]
    if len(bucket) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again shortly."
        )
    bucket.append(now)

def reset_rate_limits() -> None:
    RATE_LIMIT_BUCKETS.clear()

ALLOWED_MIME_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

def validate_uploaded_image(filename: str, content_type: str, data: bytes, max_bytes: int = 5 * 1024 * 1024) -> None:
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds maximum allowed size of 5 MB")
    if content_type not in ALLOWED_MIME_SIGNATURES:
        raise HTTPException(status_code=400, detail="Unsupported image format. Allowed: JPEG, PNG, WEBP")
    sigs = ALLOWED_MIME_SIGNATURES[content_type]
    if not any(data.startswith(sig) for sig in sigs):
        raise HTTPException(status_code=400, detail="File binary signature does not match declared image MIME type")
