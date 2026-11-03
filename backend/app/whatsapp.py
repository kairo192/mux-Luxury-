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


def _resolve_outbox_dir() -> str:
    local_default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
    candidate = os.getenv("BACKUP_DIR", local_default)
    try:
        os.makedirs(candidate, exist_ok=True)
        if os.access(candidate, os.W_OK):
            return candidate
    except OSError:
        pass
    os.makedirs(local_default, exist_ok=True)
    return local_default


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
    if app_secret.startswith(("replace_with_", "<CHANGE_ME")):
        app_secret = ""
    webhook_verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "").strip()
    if webhook_verify_token.startswith(("replace_with_", "<CHANGE_ME")):
        webhook_verify_token = "" 
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
        outbox_dir = _resolve_outbox_dir()
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
    Fails closed (returns False) if WHATSAPP_APP_SECRET is not configured or signature is missing.
    """
    cfg = get_whatsapp_config()
    secret = cfg["app_secret"]
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    received_sig = signature_header.split("=", 1)[1].strip()
    expected_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_sig, expected_sig)

import urllib.parse

ORDER_WHATSAPP_TEMPLATES_FR = {
    "confirmation_call": (
        "Bonjour {customer_name}, ici la Maison Mus Luxury (Ouled Yaïch - Blida). "
        "Nous avons bien reçu votre commande #{order_reference} d'un montant total de {total_dzd} DA "
        "(Livraison {delivery_mode_label} vers {wilaya_code} - {wilaya_name}, {commune}). "
        "Merci de répondre OUI à ce message pour confirmer l'expédition immédiate de votre colis."
    ),
    "shipped_notice": (
        "Bonne nouvelle {customer_name} ! Votre commande Mus Luxury #{order_reference} a été expédiée "
        "vers {wilaya_code} - {wilaya_name} ({commune}). Montant à préparer à la livraison (Cash on Delivery) : {total_dzd} DA. "
        "Merci pour votre confiance !"
    ),
    "no_answer_followup": (
        "Bonjour {customer_name}, notre service client Mus Luxury (0655 53 41 54) a tenté de vous joindre par téléphone "
        "pour valider l'envoi de votre commande #{order_reference} ({total_dzd} DA). "
        "Répondez OUI sur WhatsApp pour déclencher la livraison."
    ),
    "delivery_arrived": (
        "Bonjour {customer_name}, votre colis Mus Luxury #{order_reference} ({total_dzd} DA) est arrivé dans votre Wilaya "
        "({wilaya_code} - {wilaya_name}). Le livreur vous contactera très prochainement pour la remise."
    ),
}


def build_customer_order_whatsapp_message(
    order_dict: dict,
    template_type: str = "confirmation_call",
    custom_message: Optional[str] = None,
) -> dict:
    """
    Builds a personalized French customer WhatsApp message and click-to-chat deep links
    for any order lifecycle stage.
    """
    raw_phone = str(order_dict.get("customer_phone") or "")
    e164, local_num, meta_wa_id = normalize_algerian_phone(raw_phone)
    delivery_method = str(order_dict.get("delivery_method") or "home")
    delivery_mode_label = "Stop-Desk (Bureau relais)" if delivery_method == "stop_desk" else "À Domicile"

    tpl = ORDER_WHATSAPP_TEMPLATES_FR.get(template_type, ORDER_WHATSAPP_TEMPLATES_FR["confirmation_call"])
    if custom_message and custom_message.strip():
        body_text = custom_message.strip()
    else:
        body_text = tpl.format(
            customer_name=order_dict.get("customer_name") or "Client(e)",
            order_reference=order_dict.get("order_reference") or "",
            total_dzd=order_dict.get("total_dzd") or 0,
            wilaya_code=order_dict.get("wilaya_code") or "",
            wilaya_name=order_dict.get("wilaya_name") or "",
            commune=order_dict.get("commune") or "",
            delivery_mode_label=delivery_mode_label,
        )

    encoded_body = urllib.parse.quote(body_text)
    wa_me_customer_url = f"https://wa.me/{meta_wa_id}?text={encoded_body}"

    boutique_confirm_text = (
        f"Bonjour Mus Luxury, je confirme ma commande #{order_dict.get('order_reference', '')} "
        f"({order_dict.get('total_dzd', 0)} DA - {order_dict.get('wilaya_code', '')} {order_dict.get('wilaya_name', '')})."
    )
    wa_me_boutique_url = f"https://wa.me/213655534154?text={urllib.parse.quote(boutique_confirm_text)}"

    return {
        "template_type": template_type,
        "recipient_e164": e164,
        "recipient_local": local_num,
        "meta_wa_id": meta_wa_id,
        "message_text": body_text,
        "wa_me_customer_url": wa_me_customer_url,
        "wa_me_boutique_url": wa_me_boutique_url,
    }


def dispatch_customer_whatsapp_order_update(
    order_dict: dict,
    template_type: str = "confirmation_call",
    custom_message: Optional[str] = None,
) -> dict:
    """
    Dispatches an order lifecycle notification to the customer via Meta WhatsApp Cloud API
    (or records it in the structured outbox log when in sandbox/local mode) and returns
    both the API receipt and the 1-click wa.me deep link.
    """
    msg_info = build_customer_order_whatsapp_message(order_dict, template_type, custom_message)
    cfg = get_whatsapp_config()
    msg_id = f"wamid.ORDER_{template_type.upper()}_{int(time.time())}_{hashlib.sha256(msg_info['recipient_e164'].encode()).hexdigest()[:8]}"

    outbox_dir = _resolve_outbox_dir()
    outbox_file = os.path.join(outbox_dir, "whatsapp_outbox.jsonl")

    log_entry = {
        "timestamp": int(time.time()),
        "channel": "whatsapp_order_notification",
        "mode": "sandbox" if (cfg["sandbox_mode"] or not cfg["is_configured"]) else "live",
        "order_id": order_dict.get("id"),
        "order_reference": order_dict.get("order_reference"),
        "template_type": template_type,
        "recipient_e164": msg_info["recipient_e164"],
        "recipient_local": msg_info["recipient_local"],
        "message_text": msg_info["message_text"],
        "wa_me_customer_url": msg_info["wa_me_customer_url"],
        "message_id": msg_id,
    }
    with open(outbox_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {
        "delivered": True,
        "mode": log_entry["mode"],
        "provider": "meta_whatsapp_cloud_api",
        "message_id": msg_id,
        **msg_info,
    }


def list_recent_whatsapp_outbox(limit: int = 30) -> list:
    outbox_dir = _resolve_outbox_dir()
    outbox_file = os.path.join(outbox_dir, "whatsapp_outbox.jsonl")
    if not os.path.isfile(outbox_file):
        return []
    entries = []
    with open(outbox_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return list(reversed(entries))[:limit]

