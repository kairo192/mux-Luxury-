"""
Every setting the server and its scripts read from `.env` — one list.

Each entry says what the key is for, whether production needs it, whether it
is secret (its value is never shown), its default, and older names still
accepted. Used for:

  * `get(name)`               the value (or an older alias, or the default);
  * `configuration_report()`  what is set / missing / unknown, values hidden —
                              logged at start in production, shown to the owner
                              (GET /api/v1/admin/system/configuration) and by
                              `python -m app.settings check [file]`;
  * `render_template()`       the four .env templates (root .env.example and
                              infrastructure/environments/*.env.example) are
                              generated from this list — no key nobody reads.

A CI test fails when the code reads a key missing here, or a template offers a
key nothing reads.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Setting:
    name: str
    group: str
    help: str
    default: str = ""
    secret: bool = False
    required_in_production: bool = False
    aliases: Tuple[str, ...] = ()
    # False: read by the code but not offered in the .env templates
    # (internal / tests / deployment scripts set it themselves).
    in_template: bool = True
    example: str = ""


GROUPS: Dict[str, str] = {
    "core": "Shop and domain",
    "security": "Security (generated — keep secret)",
    "database": "Database",
    "first_start": "First start (owner account)",
    "files": "Photos and backups",
    "offsite": "Off-site backup copy (S3-compatible storage)",
    "whatsapp": "WhatsApp Cloud API webhook (optional)",
    "pos": "Desktop CMS / till versions",
    "deployment": "Deployment (set by the deploy scripts)",
    "internal": "Internal / tests",
}

SETTINGS: List[Setting] = [
    # ------------------------------------------------------------------ core
    Setting("APP_ENV", "core", "production on the VPS; development/test elsewhere (demo data, docs, relaxed checks).",
            default="production", required_in_production=True, example="production"),
    Setting("PUBLIC_STORE_URL", "core", "Public address of the shop (links in Google, sitemap, shared links).",
            default="https://mus-luxury.com", required_in_production=True, example="https://mus-luxury.com"),
    Setting("CORS_ORIGINS", "core", "Extra web addresses allowed to call the API, comma-separated "
            "(mus-luxury.com, www and api are always allowed).", aliases=("CORS_ALLOWED_ORIGINS",)),
    Setting("SHOP_TIMEZONE", "core", "Shop clock for daily reports and receipts.", default="Africa/Algiers",
            example="Africa/Algiers"),
    Setting("ENABLE_API_DOCS", "core", "1 = show /docs in production (off by default).", default="0", example="0"),
    # -------------------------------------------------------------- security
    Setting("SECRET_KEY", "security", "Signs logins. 64+ random hex characters; the server refuses to start without it.",
            secret=True, required_in_production=True),
    Setting("CMS_HMAC_SIGNING_SECRET", "security", "Signs requests from the desktop CMS. Different from SECRET_KEY.",
            secret=True, required_in_production=True),
    Setting("ACCESS_TOKEN_EXPIRE_MINUTES", "security", "How long a CMS login stays valid.", default="240", example="240"),
    Setting("LOGIN_ATTEMPTS_PER_MINUTE", "security", "Wrong passwords allowed per minute and address (1–30).",
            default="5", aliases=("MAX_LOGIN_ATTEMPTS_PER_MINUTE",), example="5"),
    # -------------------------------------------------------------- database
    Setting("LUXE_DB_ENGINE", "database", "postgres on the VPS; sqlite for a single PC.", default="postgres",
            required_in_production=True, example="postgres"),
    Setting("POSTGRES_HOST", "database", "PostgreSQL host (the Docker service).", default="db", example="db"),
    Setting("POSTGRES_PORT", "database", "PostgreSQL port.", default="5432", example="5432"),
    Setting("POSTGRES_DB", "database", "Database name.", default="luxe_ecommerce", example="luxe_ecommerce"),
    Setting("POSTGRES_USER", "database", "Database user.", default="luxe_app_user", example="luxe_app_user"),
    Setting("POSTGRES_PASSWORD", "database", "Database password (generated).", secret=True, required_in_production=True),
    Setting("DATABASE_URL", "database", "Full connection address (contains the password).", secret=True,
            required_in_production=True),
    Setting("LUXE_SQLITE_PATH", "database", "SQLite file when LUXE_DB_ENGINE=sqlite.", in_template=False),
    # ----------------------------------------------------------- first start
    Setting("LUXE_SEED_DEMO_ACCOUNTS", "first_start", "1 = create the owner account at first start (production: "
            "only with a strong ADMIN_INITIAL_PASSWORD). 0 = the owner uses the first-time setup screen.",
            default="0", example="0"),
    Setting("SEED_DEFAULT_ADMIN", "first_start", "Same as LUXE_SEED_DEMO_ACCOUNTS (older name).", default="0",
            in_template=False),
    Setting("LUXE_SEED_DEMO_PRODUCTS", "first_start", "1 = example products (never in production).", default="0",
            example="0"),
    Setting("ADMIN_INITIAL_EMAIL", "first_start", "Owner e-mail when the account is created at first start."),
    Setting("ADMIN_INITIAL_FULL_NAME", "first_start", "Owner name when the account is created at first start.",
            default="Propriétaire"),
    Setting("ADMIN_INITIAL_PASSWORD", "first_start", "Owner password when the account is created at first start "
            "(12+ characters). Change it after the first login.", secret=True),
    Setting("EDITOR_INITIAL_PASSWORD", "first_start", "Development/test only: second account.", secret=True,
            in_template=False),
    # ----------------------------------------------------------------- files
    Setting("UPLOAD_DIR", "files", "Product photos.", default="/var/lib/luxe/uploads", example="/var/lib/luxe/uploads"),
    Setting("BACKUP_DIR", "files", "Encrypted backups.", default="/var/lib/luxe/backups", example="/var/lib/luxe/backups"),
    Setting("BACKUP_ENCRYPTION_KEY", "files", "Encrypts every backup. Keep a copy in a password manager: "
            "without it no backup can be restored.", secret=True, required_in_production=True),
    Setting("BACKUP_RETENTION_DAYS", "files", "Days database backups are kept.", default="30", example="30"),
    Setting("BACKUP_CRON_SCHEDULE", "files", "When the nightly backup runs (cron format).", default="30 3 * * *",
            example="30 3 * * *"),
    Setting("BACKUP_MEDIA_KEEP", "files", "Photo archives kept (only made when photos change).", default="3",
            example="3"),
    Setting("BACKUP_MIN_FREE_PCT", "files", "Under this % of free disk, photo archives are skipped.", default="15",
            example="15"),
    # --------------------------------------------------------------- offsite
    Setting("S3_BACKUP_ENABLED", "offsite", "true = copy each night's backup to S3-compatible storage "
            "(strongly recommended: the VPS can be lost).", default="false", example="false"),
    Setting("S3_ENDPOINT_URL", "offsite", "Storage address (e.g. Backblaze B2, Wasabi, OVH).",
            example="https://s3.eu-central-003.backblazeb2.com"),
    Setting("S3_REGION", "offsite", "Storage region.", example="eu-central-003"),
    Setting("S3_BUCKET_NAME", "offsite", "Bucket name.", example="mus-luxury-backups"),
    Setting("S3_BUCKET_PREFIX", "offsite", "Folder inside the bucket.", default="luxe", example="luxe"),
    Setting("S3_ACCESS_KEY_ID", "offsite", "Storage access key.", secret=True),
    Setting("S3_SECRET_ACCESS_KEY", "offsite", "Storage secret key.", secret=True),
    Setting("OFFSITE_RETENTION_DAYS", "offsite", "Days off-site copies are kept.", default="90", example="90"),
    # -------------------------------------------------------------- whatsapp
    Setting("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "whatsapp", "Webhook check (Meta app settings). Empty = webhook off. "
            "Messages to customers work without it (wa.me links).", secret=True),
    Setting("WHATSAPP_APP_SECRET", "whatsapp", "Meta app secret: checks webhook signatures.", secret=True),
    # Read by app/whatsapp.py, kept out of the templates: automatic sending
    # through the Cloud API is not built (staff send prepared wa.me messages).
    Setting("WHATSAPP_CLOUD_API_TOKEN", "whatsapp", "Not used yet (automatic sending not built).", secret=True,
            aliases=("WHATSAPP_ACCESS_TOKEN",), in_template=False),
    Setting("WHATSAPP_PHONE_NUMBER_ID", "whatsapp", "Not used yet (automatic sending not built).", in_template=False),
    Setting("WHATSAPP_BUSINESS_ACCOUNT_ID", "whatsapp", "Not used yet (automatic sending not built).", in_template=False),
    Setting("WHATSAPP_API_VERSION", "whatsapp", "Not used yet (automatic sending not built).", default="v20.0",
            in_template=False),
    Setting("WHATSAPP_TEMPLATE_NAME", "whatsapp", "Not used yet (automatic sending not built).", in_template=False),
    Setting("WHATSAPP_TEMPLATE_LANG", "whatsapp", "Not used yet (automatic sending not built).", default="fr",
            in_template=False),
    Setting("WHATSAPP_SANDBOX_MODE", "whatsapp", "Not used yet (automatic sending not built).", in_template=False),
    Setting("WHATSAPP_TEST_CAPTURE", "internal", "Tests only.", in_template=False),
    # ------------------------------------------------------------------- pos
    Setting("POS_MIN_SUPPORTED_VERSION", "pos", "Oldest desktop CMS version allowed to connect.", default="1.0.0",
            example="1.0.0"),
    Setting("POS_LATEST_VERSION", "pos", "Newest desktop CMS version (shown as an update).", default="1.0.0",
            example="1.0.0"),
    Setting("POS_API_CONTRACT_VERSION", "pos", "API contract version the CMS checks.", default="1", example="1"),
    # ------------------------------------------------------------ deployment
    Setting("COMPOSE_PROJECT_NAME", "deployment", "Docker project of the shop; added by release-deploy.sh. "
            "Never change it on a running shop (its database volume is <name>_pgdata).", in_template=False),
    Setting("STOREFRONT_INTERNAL_URL", "deployment", "Shop container address for Google pages (docker-compose).",
            in_template=False),
]

BY_NAME: Dict[str, Setting] = {s.name: s for s in SETTINGS}
ALIASES: Dict[str, str] = {a: s.name for s in SETTINGS for a in s.aliases}

# Integrations announced by older templates whose code does not exist yet.
# Their keys do nothing; listed so the report names them instead of "unknown".
NOT_BUILT: Dict[str, str] = {
    **{k: "Yalidine (delivery company API) — not built: parcels are handled outside the system"
       for k in ("YALIDINE_API_ID", "YALIDINE_API_TOKEN", "YALIDINE_API_BASE_URL")},
    **{k: "ZR Express (delivery company API) — not built"
       for k in ("ZR_EXPRESS_API_KEY", "ZR_EXPRESS_TOKEN", "ZR_EXPRESS_BASE_URL")},
    **{k: "Maystro (delivery company API) — not built" for k in ("MAYSTRO_API_TOKEN", "MAYSTRO_STORE_ID")},
    **{k: "Chargily (online card payment) — not built: payment is cash on delivery"
       for k in ("CHARGILY_MODE", "CHARGILY_PUBLIC_KEY", "CHARGILY_SECRET_KEY", "CHARGILY_WEBHOOK_SECRET",
                 "PAYMENT_DEFAULT_METHOD")},
    **{k: "E-mail sending — not built" for k in ("SMTP_ENABLED", "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
                                                 "SMTP_PASSWORD", "SMTP_FROM_EMAIL")},
    **{k: "Advertising pixels — not built" for k in ("META_PIXEL_ID", "TIKTOK_PIXEL_ID")},
    "GOOGLE_MAPS_API_KEY": "Not needed: the shop uses plain Google Maps links",
    "DELIVERY_DEFAULT_PROVIDER": "Delivery company APIs — not built",
    "WHATSAPP_APP_ID": "Not used (automatic WhatsApp sending not built)",
    **{k: "Not used: fixed by the code (French shop, DA, /api/v1, 15 MB photos)"
       for k in ("APP_NAME", "DEFAULT_LOCALE", "SUPPORTED_LOCALES", "PRIMARY_CURRENCY", "API_V1_PREFIX",
                 "MAX_UPLOAD_SIZE_MB", "ALLOWED_IMAGE_TYPES", "STORAGE_PROVIDER", "PUBLIC_API_URL",
                 "SIGNATURE_MAX_SKEW_SECONDS")},
    **{k: "Not used: shop phone / WhatsApp are set in CMS → Contenu"
       for k in ("STORE_WHATSAPP_CONTACT_NUMBER", "ADMIN_SECONDARY_PHONE", "ADMIN_INITIAL_WHATSAPP_PHONE")},
    "ADMIN_EMERGENCY_RECOVERY_CODE": "Removed (WhatsApp password recovery was removed; use app.admin_cli)",
    **{k: "Not read by the server: the desktop CMS and the shop are built without it"
       for k in ("VITE_API_BASE_URL", "VITE_CMS_API_URL", "VITE_STORE_WHATSAPP_NUMBER", "VITE_ENABLE_REQUEST_SIGNING")},
}


def _environ(env: Optional[Dict[str, str]]) -> Dict[str, str]:
    return os.environ if env is None else env  # type: ignore[return-value]


def raw(name: str, env: Optional[Dict[str, str]] = None) -> str:
    """The configured value of `name` (or of an older alias), without default."""
    e = _environ(env)
    s = BY_NAME.get(name)
    for key in (name, *(s.aliases if s else ())):
        v = (e.get(key) or "").strip()
        if v:
            return v
    return ""


def get(name: str, default: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> str:
    """Value of a registered setting: configured, else an alias, else the default."""
    if name not in BY_NAME:
        raise KeyError(f"{name} is not a registered setting (add it to app/settings.py)")
    v = raw(name, env)
    if v:
        return v
    return BY_NAME[name].default if default is None else default


def get_int(name: str, low: int, high: int, env: Optional[Dict[str, str]] = None) -> int:
    try:
        n = int(get(name, env=env))
    except (TypeError, ValueError):
        n = int(BY_NAME[name].default or low)
    return max(low, min(high, n))


_PLACEHOLDER = re.compile(r"^(<|replace|change|fill|your_|todo)", re.IGNORECASE)


def is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.match((value or "").strip()))


def configuration_report(env: Optional[Dict[str, str]] = None, production: Optional[bool] = None) -> dict:
    """What is configured, grouped — values never included."""
    e = _environ(env)
    if production is None:
        production = (e.get("APP_ENV") or "production").strip().lower() not in {"development", "dev", "local", "test", "testing"}
    groups: Dict[str, dict] = {}
    problems: List[str] = []
    for s in SETTINGS:
        if not s.in_template:
            continue
        value = raw(s.name, e)
        if value and is_placeholder(value):
            state = "placeholder"
        elif value:
            state = "set"
        elif s.default:
            state = "default"
        else:
            state = "empty"
        if production and s.required_in_production and state in ("empty", "placeholder"):
            problems.append(f"{s.name}: required in production ({s.help})")
        used_alias = next((a for a in s.aliases if (e.get(a) or "").strip() and not (e.get(s.name) or "").strip()), None)
        g = groups.setdefault(s.group, {"title": GROUPS[s.group], "settings": []})
        g["settings"].append({
            "name": s.name, "state": state, "secret": s.secret, "required": s.required_in_production,
            "help": s.help, **({"value": value} if (value and not s.secret and state == "set") else {}),
            **({"via_old_name": used_alias} if used_alias else {}),
        })
    known = set(BY_NAME) | set(ALIASES)
    not_built = sorted(k for k in e if k in NOT_BUILT and (e.get(k) or "").strip())
    # Read by the code but no feature uses them yet (automatic WhatsApp sending).
    reserved = sorted(n for s in SETTINGS if not s.in_template and s.help.startswith("Not used yet")
                      for n in (s.name, *s.aliases) if (e.get(n) or "").strip())
    offsite_on = raw("S3_BACKUP_ENABLED", e).lower() in ("1", "true", "yes")
    if production and not offsite_on:
        problems.append("S3_BACKUP_ENABLED: backups stay on the VPS only (no off-site copy)")
    if offsite_on:
        for k in ("S3_ENDPOINT_URL", "S3_BUCKET_NAME", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
            v = raw(k, e)
            if not v or is_placeholder(v):
                problems.append(f"{k}: needed because S3_BACKUP_ENABLED is on")
    return {
        "production": production,
        "ok": not any("required in production" in p for p in problems),
        "problems": problems,
        "groups": groups,
        "not_built": [{"name": k, "note": NOT_BUILT[k]} for k in not_built]
                     + [{"name": k, "note": "Not used yet (automatic WhatsApp sending not built)"} for k in reserved],
        "unknown": [],  # filled by check_file (environment variables of the system are not listed)
        "_known": known,
    }


def parse_env_file(path: str) -> Dict[str, str]:
    """KEY=VALUE lines as Docker reads them (quotes removed, comments skipped)."""
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", line)
            if not m or line.lstrip().startswith("#"):
                continue
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            else:
                val = re.sub(r"\s+#.*$", "", val)
            out[m.group(1)] = val
    return out


def check_file(path: str, production: bool = True) -> dict:
    env = parse_env_file(path)
    rep = configuration_report(env, production=production)
    rep["unknown"] = sorted(k for k in env if k not in rep["_known"] and k not in NOT_BUILT)
    return rep


def public_report(env: Optional[Dict[str, str]] = None) -> dict:
    rep = configuration_report(env)
    rep.pop("_known", None)
    return rep


PROFILES = {
    # Root .env.example (docker compose) and the VPS templates: production values.
    "production": {"APP_ENV": "production", "LUXE_DB_ENGINE": "postgres"},
    "staging": {"APP_ENV": "production", "LUXE_DB_ENGINE": "postgres",
                "PUBLIC_STORE_URL": "https://staging.mus-luxury.com"},
    # One PC, no Docker: SQLite, demo data and API docs allowed.
    "development": {"APP_ENV": "development", "LUXE_DB_ENGINE": "sqlite", "ENABLE_API_DOCS": "1",
                    "PUBLIC_STORE_URL": "http://localhost:5173", "UPLOAD_DIR": "./backend/uploads",
                    "BACKUP_DIR": "./backend/backups"},
}


def _secret_placeholder(name: str) -> str:
    if name == "DATABASE_URL":
        return "postgresql://luxe_app_user:<CHANGE_ME_POSTGRES_PASSWORD>@db:5432/luxe_ecommerce"
    if name in ("SECRET_KEY", "CMS_HMAC_SIGNING_SECRET"):
        return "<CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_64>"
    if name == "BACKUP_ENCRYPTION_KEY":
        return "<CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32>"
    if name == "POSTGRES_PASSWORD":
        return "<CHANGE_ME_POSTGRES_PASSWORD>"
    # Provider secrets: empty = feature off until filled in.
    return ""


def render_template(profile: str = "production") -> str:
    """An .env template generated from SETTINGS (only keys the code reads)."""
    overrides = PROFILES[profile]
    lines = [
        "# =============================================================================",
        f"# Mus Luxury — .env template ({profile}). GENERATED from backend/app/settings.py:",
        "# do not edit by hand — change the list there, then run (from backend/):",
        "#   python3 -m app.settings templates",
        "# Real values: python3 backend/scripts/generate_production_env.py (fresh secrets)",
        "# Check a filled file: python3 -m app.settings check <file>",
        "# Empty value = feature off.  <CHANGE_ME_…> = must be generated before use.",
        "# =============================================================================",
    ]
    for gid, title in GROUPS.items():
        items = [s for s in SETTINGS if s.group == gid and s.in_template]
        if not items:
            continue
        lines += ["", f"# --- {title} " + "-" * max(3, 72 - len(title))]
        for s in items:
            flag = " [REQUIRED in production]" if s.required_in_production else ""
            lines.append(f"# {s.help}{flag}")
            if s.name in overrides:
                value = overrides[s.name]
            elif s.secret:
                value = _secret_placeholder(s.name)
            else:
                value = s.example or s.default
            lines.append(f"{s.name}={value}")
    built = sorted({v.split(" — ")[0] for v in NOT_BUILT.values() if "not built" in v})
    lines += ["", "# Not built yet — no key to set: " + "; ".join(built) + "."]
    return "\n".join(lines) + "\n"


TEMPLATE_FILES = {
    ".env.example": "production",
    "infrastructure/environments/production.env.example": "production",
    "infrastructure/environments/staging.env.example": "staging",
    "infrastructure/environments/development.env.example": "development",
}


def write_templates(repo_root: str) -> List[str]:
    written = []
    for rel, profile in TEMPLATE_FILES.items():
        path = os.path.join(repo_root, rel)
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_template(profile))
        written.append(rel)
    return written


def _print_report(rep: dict) -> None:
    print(f"Mus Luxury configuration — {'production' if rep['production'] else 'development'}")
    for g in rep["groups"].values():
        print(f"\n[{g['title']}]")
        for s in g["settings"]:
            mark = {"set": "OK ", "default": "def", "empty": " - ", "placeholder": " ? "}[s["state"]]
            if s["required"] and s["state"] in ("empty", "placeholder") and rep["production"]:
                mark = "!! "
            alias = f"  (old name {s['via_old_name']})" if s.get("via_old_name") else ""
            print(f"  {mark} {s['name']}{alias}")
    if rep["not_built"]:
        print("\nKeys for features not built (they do nothing):")
        for n in rep["not_built"]:
            print(f"   - {n['name']}: {n['note']}")
    if rep.get("unknown"):
        print("\nUnknown keys (typo?): " + ", ".join(rep["unknown"]))
    print("\nOK = set   def = default value   - = empty (feature off)   ? = placeholder, not filled in (feature off)"
          "   !! = REQUIRED and missing")
    print("\n" + ("OK — every required setting is present" if rep["ok"] else "MISSING REQUIRED SETTINGS"))
    for p in rep["problems"]:
        print(f"  ! {p}")


def main(argv: Iterable[str]) -> int:
    args = list(argv)
    if args[:1] == ["template"]:
        sys.stdout.write(render_template(args[1] if len(args) > 1 else "production"))
        return 0
    if args[:1] == ["templates"]:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for rel in write_templates(root):
            print(f"wrote {rel}")
        return 0
    if args[:1] == ["check"]:
        rep = check_file(args[1], production=True) if len(args) > 1 else public_report()
        _print_report(rep)
        return 0 if rep["ok"] else 1
    print("usage: python -m app.settings check [env-file] | template [profile] | templates")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
