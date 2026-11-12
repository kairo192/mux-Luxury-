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
    The Meta WhatsApp Cloud API webhook settings (delivery receipts). Messages
    to customers need no key: staff send prepared wa.me messages.
    Hardening: placeholder values count as empty; in production a value from
    the published-secret denylist is refused (the webhook then answers 503).
    """
    from .security import COMPROMISED_SECRET_SHA256_DENYLIST

    def _clean(raw: str) -> str:
        value = (raw or "").strip()
        if value.lower().startswith(("replace", "change", "<change", "<replace")):
            return ""
        if config.is_production() and hashlib.sha256(value.encode("utf-8")).hexdigest() in COMPROMISED_SECRET_SHA256_DENYLIST:
            return ""
        return value

    return {
        "app_secret": _clean(os.getenv("WHATSAPP_APP_SECRET", "")),
        "webhook_verify_token": _clean(os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")),
    }


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
    # Nothing is sent from the server: no WhatsApp Business API call exists in
    # this system. The back office opens WhatsApp on the PC with the message
    # already written (wa.me link) and the staff member presses "Send". The
    # result therefore says "prepared", never "delivered".
    log_id = f"wa_{template_type}_{int(time.time())}_{hashlib.sha256(msg_info['recipient_e164'].encode()).hexdigest()[:8]}"

    outbox_dir = _resolve_outbox_dir()
    outbox_file = os.path.join(outbox_dir, "whatsapp_outbox.jsonl")

    log_entry = {
        "timestamp": int(time.time()),
        "channel": "whatsapp_order_notification",
        "mode": "manual_link",
        "status": "prepared",
        "order_id": order_dict.get("id"),
        "order_reference": order_dict.get("order_reference"),
        "template_type": template_type,
        "recipient_e164": msg_info["recipient_e164"],
        "recipient_local": msg_info["recipient_local"],
        "message_text": msg_info["message_text"],
        "wa_me_customer_url": msg_info["wa_me_customer_url"],
        "message_id": log_id,
    }
    with open(outbox_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {
        "delivered": False,
        "status": "prepared",
        "mode": "manual_link",
        "message_id": log_id,
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

