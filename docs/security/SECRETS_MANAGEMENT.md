# Mus Luxury (`LUXE`) — Secrets Management & Cryptographic Keys Standard

## 1. Secrets Separation Policy

Mus Luxury strictly isolates secrets across four decoupled boundaries:
1. **GitHub Actions Secrets** (CI/CD build, deployment & signing runners only).
2. **VPS Production Runtime Secrets** (`/opt/luxe/shared/.env` with `chmod 0600`).
3. **Local Development Environment** (developer `.env`, ignored by git).
4. **Desktop Native Keychain** (OS Credential Manager `com.musluxury.cms.wincred`).

> [!CAUTION]
> Under no circumstances may server-side secrets (`SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `CMS_HMAC_SIGNING_SECRET`) be prefixed with `VITE_` or embedded in public storefront client bundles.

---

## 2. Complete Environment Variables Matrix

| Variable | Category | Required | Consumer | How to Generate / Source |
| :--- | :--- | :---: | :--- | :--- |
| `APP_NAME` | Config | Yes | API | Static: `"Mus Luxury (LUXE)"` |
| `APP_ENV` | Config | Yes | API | `"production"`, `"staging"`, or `"development"` |
| `API_V1_PREFIX` | Config | Yes | API | `"/api/v1"` |
| `DEFAULT_LOCALE` | Config | Yes | API | `"fr"` (Options: `fr`, `ar`, `en`) |
| `PRIMARY_CURRENCY` | Config | Yes | API / Store | `"DZD"` |
| `PUBLIC_STORE_URL` | Config | Yes | API | `https://mus-luxury.com` |
| `PUBLIC_API_URL` | Config | Yes | Storefront / CMS | `https://api.mus-luxury.com/api/v1` |
| `CORS_ALLOWED_ORIGINS` | Security | Yes | API / Nginx | Comma-separated trusted origins |
| `SECRET_KEY` | Cryptographic | Yes | API (JWT) | `openssl rand -hex 64` (64 bytes) |
| `CMS_HMAC_SIGNING_SECRET` | Cryptographic | Yes | API (HMAC) | `openssl rand -hex 64` (64 bytes) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Security | Yes | API | Default: `240` (4 hours) |
| `MAX_LOGIN_ATTEMPTS_PER_MINUTE` | Security | Yes | API Rate Limit | Default: `5` |
| `SIGNATURE_MAX_SKEW_SECONDS` | Security | Yes | API Anti-Replay | Default: `300` (5 minutes) |
| `LUXE_DB_ENGINE` | Database | Yes | Database Adapter | `"postgres"` (prod) / `"sqlite"` (dev) |
| `POSTGRES_HOST` | Database | Yes | PostgreSQL | `"db"` (Docker internal network) |
| `POSTGRES_PORT` | Database | Yes | PostgreSQL | `5432` |
| `POSTGRES_DB` | Database | Yes | PostgreSQL | `"luxe_ecommerce"` |
| `POSTGRES_USER` | Database | Yes | PostgreSQL | `"luxe_app_user"` |
| `POSTGRES_PASSWORD` | Database | Yes | PostgreSQL | `openssl rand -base64 32` |
| `DATABASE_URL` | Database | Yes | API / Alembic | `postgresql://luxe_app_user:<PASS>@db:5432/luxe_ecommerce` |
| `BACKUP_ENCRYPTION_KEY` | Backups | Yes | Encrypted backups | `openssl rand -hex 32` — keep a copy in a password manager |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Backups | Optional | Off-site copy | Storage provider dashboard |

The complete, current list of keys is `backend/app/settings.py` (guide: `docs/CONFIGURATION.md`).

---

## 3. Cryptographic Secret Generation Procedures

When bootstrapping the production VPS, generate unique keys directly in the secure shell:

```bash
# 1. Generate 64-byte JWT Secret Key
export PROD_SECRET_KEY=$(openssl rand -hex 64)

# 2. Generate 64-byte HMAC Signing Secret
export PROD_HMAC_SECRET=$(openssl rand -hex 64)

# 3. Generate Strong Database Password
export PROD_DB_PASSWORD=$(openssl rand -base64 32)
```

Write these exclusively to `/opt/luxe/shared/.env` and restrict file ownership:
```bash
chmod 600 /opt/luxe/shared/.env
chown luxe:luxe /opt/luxe/shared/.env
```

---

## 4. Key Rotation Policies

| Secret | Rotation Cadence | Rotation Procedure |
| :--- | :--- | :--- |
| `SECRET_KEY` | 6 Months | Seamless: Active tokens remain valid until expiration; users log in with new token. |
| `POSTGRES_PASSWORD` | 12 Months | Requires updating both `.env` and `ALTER USER luxe_app_user WITH PASSWORD '...';`. |
| `CMS_HMAC_SIGNING_SECRET` | 6 Months | Coordinated: Update `.env` and deploy new Desktop CMS version. |
| `TAURI_SIGNING_PRIVATE_KEY` | On Compromise Only | **Critical:** Rotating the updater private key requires a manual reinstall for all running POS terminals. |

