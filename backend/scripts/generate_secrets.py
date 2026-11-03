#!/usr/bin/env python3
"""
Mus Luxury (LUXE) — Cryptographic Secret Generator (Stdlib `secrets`).
Generates fresh, high-entropy values for .env configuration.
"""
import secrets
import string


def generate_all_secrets() -> dict:
    alphabet = string.ascii_letters + string.digits
    pg_pass = "".join(secrets.choice(alphabet) for _ in range(36))
    return {
        "SECRET_KEY": secrets.token_hex(64),
        "CMS_HMAC_SIGNING_SECRET": secrets.token_hex(64),
        "POSTGRES_PASSWORD": pg_pass,
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN": secrets.token_hex(32),
        "BACKUP_ENCRYPTION_KEY": secrets.token_hex(32),
    }


if __name__ == "__main__":
    for k, v in generate_all_secrets().items():
        print(f"{k}={v}")
