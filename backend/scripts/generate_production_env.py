#!/usr/bin/env python3
"""
Mus Luxury — production `.env` generator.

Produces a complete `.env.production` file with cryptographically strong
values for every secret the backend + storefront + CMS need at runtime.
Keys come from backend/app/settings.py (only keys the code reads). Third-party
credentials the project cannot generate (S3 off-site storage, WhatsApp webhook
secret) are left EMPTY — the feature stays off until they are filled in.

Output path defaults to `scratch/production.env` (git-ignored). This is
intentional: we do NOT want production secrets on disk under `backend/`
where a careless `git add backend/` could stage them.

Usage:
    python3 backend/scripts/generate_production_env.py \\
        --domain mus-luxury.com \\
        --admin-email admin@mus-luxury.com \\
        [--admin-name "Prénom Nom"] \\
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


def _bare_domain(raw: str) -> str:
    d = raw.strip()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.strip("/")


def render(*, domain: str, admin_email: str, admin_name: str = "") -> str:
    """The production .env: every key the code reads (app/settings.py), fresh
    secrets, the owner's domain / e-mail, defaults elsewhere. Integrations the
    owner has not signed up for stay EMPTY (= off), never placeholders."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.settings import GROUPS, NOT_BUILT, SETTINGS

    pg_password = _password(36)
    values = {
        "APP_ENV": "production",
        "PUBLIC_STORE_URL": f"https://{domain}",
        "SECRET_KEY": _hex(64),
        "CMS_HMAC_SIGNING_SECRET": _hex(64),
        "POSTGRES_PASSWORD": pg_password,
        "DATABASE_URL": f"postgresql://luxe_app_user:{pg_password}@db:5432/luxe_ecommerce",
        "BACKUP_ENCRYPTION_KEY": _hex(32),
        "ADMIN_INITIAL_EMAIL": admin_email,
        "ADMIN_INITIAL_FULL_NAME": admin_name or "Propriétaire",
        "ADMIN_INITIAL_PASSWORD": _admin_password(20),
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN": _hex(32),
    }
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    out = [
        "# ============================================================================",
        f"# Mus Luxury — PRODUCTION .env — generated {now}",
        "# Live secrets: never commit; copy to /opt/luxe/shared/.env (chmod 600).",
        "# BACKUP_ENCRYPTION_KEY: keep a copy in a password manager — without it no",
        "# backup can be restored. Check this file: python3 -m app.settings check <file>",
        "# Empty value = feature off (e.g. off-site backup copy until S3 is set).",
        "# ============================================================================",
    ]
    for gid, title in GROUPS.items():
        items = [st for st in SETTINGS if st.group == gid and st.in_template]
        if not items:
            continue
        out += ["", f"# --- {title}"]
        for st in items:
            out.append(f"# {st.help}")
            out.append(f"{st.name}={values.get(st.name, st.example or st.default)}")
    built = sorted({v.split(" — ")[0] for v in NOT_BUILT.values() if "not built" in v})
    out += ["", "# Not built yet (no key to set): " + "; ".join(built) + "."]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("--domain", required=True,
                        help="Public bare domain, e.g. 'mus-luxury.com' (no scheme, no www).")
    parser.add_argument("--admin-email", required=True,
                        help="First-owner email used by the setup wizard pre-fill.")
    parser.add_argument("--admin-name", default="",
                        help="Owner name for the account created at first start (optional).")
    # Accepted for older instructions; the shop phone / WhatsApp are set in CMS → Contenu.
    parser.add_argument("--admin-whatsapp", default="", help=argparse.SUPPRESS)
    parser.add_argument("--emergency-phone", default="", help=argparse.SUPPRESS)
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
        domain=_bare_domain(args.domain),
        admin_email=args.admin_email.strip(),
        admin_name=args.admin_name.strip(),
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
    print("  1. Off-site backups (recommended): fill the S3_* lines and set S3_BACKUP_ENABLED=true.")
    print("  2. Copy to the VPS, then:")
    print(f"       scp {out_path} luxe@<vps>:/opt/luxe/shared/.env")
    print("       ssh luxe@<vps> 'chmod 0600 /opt/luxe/shared/.env'")
    print("  3. Open the file and copy BACKUP_ENCRYPTION_KEY and ADMIN_INITIAL_PASSWORD into a")
    print("     password manager (they are not printed here, to stay out of terminal history).")
    print(f"  4. Check it:  cd backend && python3 -m app.settings check {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
