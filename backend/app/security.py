from . import config
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Dict, List, Optional, Set, Tuple
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, status

logger = logging.getLogger("luxe.security")

# C-3.3: SHA-256 digests of compromised/default secrets from audit handoff (never store raw strings)
COMPROMISED_SECRET_SHA256_DENYLIST: Set[str] = {
    "fe10bb548e201d48e861e4d157baeeb64dab05d299c71b007f4a8cafecd70daa",  # leaked .env.example SECRET_KEY
    "133c08ff8619883e3f0140e7a7a5ae602393290528db0a3c158ff209a9c5cc02",  # old dev default SECRET_KEY
    "6b9d81fa41d2d5d3608d6de07b41e1d05214482efdd6ed355a1fec802b9e4e9c",  # leaked/default webhook verify token
    "392e96df58c32fb8e877b4154892d0cc9b333201e206244128422f5242d22211",  # leaked HMAC secret
}

_EPHEMERAL_DEV_SECRET = secrets.token_hex(32)
_WARNED_EPHEMERAL = False


def is_secret_compromised_or_weak(raw_value: str, min_len: int = 32) -> bool:
    s = (raw_value or "").strip()
    if len(s) < min_len:
        return True
    lower = s.lower()
    if lower.startswith(("change", "replace", "<change", "<replace", "your_")):
        return True
    digest = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return digest in COMPROMISED_SECRET_SHA256_DENYLIST


def get_secret_key() -> str:
    """
    Resolves JWT SECRET_KEY.
    In production (config.is_production()), raises RuntimeError if SECRET_KEY is missing,
    shorter than 32 chars, starts with change/replace, or matches the SHA-256 denylist.
    In non-production, falls back to a per-process random 32-byte hex secret and logs a warning.
    """
    global _WARNED_EPHEMERAL
    raw = os.getenv("SECRET_KEY", "").strip()
    if is_secret_compromised_or_weak(raw, min_len=32):
        if config.is_production():
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: SECRET_KEY is missing, weak, or compromised. "
                "Generate a fresh secret with `python3 backend/scripts/generate_secrets.py`."
            )
        if not _WARNED_EPHEMERAL:
            logger.warning("Using ephemeral per-process SECRET_KEY in non-production environment (%s)", config.app_env())
            _WARNED_EPHEMERAL = True
        return _EPHEMERAL_DEV_SECRET
    return raw


def get_hmac_signing_secret() -> str:
    """
    C-3.6: Separate key for client API request signing (`sign_api_request` / `verify_signed_request`).
    Uses `CMS_HMAC_SIGNING_SECRET` when valid and distinct from JWT `SECRET_KEY`; otherwise derives
    `HMAC-SHA256(SECRET_KEY, b"luxe-request-signing-v1")` so the signing key never equals the JWT key.
    """
    raw_hmac = os.getenv("CMS_HMAC_SIGNING_SECRET", "").strip()
    jwt_secret = get_secret_key()
    if not is_secret_compromised_or_weak(raw_hmac, min_len=32) and raw_hmac != jwt_secret:
        return raw_hmac
    return hmac.new(jwt_secret.encode("utf-8"), b"luxe-request-signing-v1", hashlib.sha256).hexdigest()


# Fail fast at import if running in production with an invalid/compromised SECRET_KEY
if config.is_production():
    get_secret_key()

TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")) * 60

# M-1: Bounded token->exp blacklist (purges expired tokens first, evicts single oldest entry, never .clear()s)
# Single-worker note: In-memory cache is per-worker; password resets additionally persist `session_revoked_ns` in DB.
REVOKED_TOKENS: Dict[str, float] = {}
USER_SESSION_REVOKED_NS: Dict[int, int] = {}

# Nonce cache with timestamps to prevent Replay Attacks (OWASP Anti-Replay)
SEEN_NONCES: Dict[str, float] = {}

# Sliding-window rate limiter per IP + route bucket (Brute-Force & DoS protection)
RATE_LIMIT_BUCKETS: Dict[str, list] = {}

PBKDF2_ITERATIONS_DEFAULT = 600000  # M-12: OWASP 2023+ PBKDF2-HMAC-SHA256 recommendation (600,000 iterations)


