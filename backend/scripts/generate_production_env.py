#!/usr/bin/env python3
"""
Mus Luxury — production `.env` generator.

Produces a complete `.env.production` file with cryptographically strong
values for every secret the backend + storefront + CMS need at runtime.
Third-party credentials the project cannot generate (Meta WhatsApp Cloud
API, Chargily, Yalidine, S3) are written as explicit `<FILL_IN>` tokens
so a scan will immediately show what still needs the owner's input.

Output path defaults to `scratch/production.env` (git-ignored). This is
intentional: we do NOT want production secrets on disk under `backend/`
where a careless `git add backend/` could stage them.

Usage:
    python3 backend/scripts/generate_production_env.py \\
        --domain mus-luxury.com \\
        --admin-email admin@mus-luxury.com \\
        --admin-whatsapp +213655534154 \\
        [--out scratch/production.env]

Nothing here is written to GitHub Actions or any remote store — the
operator must copy the resulting file to the VPS themselves, e.g.:

    scp scratch/production.env luxe@<vps>:/opt/luxe/shared/.env
    ssh luxe@<vps> 'chmod 0600 /opt/luxe/shared/.env'
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path


def _hex(n_bytes: int) -> str:
    return secrets.token_hex(n_bytes)


def _password(length: int = 36) -> str:
    # URL-safe password: no quoting headaches inside the .env file.
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _admin_password(length: int = 20) -> str:
    # Mixed-case + digits + 2 symbols; printable, memorable-ish for the first
    # owner login right before they change it in the UI.
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#&?"
    core = "".join(secrets.choice(alphabet) for _ in range(length - 2))
    return core + "".join(secrets.choice(symbols) for _ in range(2))


def render(
    *,
    domain: str,
    admin_email: str,
    admin_whatsapp: str,
    emergency_phone: str,
) -> str:
    """Assemble the full .env.production body."""
    api_domain = f"api.{domain}"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    secret_key = _hex(64)
    cms_hmac = _hex(64)
    backup_key = _hex(32)
    pg_password = _password(36)
    whatsapp_verify = _hex(32)
    admin_pw = _admin_password(20)
    recovery_code = _hex(16).upper()

    return f"""# ============================================================================
# Mus Luxury — PRODUCTION .env
# Generated {now} by backend/scripts/generate_production_env.py
# ============================================================================
#
# This file holds live production secrets. Treat it like a key:
#
#   * NEVER commit it. `.env` and `.env.*` are already in .gitignore.
#   * Copy to the VPS at `/opt/luxe/shared/.env`, chmod 0600, owner `luxe`.
#   * Rotate SECRET_KEY / CMS_HMAC_SIGNING_SECRET every 6 months or on
#     any suspected compromise. BACKUP_ENCRYPTION_KEY is deliberately
#     stable — rotating it orphans historical encrypted backups.
#   * The owner's password below is a one-shot bootstrap value; log in
#     once, change it immediately in the CMS.
#
# Fields marked <FILL_IN_xxx> require the owner's own vendor credentials
# (Meta WhatsApp Business, Chargily, Yalidine, S3). Leave them as-is if
# the feature is not yet enabled — the backend degrades gracefully.
# ============================================================================

APP_NAME="Mus Luxury (LUXE)"
APP_ENV=production
API_V1_PREFIX=/api/v1
DEFAULT_LOCALE=fr
SUPPORTED_LOCALES=fr,ar,en
PRIMARY_CURRENCY=DZD
PUBLIC_STORE_URL=https://{domain}
PUBLIC_API_URL=https://{api_domain}/api/v1
CORS_ALLOWED_ORIGINS=https://{domain},https://www.{domain},https://{api_domain},tauri://localhost

# ----------------------------------------------------------------------------
# Cryptographic secrets (NEVER regenerate without a plan — in-flight sessions
# will be invalidated and signed URLs will fail).
# ----------------------------------------------------------------------------
SECRET_KEY={secret_key}
CMS_HMAC_SIGNING_SECRET={cms_hmac}
ACCESS_TOKEN_EXPIRE_MINUTES=240
MAX_LOGIN_ATTEMPTS_PER_MINUTE=5
SIGNATURE_MAX_SKEW_SECONDS=300

