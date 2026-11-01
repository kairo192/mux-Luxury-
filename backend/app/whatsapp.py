import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

from . import config  # Ensures .env is loaded


def normalize_algerian_phone(raw_phone: str) -> Tuple[str, str, str]:
    """
    Normalizes any Algerian mobile or landline number into three canonical formats:
    1. e164: '+213655534154'
    2. local: '0655534154'
    3. meta_wa_id: '213655534154' (Meta WhatsApp Cloud API recipient format)

    Supports inputs like:
      - '0655 53 41 54'
      - '0655-53-41-54'
      - '+213 655 53 41 54'
      - '00213655534154'
      - '213655534154'
    """
    cleaned = re.sub(r"[\s\-\.\(\)]", "", (raw_phone or "").strip())
    if cleaned.startswith("00213"):
        national = cleaned[5:]
    elif cleaned.startswith("+213"):
        national = cleaned[4:]
    elif cleaned.startswith("213") and len(cleaned) == 12:
        national = cleaned[3:]
    elif cleaned.startswith("0") and len(cleaned) == 10:
        national = cleaned[1:]
    else:
        # Fallback if non-standard length
        digits = re.sub(r"\D", "", cleaned)
        return cleaned, cleaned, digits

    if national.startswith("0"):
        national = national[1:]

    e164 = f"+213{national}"
    local = f"0{national}"
    meta_wa_id = f"213{national}"
    return e164, local, meta_wa_id


def get_whatsapp_config() -> dict:
    """
    Reads Meta WhatsApp Business Cloud API configuration from environment variables.
    Supports both WHATSAPP_CLOUD_API_TOKEN and WHATSAPP_ACCESS_TOKEN.
    """
    token = os.getenv("WHATSAPP_CLOUD_API_TOKEN", "").strip()
    if not token and "WHATSAPP_CLOUD_API_TOKEN" not in os.environ:
        # Only fall back to WHATSAPP_ACCESS_TOKEN if explicitly set by caller
        token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    business_account_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip()
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    webhook_verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "mus_luxury_wa_webhook_verify_2026_secret").strip()
    api_version = os.getenv("WHATSAPP_API_VERSION", "v20.0").strip() or "v20.0"
    template_name = os.getenv("WHATSAPP_TEMPLATE_NAME", "luxe_admin_password_reset").strip()
    template_lang = os.getenv("WHATSAPP_TEMPLATE_LANG", "fr").strip() or "fr"
    sandbox_raw = os.getenv("WHATSAPP_SANDBOX_MODE", "").strip().lower()
    test_capture = os.getenv("WHATSAPP_TEST_CAPTURE", "").strip() == "1"

    # If token is a placeholder (`EAATest_...` or `test_...`) and WHATSAPP_SANDBOX_MODE is not explicitly false,
    # operate in sandbox mode unless the caller explicitly cleared WHATSAPP_CLOUD_API_TOKEN to test 503 behavior.
    is_placeholder_token = token.startswith("EAATest_") or token.startswith("test_")
    sandbox_mode = sandbox_raw in ("1", "true", "yes") or (bool(token) and is_placeholder_token)

    is_configured = bool(token and phone_number_id)

    return {
        "token": token,
        "phone_number_id": phone_number_id,
        "business_account_id": business_account_id,
        "app_secret": app_secret,
        "webhook_verify_token": webhook_verify_token,
        "api_version": api_version,
        "template_name": template_name,
        "template_lang": template_lang,
        "sandbox_mode": sandbox_mode,
        "test_capture": test_capture,
        "is_configured": is_configured,
    }


def dispatch_whatsapp_recovery_otp(to_phone: str, otp_code: str, expires_minutes: int = 5) -> dict:
    """
    Dispatches a single-use 6-digit recovery OTP via Meta WhatsApp Business Cloud API.
    - When live credentials are provided and `sandbox_mode` is False, performs an HTTPS POST
      to `https://graph.facebook.com/{api_version}/{phone_number_id}/messages`.
    - When `sandbox_mode` is True or `test_capture` is True (local/staging/CI), records the
      structured outbox event in `backend/backups/whatsapp_outbox.jsonl` (without logging raw OTP
      unless `WHATSAPP_TEST_CAPTURE=1`) and returns simulated Meta receipt metadata.
    """
    cfg = get_whatsapp_config()
    if not cfg["is_configured"]:
        raise RuntimeError(
            "Official WhatsApp Business Cloud API is not configured on this server "
            "(missing WHATSAPP_CLOUD_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID)."
        )

    e164, local_num, meta_wa_id = normalize_algerian_phone(to_phone)
    endpoint = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"

    # Official Meta WhatsApp Cloud API payload
    message_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": meta_wa_id,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": (
                f"[Mus Luxury CMS] Votre code de récupération administrateur à usage unique est : "
                f"{otp_code}. Valable {expires_minutes} minutes. Ne le partagez jamais."
            ),
        },
    }

    if cfg["sandbox_mode"] or cfg["test_capture"]:
        msg_id = f"wamid.LUXE_SANDBOX_{int(time.time())}_{hashlib.sha256(e164.encode()).hexdigest()[:8]}"
        outbox_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
        os.makedirs(outbox_dir, exist_ok=True)
        outbox_file = os.path.join(outbox_dir, "whatsapp_outbox.jsonl")
        log_entry = {
            "timestamp": int(time.time()),
            "mode": "sandbox",
            "endpoint": endpoint,
            "recipient_e164": e164,
            "recipient_local": local_num,
            "meta_wa_id": meta_wa_id,
            "message_id": msg_id,
            "otp_sha256": hashlib.sha256(otp_code.encode("utf-8")).hexdigest(),
        }
        with open(outbox_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        return {
            "delivered": True,
            "mode": "sandbox",
            "provider": "meta_whatsapp_cloud_api",
            "api_version": cfg["api_version"],
            "recipient_e164": e164,
            "message_id": msg_id,
        }

    # Live HTTPS call to Meta Graph API
    body_bytes = json.dumps(message_payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {cfg['token']}",
            "Content-Type": "application/json",
            "User-Agent": "MusLuxury-CMS-Backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            messages = resp_data.get("messages") or [{}]
            msg_id = messages[0].get("id", f"wamid.LIVE_{int(time.time())}")
            return {
                "delivered": True,
                "mode": "live",
                "provider": "meta_whatsapp_cloud_api",
                "api_version": cfg["api_version"],
                "recipient_e164": e164,
                "message_id": msg_id,
            }
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WhatsApp Cloud API HTTP {exc.code}: {err_body[:240]}") from exc
    except Exception as exc:
        raise RuntimeError(f"WhatsApp Cloud API connection error: {str(exc)}") from exc


def verify_whatsapp_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verifies X-Hub-Signature-256 sent by Meta Webhooks using WHATSAPP_APP_SECRET.
    """
    cfg = get_whatsapp_config()
    secret = cfg["app_secret"]
    if not secret or secret.startswith("replace_with_"):
        # If app secret is not enforced yet, require explicit header format check
        return bool(signature_header and signature_header.startswith("sha256="))
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received_sig = signature_header.split("=", 1)[1].strip()
    expected_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_sig, expected_sig)