def hash_password(password: str, salt: Optional[str] = None, iterations: int = PBKDF2_ITERATIONS_DEFAULT) -> str:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with 600,000 OWASP-recommended iterations
    and a cryptographically secure 128-bit random salt.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return f"pbkdf2_sha256${int(iterations)}${salt}${dk.hex()}"


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
        "iat_ns": time.time_ns(),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "jti": secrets.token_hex(16),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(get_secret_key().encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def decode_access_token(token: str) -> dict:
    now = time.time()
    exp_rev = REVOKED_TOKENS.get(token)
    if exp_rev is not None:
        if now < exp_rev:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session fermée. Reconnectez-vous.")
        REVOKED_TOKENS.pop(token, None)
    try:
        raw, sig = token.split(".", 1)
        expected_sig = hmac.new(get_secret_key().encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < int(now):
            raise ValueError("Token expired")
        uid = int(payload.get("sub") or 0)
        revoked_ns = USER_SESSION_REVOKED_NS.get(uid, 0)
        if revoked_ns and int(payload.get("iat_ns") or 0) < revoked_ns:
            raise ValueError("Token revoked by password reset")
        return payload
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée. Reconnectez-vous.")


def revoke_all_user_sessions(user_id: int, conn=None) -> int:
    now_ns = time.time_ns()
    uid = int(user_id)
    USER_SESSION_REVOKED_NS[uid] = now_ns
    if conn is not None:
        conn.cursor().execute(
            """INSERT INTO store_settings (setting_key, setting_value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP""",
            (f"session_revoked_ns:{uid}", str(now_ns)),
        )
    return now_ns


def _extract_token_exp(token: str) -> float:
    try:
        raw = token.split(".", 1)[0]
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
        exp = float(payload.get("exp") or 0)
        if exp > 0:
            return exp
    except Exception:
        pass
    return time.time() + TOKEN_TTL_SECONDS


def revoke_token(token: str) -> None:
    """
    M-1: Stores token->exp in REVOKED_TOKENS, purges expired tokens first, and evicts
    only the single oldest entry when full (never calls .clear()).
    """
    now = time.time()
    if len(REVOKED_TOKENS) >= MAX_REVOKED_TOKENS:
        expired = [k for k, exp_ts in REVOKED_TOKENS.items() if now >= exp_ts]
        for k in expired:
            REVOKED_TOKENS.pop(k, None)
        if len(REVOKED_TOKENS) >= MAX_REVOKED_TOKENS:
            oldest_k = min(REVOKED_TOKENS, key=REVOKED_TOKENS.get)
            REVOKED_TOKENS.pop(oldest_k, None)
    REVOKED_TOKENS[token] = _extract_token_exp(token)


# ============================================================================
# CRYPTOGRAPHIC REQUEST SIGNING & REPLAY ATTACK DEFENSE (Section 8)
# ============================================================================

def sign_api_request(method: str, path: str, body_bytes: bytes, secret: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Generates HMAC-SHA256 signature, timestamp, and unique nonce for client-side API requests.
    """
    signing_secret = secret or get_hmac_signing_secret()
    ts = str(int(time.time()))
    nonce = secrets.token_hex(12)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    msg = f"{method.upper()}|{path}|{ts}|{nonce}|{body_hash}"
    sig = hmac.new(signing_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig, ts, nonce


def verify_signed_request(
    method: str,
    path: str,
    body_bytes: bytes,
    signature: Optional[str],
    timestamp_str: Optional[str],
    nonce: Optional[str],
    max_skew_seconds: int = 300,
    secret: Optional[str] = None,
) -> None:
    """
    Cryptographic verification (C-3.6 & M-2):
    1. Validates timestamp freshness (max 300s window).
    2. Checks if nonce was already used.
    3. Validates HMAC-SHA256 signature FIRST using dedicated signing key.
    4. Records nonce in SEEN_NONCES ONLY AFTER signature verification succeeds.
    """
    signing_secret = secret or get_hmac_signing_secret()
    now = time.time()
    stale_keys = [k for k, t in SEEN_NONCES.items() if now - t > 600]
    for k in stale_keys:
        SEEN_NONCES.pop(k, None)

    if not signature or not timestamp_str or not nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing cryptographic headers (X-Luxe-Signature, X-Luxe-Timestamp, X-Luxe-Nonce)",
        )

    try:
        ts = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format")

    if abs(now - ts) > max_skew_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cryptographic timestamp expired or clock skew too high ({abs(now - ts):.1f}s > {max_skew_seconds}s)",
        )

    if nonce in SEEN_NONCES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Replay Attack Detected: Nonce '{nonce}' has already been processed",
        )

    body_hash = hashlib.sha256(body_bytes).hexdigest()
    msg = f"{method.upper()}|{path}|{timestamp_str}|{nonce}|{body_hash}"
    expected_sig = hmac.new(signing_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature mismatch: Request payload or headers were tampered with in transit",
        )

    if len(SEEN_NONCES) >= MAX_SEEN_NONCES:
        oldest_k = min(SEEN_NONCES, key=SEEN_NONCES.get)
        SEEN_NONCES.pop(oldest_k, None)
    SEEN_NONCES[nonce] = now


def check_rate_limit(key: str, max_requests: int, window_seconds: int = 60) -> None:
    now = time.time()
    if key not in RATE_LIMIT_BUCKETS and len(RATE_LIMIT_BUCKETS) >= MAX_RATE_LIMIT_KEYS:
        stale_k = next(iter(RATE_LIMIT_BUCKETS))
        RATE_LIMIT_BUCKETS.pop(stale_k, None)
    bucket = RATE_LIMIT_BUCKETS.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < window_seconds]
    if len(bucket) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Patientez un moment avant de réessayer.",
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
    # 1. Prevent Path Traversal & trailing newline bypass via re.fullmatch (M-7)
    if ".." in filename or "/" in filename or "\\" in filename or "\n" in filename or "\r" in filename:
        raise HTTPException(status_code=400, detail="Path traversal characters detected in upload filename")
    basename = os.path.basename(filename)
    if not re.fullmatch(r"^[a-zA-Z0-9_.\-]+\.(jpg|jpeg|png|webp)$", basename, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Nom de fichier non accepté (image JPEG, PNG ou WEBP attendue)")

    # 2. Prevent Buffer Overflow / DoS via huge payload
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Image trop lourde (5 Mo maximum)")

    # 3. Magic-Byte Binary Header & Extension-to-MIME Consistency Inspection
    if content_type not in ALLOWED_MIME_SIGNATURES:
        raise HTTPException(status_code=400, detail="Format d'image non accepté (JPEG, PNG ou WEBP)")
    ext_lower = os.path.splitext(basename)[1].lower()
    allowed_exts_for_mime = {
        "image/jpeg": (".jpg", ".jpeg"),
        "image/png": (".png",),
        "image/webp": (".webp",),
    }
    if ext_lower not in allowed_exts_for_mime.get(content_type, ()):
        raise HTTPException(status_code=400, detail="File extension does not match declared image MIME type")
    sigs = ALLOWED_MIME_SIGNATURES[content_type]
    if not any(data.startswith(sig) for sig in sigs):
        raise HTTPException(status_code=400, detail="Binary signature does not match declared image MIME type")
    if content_type == "image/webp" and (len(data) < 12 or data[8:12] != b"WEBP"):
        raise HTTPException(status_code=400, detail="Invalid WebP container header (missing WEBP signature)")

    # 4. Full-Payload Scan for Embedded Script Injections
    lower_payload = data.lower()
    dangerous_signatures = [b"<?php", b"<script", b"eval(", b"base64_decode(", b"system(", b"passthru("]
    if any(dsig in lower_payload for dsig in dangerous_signatures):
        raise HTTPException(status_code=400, detail="Malicious script signature detected inside image payload")


MAX_RATE_LIMIT_KEYS = 10000
MAX_SEEN_NONCES = 20000
MAX_REVOKED_TOKENS = 10000


def _is_trusted_proxy_peer(host: str) -> bool:
    if not host:
        return False
    h = host.strip().lower()
    if h in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True
    if h.startswith(("10.", "192.168.")):
        return True
    if h.startswith("172."):
        parts = h.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return True
    return False


def get_real_client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client and request.client.host else "127.0.0.1"
    if _is_trusted_proxy_peer(peer_ip):
        x_real_ip = request.headers.get("X-Real-IP", "").strip()
        if x_real_ip and len(x_real_ip) <= 64:
            return x_real_ip
        xff = request.headers.get("X-Forwarded-For", "").strip()
        if xff:
            first_hop = xff.split(",")[0].strip()
            if first_hop and len(first_hop) <= 64:
                return first_hop
    return peer_ip


BACKUP_MAGIC_HEADER = b"LUXEENC1"


def _derive_backup_fernet(salt: bytes) -> Fernet:
    raw_key = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
    if is_secret_compromised_or_weak(raw_key, min_len=16):
        raw_key = get_secret_key()
    dk = hashlib.pbkdf2_hmac("sha256", raw_key.encode("utf-8"), salt, 100000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(dk))


def encrypt_backup_bytes(plaintext_bytes: bytes) -> bytes:
    salt = secrets.token_bytes(16)
    f = _derive_backup_fernet(salt)
    token = f.encrypt(plaintext_bytes)
    return BACKUP_MAGIC_HEADER + salt + token


def decrypt_backup_bytes(stored_bytes: bytes) -> bytes:
    if stored_bytes.startswith(BACKUP_MAGIC_HEADER):
        salt = stored_bytes[8:24]
        token = stored_bytes[24:]
        f = _derive_backup_fernet(salt)
        return f.decrypt(token)
    return stored_bytes