# ----------------------------------------------------------------------------
# Database — PostgreSQL 16, bind the service only to the internal Docker
# network. Never expose 5432 on the public IP.
# ----------------------------------------------------------------------------
LUXE_DB_ENGINE=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=luxe_ecommerce
POSTGRES_USER=luxe_app_user
POSTGRES_PASSWORD={pg_password}
DATABASE_URL=postgresql://luxe_app_user:{pg_password}@db:5432/luxe_ecommerce

# ----------------------------------------------------------------------------
# First-time owner bootstrap. In production, APP_ENV=production normally
# blocks default-admin seeding (owner runs the setup wizard in the CMS).
# If you prefer a pre-seeded admin, set LUXE_SEED_DEMO_ACCOUNTS=1 below AND a
# strong ADMIN_INITIAL_PASSWORD (12+ characters): weak, placeholder or the
# public development passwords are refused in production (no account created).
# These values are what the wizard pre-fills if you choose to seed.
# ----------------------------------------------------------------------------
LUXE_SEED_DEMO_ACCOUNTS=0
LUXE_SEED_DEMO_PRODUCTS=0
ADMIN_INITIAL_EMAIL={admin_email}
ADMIN_INITIAL_PASSWORD={admin_pw}
ADMIN_INITIAL_FULL_NAME="Owner"
ADMIN_SECONDARY_PHONE={emergency_phone}

STORE_WHATSAPP_CONTACT_NUMBER={admin_whatsapp}

# ----------------------------------------------------------------------------
# Delivery providers (optional — manual CMS fallback always works).
# ----------------------------------------------------------------------------
DELIVERY_DEFAULT_PROVIDER=manual_cms
YALIDINE_API_ID=<FILL_IN_YALIDINE_API_ID>
YALIDINE_API_TOKEN=<FILL_IN_YALIDINE_API_TOKEN>
YALIDINE_API_BASE_URL=https://api.yalidine.app/v1
ZR_EXPRESS_API_KEY=<FILL_IN_ZR_EXPRESS_API_KEY>
ZR_EXPRESS_TOKEN=<FILL_IN_ZR_EXPRESS_TOKEN>
ZR_EXPRESS_BASE_URL=https://procolis.com/api_v1
MAYSTRO_API_TOKEN=<FILL_IN_MAYSTRO_API_TOKEN>
MAYSTRO_STORE_ID=<FILL_IN_MAYSTRO_STORE_ID>

# ----------------------------------------------------------------------------
# Payments (optional — COD is the Algerian default).
# ----------------------------------------------------------------------------
PAYMENT_DEFAULT_METHOD=cod
CHARGILY_MODE=live
CHARGILY_PUBLIC_KEY=<FILL_IN_CHARGILY_PUBLIC_KEY>
CHARGILY_SECRET_KEY=<FILL_IN_CHARGILY_SECRET_KEY>
CHARGILY_WEBHOOK_SECRET=<FILL_IN_CHARGILY_WEBHOOK_SECRET>

META_PIXEL_ID=
TIKTOK_PIXEL_ID=
GOOGLE_MAPS_API_KEY=

# ----------------------------------------------------------------------------
# Storage + encrypted backups. BACKUP_ENCRYPTION_KEY is stable: do NOT
# regenerate it unless you have a plan for migrating existing archives.
# ----------------------------------------------------------------------------
STORAGE_PROVIDER=local
UPLOAD_DIR=/var/lib/luxe/uploads
MAX_UPLOAD_SIZE_MB=5
ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/webp

BACKUP_DIR=/var/lib/luxe/backups
BACKUP_RETENTION_DAYS=30
BACKUP_CRON_SCHEDULE="30 3 * * *"
BACKUP_ENCRYPTION_KEY={backup_key}

