"""Incoming webhooks from delivery and messaging providers."""
from fastapi import APIRouter
import hmac
import json
from typing import Optional
from fastapi import HTTPException, Query, Request, Response, status
from ..database import db_session
from ..security import check_rate_limit, get_real_client_ip
from ..whatsapp import get_whatsapp_config, verify_whatsapp_webhook_signature
from ..deps import (
    log_audit,
)

router = APIRouter()



# ---------------------------------------------------------------------------
# WHATSAPP-BASED ADMIN PASSWORD RECOVERY — REMOVED (owner request)
# The four endpoints formerly here (`/admin/auth/recovery/status|request|
# verify|rotate-emergency-code`) are gone. Owner-side password reset is
# now a server-side CLI operation only:
#     python3 backend/scripts/emergency_reset_owner.py \
#         --email admin@mus-luxury.com --new-password '<new>'
# Run from the VPS over SSH as the deploy user. The WhatsApp module itself
# (customer order notifications + webhook) stays in place.
# ---------------------------------------------------------------------------

MAX_WEBHOOK_BODY_BYTES = 64 * 1024

MAX_WEBHOOK_STATUSES_PER_CALL = 50


@router.get("/api/v1/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Meta WhatsApp Cloud API Webhook Verification Endpoint (GET).
    C-3.4: Returns 503 when WHATSAPP_WEBHOOK_VERIFY_TOKEN is empty/unconfigured.
    """
    cfg = get_whatsapp_config()
    expected_token = cfg["webhook_verify_token"]
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WhatsApp webhook verify token is not configured")
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, expected_token):
        return Response(content=str(hub_challenge or ""), media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification token mismatch")


@router.post("/api/v1/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    """
    Meta WhatsApp Cloud API Webhook Receiver (POST) for message delivery & read receipts (H-4).
    - Enforces per-IP rate limiting.
    - Returns 503 if WHATSAPP_APP_SECRET is not configured.
    - Caps payload size at 64 KB and statuses logged per request at 50.
    - Always requires a valid HMAC-SHA256 X-Hub-Signature-256 header.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"wa_webhook:{client_ip}", max_requests=60, window_seconds=60)
    cfg = get_whatsapp_config()
    if not cfg["app_secret"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WhatsApp webhook app secret is not configured")
    # Read at most 64 KB: stop as soon as the body passes the limit instead of
    # buffering whatever size an unsigned sender chose.
    too_large = HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook payload exceeds 64 KB limit")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_WEBHOOK_BODY_BYTES:
        raise too_large
    chunks: list = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_WEBHOOK_BODY_BYTES:
            raise too_large
        chunks.append(chunk)
    raw_body = b"".join(chunks)
    sig_header = request.headers.get("X-Hub-Signature-256")
    if not verify_whatsapp_webhook_signature(raw_body, sig_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Hub-Signature-256 webhook signature")
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON webhook payload")

    statuses_logged = 0
    with db_session(commit=True) as conn:
        for entry in (payload.get("entry") or [])[:20]:
            for change in (entry.get("changes") or [])[:20]:
                val = change.get("value") or {}
                for st in (val.get("statuses") or [])[:MAX_WEBHOOK_STATUSES_PER_CALL]:
                    if statuses_logged >= MAX_WEBHOOK_STATUSES_PER_CALL:
                        break
                    statuses_logged += 1
                    log_audit(
                        conn,
                        None,
                        "whatsapp_webhook_status",
                        "whatsapp_message",
                        str(st.get("id", "unknown"))[:120],
                        {"status": str(st.get("status", ""))[:64], "recipient_id": str(st.get("recipient_id", ""))[:64]},
                    )
    return {"received": True, "statuses_logged": statuses_logged}
