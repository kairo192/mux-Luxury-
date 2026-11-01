import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, Request, status

SECRET_KEY = os.getenv("SECRET_KEY", "luxe_dev_secret_key_change_in_prod_998877665544332211")
TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")) * 60

# Revoked token blacklist (for explicit logout)
REVOKED_TOKENS: Set[str] = set()

# Nonce cache with timestamps to prevent Replay Attacks (OWASP Anti-Replay)
SEEN_NONCES: Dict[str, float] = {}

# Sliding-window rate limiter per IP + route bucket (Brute-Force & DoS protection)
RATE_LIMIT_BUCKETS: Dict[str, list] = {}

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with 310,000 OWASP-recommended iterations
    and a cryptographically secure 128-bit random salt.
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
        "jti": secrets.token_hex(16),
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

# ============================================================================
# CRYPTOGRAPHIC REQUEST SIGNING & REPLAY ATTACK DEFENSE (Section 8)
# Protects against Man-in-the-Middle tampering and Replay Attacks
# ============================================================================

def sign_api_request(method: str, path: str, body_bytes: bytes, secret: str = SECRET_KEY) -> Tuple[str, str, str]:
    """
    Generates HMAC-SHA256 signature, timestamp, and unique nonce for client-side API requests.
    """
    ts = str(int(time.time()))
    nonce = secrets.token_hex(12)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    msg = f"{method.upper()}|{path}|{ts}|{nonce}|{body_hash}"
    sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig, ts, nonce

def verify_signed_request(
    method: str,
    path: str,
    body_bytes: bytes,
    signature: Optional[str],
    timestamp_str: Optional[str],
    nonce: Optional[str],
    max_skew_seconds: int = 300,
    secret: str = SECRET_KEY
) -> None:
    """
    Cryptographic verification:
    1. Validates timestamp freshness (prevents delayed packets, max 300s window).
    2. Validates nonce uniqueness (strictly blocks Replay Attacks).
    3. Validates HMAC-SHA256 signature over method, path, timestamp, nonce, and body hash.
    """
    now = time.time()
    # Purge expired nonces older than 600 seconds
    stale_keys = [k for k, t in SEEN_NONCES.items() if now - t > 600]
    for k in stale_keys:
        SEEN_NONCES.pop(k, None)

    if not signature or not timestamp_str or not nonce:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing cryptographic headers (X-Luxe-Signature, X-Luxe-Timestamp, X-Luxe-Nonce)")

    try:
        ts = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format")

    if abs(now - ts) > max_skew_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cryptographic timestamp expired or clock skew too high ({abs(now - ts):.1f}s > {max_skew_seconds}s)"
        )

    if nonce in SEEN_NONCES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Replay Attack Detected: Nonce '{nonce}' has already been processed"
        )
    SEEN_NONCES[nonce] = now

    body_hash = hashlib.sha256(body_bytes).hexdigest()
    msg = f"{method.upper()}|{path}|{timestamp_str}|{nonce}|{body_hash}"
    expected_sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature mismatch: Request payload or headers were tampered with in transit"
        )

def check_rate_limit(key: str, max_requests: int, window_seconds: int = 60) -> None:
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < window_seconds]
    if len(bucket) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Progressive security backoff triggered. Please wait before retrying."
        )
    bucket.append(now)

def reset_rate_limits() -> None:
    RATE_LIMIT_BUCKETS.clear()
    SEEN_NONCES.clear()

ALLOWED_MIME_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

def validate_uploaded_image(filename: str, content_type: str, data: bytes, max_bytes: int = 5 * 1024 * 1024) -> None:
    # 1. Prevent Path Traversal (e.g. ../../../etc/passwd or exploit.php)
    basename = os.path.basename(filename)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Path traversal characters detected in upload filename")
    if not re.match(r"^[a-zA-Z0-9_.\-]+\.(jpg|jpeg|png|webp)$", basename, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Filename contains dangerous characters or non-image extension")

    # 2. Prevent Buffer Overflow / DoS via huge payload
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds maximum allowed size of 5 MB")

    # 3. Magic-Byte Binary Header Inspection (prevents PHP/JS script execution disguised as JPEG/PNG)
    if content_type not in ALLOWED_MIME_SIGNATURES:
        raise HTTPException(status_code=400, detail="Unsupported image format. Allowed: JPEG, PNG, WEBP")
    sigs = ALLOWED_MIME_SIGNATURES[content_type]
    if not any(data.startswith(sig) for sig in sigs):
        raise HTTPException(status_code=400, detail="Binary signature does not match declared image MIME type")

    # 4. Check for embedded script injections (Polyglot / WebShell protection)
    lower_snippet = data[:4096].lower()
    dangerous_signatures = [b"<?php", b"<script", b"eval(", b"base64_decode(", b"system(", b"passthru("]
    if any(dsig in lower_snippet for dsig in dangerous_signatures):
        raise HTTPException(status_code=400, detail="Malicious script signature detected inside image payload")