S3_BACKUP_ENABLED=false
S3_ENDPOINT_URL=https://s3.eu-west-3.amazonaws.com
S3_REGION=eu-west-3
S3_BUCKET_NAME=mus-luxury-backups
S3_ACCESS_KEY_ID=<FILL_IN_S3_ACCESS_KEY_ID>
S3_SECRET_ACCESS_KEY=<FILL_IN_S3_SECRET_ACCESS_KEY>

# ----------------------------------------------------------------------------
# SMTP (optional — alerts + receipts by email).
# ----------------------------------------------------------------------------
SMTP_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=contact@{domain}
SMTP_PASSWORD=<FILL_IN_SMTP_APP_PASSWORD>
SMTP_FROM_EMAIL="Mus Luxury <contact@{domain}>"

# ----------------------------------------------------------------------------
# Frontend build inputs (used by Vite / Tauri at build time).
# ----------------------------------------------------------------------------
VITE_API_BASE_URL=https://{api_domain}/api/v1
VITE_CMS_API_URL=https://{api_domain}/api/v1
VITE_STORE_WHATSAPP_NUMBER={admin_whatsapp}
VITE_ENABLE_REQUEST_SIGNING=true

# ----------------------------------------------------------------------------
# POS compatibility matrix — bump these in lockstep with Desktop CMS releases.
# ----------------------------------------------------------------------------
POS_MIN_SUPPORTED_VERSION=1.0.0
POS_LATEST_VERSION=1.0.0
POS_API_CONTRACT_VERSION=1
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("--domain", required=True,
                        help="Public bare domain, e.g. 'mus-luxury.com' (no scheme, no www).")
    parser.add_argument("--admin-email", required=True,
                        help="First-owner email used by the setup wizard pre-fill.")
    parser.add_argument("--admin-whatsapp", required=True,
                        help="Owner WhatsApp phone in international format, e.g. +213655534154.")
    parser.add_argument("--emergency-phone", default="",
                        help="Secondary phone number (optional). Defaults to admin-whatsapp.")
    parser.add_argument("--out", default="scratch/production.env",
                        help="Output path. Default: scratch/production.env (git-ignored).")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing output file.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = repo_root / out_path

    if out_path.exists() and not args.force:
        print(
            f"ERROR: {out_path} already exists. Re-run with --force to overwrite.\n"
            "       (This guards against silently rotating live secrets.)",
            file=sys.stderr,
        )
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)

    body = render(
        domain=args.domain.strip().lstrip("https://").lstrip("http://").rstrip("/"),
        admin_email=args.admin_email.strip(),
        admin_whatsapp=args.admin_whatsapp.strip(),
        emergency_phone=(args.emergency_phone or args.admin_whatsapp).strip(),
    )
    out_path.write_text(body, encoding="utf-8")
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        # Windows has no POSIX permission bits — skip silently.
        pass

    print(f"✓ Wrote {out_path}")
    print(f"✓ Mode set to 0600 (owner-only read/write).")
    print()
    print("Next steps:")
    print("  1. Edit the file. Replace every <FILL_IN_...> with the real vendor value.")
    print("     Leave <FILL_IN_...> as-is for features you have not enabled yet;")
    print("     the backend degrades gracefully.")
    print("  2. Copy to the VPS, then chmod it there too:")
    print(f"       scp {out_path} luxe@<vps>:/opt/luxe/shared/.env")
    print(f"       ssh luxe@<vps> 'chmod 0600 /opt/luxe/shared/.env'")
    print("  3. Store the ADMIN_INITIAL_PASSWORD printed below in a password manager.")
    print("     Log in to the CMS once with it, then change it immediately.")
    print()
    print("Critical values (copy into a password manager NOW, close this terminal):")
    for line in body.splitlines():
        if line.startswith(("ADMIN_INITIAL_PASSWORD=",
                            "POSTGRES_PASSWORD=", "BACKUP_ENCRYPTION_KEY=")):
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
