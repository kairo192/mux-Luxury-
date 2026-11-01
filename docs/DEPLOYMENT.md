# DEPLOYMENT & ALGERIA VPS HOSTING GUIDE — MUS LUXURY (`LUXE`)

---

## 1. Hosting Requirements & Algerian Provider Compatibility

Because the **Mus Luxury (`LUXE`)** platform runs a persistent **Python 3.11 FastAPI** service, a transactional **PostgreSQL 16** database, automated **cron backups**, and an **Nginx TLS reverse proxy** (plus optional **WireGuard VPN** for the Desktop CMS), **standard PHP/cPanel shared hosting is NOT sufficient**.

You must provision a **Linux VPS (Ubuntu 22.04 LTS or 24.04 LTS)** with root/SSH and Docker support (for example, an Algerian Cloud VPS from Icosnet, Djaweb, Ayrade, or an欧洲/European low-latency VPS in Marseille/Paris ~25ms from Algiers/Blida):
- **Minimum Specs**: 2 vCPU, 4 GB RAM, 40 GB NVMe SSD.
- **Required Ports**:
  - `80/tcp` & `443/tcp`: Public HTTPS storefront (`musluxury.dz`) and `/api/v1/*` reverse proxy.
  - `51820/udp` (Optional): WireGuard encrypted tunnel for `/api/v1/admin/*` Desktop CMS administration.
  - PostgreSQL (`5432/tcp`) is bound strictly to `127.0.0.1` / internal Docker network and is **never** exposed to the public internet.

---

## 2. Environment Separation & Required Variables

Create `/opt/luxe-ecommerce/.env` on the production server (never commit `.env` to Git):

```ini
# Environment & Security
ENV=production
SECRET_KEY=<generate-64-byte-hex-secret-via-openssl-rand-hex-64>
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Database (PostgreSQL 16)
DATABASE_URL=postgresql://luxe_user:<strong-db-password>@postgres:5432/luxe_prod

# CORS & Domain
ALLOWED_ORIGINS=https://musluxury.dz,https://www.musluxury.dz,tauri://localhost

# Official WhatsApp Business Cloud API (Optional — Required only for live WhatsApp OTP delivery)
WHATSAPP_CLOUD_API_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

---

## 3. Build & Runtime Commands

### A. Backend & Database (`backend/`)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run automated test suite (uses isolated temporary SQLite database)
python3 -m unittest discover -s tests -v

# Start production ASGI server behind Nginx
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers
```

### B. Public Storefront (`apps/storefront/`)
```bash
cd apps/storefront
npm ci
VITE_API_BASE_URL=https://musluxury.dz/api/v1 npm run build
```

### C. Windows Desktop CMS (`apps/desktop-cms/`)
```bash
cd apps/desktop-cms
npm ci
VITE_CMS_API_URL=https://musluxury.dz/api/v1 npm run tauri build
# Produces Windows installer in apps/desktop-cms/src-tauri/target/release/bundle/msi/
```

### D. Docker Compose Production Stack
```bash
docker compose up -d --build
```

---

## 4. External Dependencies & Pre-Launch Checklist

1. **DNS Configuration**: Point `A` records for `musluxury.dz` and `api.musluxury.dz` to the VPS public IPv4 address.
2. **TLS Certificates**: Run `certbot --nginx -d musluxury.dz -d www.musluxury.dz -d api.musluxury.dz` so HTTPS and HSTS are active.
3. **First-Time Owner Setup**: Open the Windows Desktop CMS on first launch, enter the owner's full name, email, password, primary WhatsApp number (`0655534154`), and emergency number, and save the generated `EMERGENCY-...` offline recovery code in a physical safe.
4. **WhatsApp Business Cloud API (Optional)**: Until `WHATSAPP_CLOUD_API_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are populated in `.env`, the backend honestly returns `503 Service Unavailable` for `whatsapp_cloud_api` OTP requests and directs the owner to use the offline emergency recovery code.


---

## 9. Database, CMS Administrator & WhatsApp Cloud API Credentials Reference

### A. PostgreSQL 16 Database Credentials (Docker & Production VPS)
- **Container / Host (`POSTGRES_HOST`)**: `db` (internal Docker network) or `127.0.0.1` (via WireGuard `10.8.0.1`)
- **Port (`POSTGRES_PORT`)**: `5432`
- **Database Name (`POSTGRES_DB`)**: `luxe_ecommerce`
- **Username (`POSTGRES_USER`)**: `luxe_app_user`
- **Password (`POSTGRES_PASSWORD`)**:Configured in `.env` (default template value: `LuxePgProd_2026_Dz!99482aBc` — rotate via `.env` on live VPS)
- **Connection URI (`DATABASE_URL`)**:
  `postgresql+psycopg://luxe_app_user:LuxePgProd_2026_Dz!99482aBc@db:5432/luxe_ecommerce`

### B. Local / CI SQLite 3 Database
- **File Path (`LUXE_SQLITE_PATH`)**: `./backend/luxe_store.sqlite3`
- **Schema**: `backend/migrations/001_initial_schema.sql` (24 tables, identical to `001_initial_schema_postgres.sql`)

### C. Initial Seeded CMS Accounts & Recovery Credentials
| Role | Email | Default Password | Verified WhatsApp Phones | Offline Emergency Code |
| :--- | :--- | :--- | :--- | :--- |
| **Owner (`super_admin`)** | `admin@musluxury.dz` | `MusLuxury2026!` | `0655534154` (`+213655534154`) & `+213550000001` | `LUXE-EMERGENCY-2026-RECOVERY` |
| **Product Manager (`product_manager`)** | `editor@musluxury.dz` | `EditorLuxury2026!` | `+213550000002` (`0550000002`) | — |

### D. WhatsApp Cloud API & External Tokens in `.env`
All required tokens are pre-structured in `.env.example` (and `.env` for local execution, protected by `.gitignore`):
- `WHATSAPP_CLOUD_API_TOKEN` / `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_APP_ID` & `WHATSAPP_APP_SECRET`
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (`mus_luxury_wa_webhook_verify_2026_secret`)
- `WHATSAPP_API_VERSION=v20.0` & `WHATSAPP_TEMPLATE_NAME=luxe_admin_password_reset`
- `WHATSAPP_SANDBOX_MODE=true` (set to `false` once live Meta permanent token is inserted)
- Optional Algerian courier tokens (`YALIDINE_API_ID`, `YALIDINE_API_TOKEN`, `ZR_EXPRESS_API_KEY`, `ZR_EXPRESS_TOKEN`, `MAYSTRO_API_TOKEN`) & `CHARGILY_SECRET_KEY`.
