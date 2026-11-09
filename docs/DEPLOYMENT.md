# Mus Luxury (LUXE) — Production Deployment Manual

**Domain:** `https://mus-luxury.com` (Main) | `https://api.mus-luxury.com` (API)  
**Host IP:** `5.196.163.6`  
**Target Host:** Octenium Ubuntu 24.04 LTS

---

## 1. Pre-Deployment DNS Verification

Configure the following DNS `A` records with your domain registrar before deploying:

| Record Type | Host / Name | Target IPv4 | TTL | Status |
| :--- | :--- | :--- | :--- | :--- |
| `A` | `mus-luxury.com` | `5.196.163.6` | 300 | Required |
| `A` | `www.mus-luxury.com` | `5.196.163.6` | 300 | Required |
| `A` | `api.mus-luxury.com` | `5.196.163.6` | 300 | Required |

Verify propagation from your local terminal:
```bash
dig +short mus-luxury.com
dig +short api.mus-luxury.com
```
Both must return `5.196.163.6`.

---

## 2. Server Environment Configuration (`.env`)

On the VPS in `/opt/luxe`, create the production `.env` file from the secure template:

```bash
cd /opt/luxe
cp infrastructure/environments/production.env.example .env
chmod 600 .env
```

Generate cryptographically secure 64-character secrets:
```bash
# Generate SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Generate POSTGRES_PASSWORD
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_hex(24))"
```

Configure `.env` with the following production values:
```ini
APP_ENV=production
DEBUG=false

# Domain and Routing
SERVER_NAME=mus-luxury.com
CORS_ORIGINS=https://mus-luxury.com,https://www.mus-luxury.com,https://api.mus-luxury.com,http://tauri.localhost,tauri://localhost

# Database Configuration
LUXE_DB_ENGINE=postgres
POSTGRES_DB=luxe_ecommerce
POSTGRES_USER=luxe_app_user
POSTGRES_PASSWORD=<PASTE_GENERATED_POSTGRES_PASSWORD>
DATABASE_URL=postgresql://luxe_app_user:<PASTE_GENERATED_POSTGRES_PASSWORD>@db:5432/luxe_ecommerce

# Security & Cryptography
SECRET_KEY=<PASTE_GENERATED_SECRET_KEY>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Persistent Storage
UPLOAD_DIR=/var/lib/luxe/uploads
BACKUP_DIR=/var/lib/luxe/backups
```

---

## 3. Deployment Execution Steps

### 3.1 Clone or Pull the Latest Code
As the `luxe` deployer user:
```bash
cd /opt/luxe
git fetch origin main
git checkout main
git pull origin main
```

### 3.2 Build and Launch Containers
Execute the production build via Docker Compose:
```bash
# Build storefront and backend images with resource limits
docker compose build --no-cache

# Start database first and wait for healthy state
docker compose up -d db
docker compose ps

# Start backend, storefront, and reverse proxy
docker compose up -d
```

### 3.3 Apply Database Migrations
Run the database schema migration runner:
```bash
docker compose exec -T api python3 -m app.migration_runner
```
Output must verify:
```
[migration_runner] Connected to database: postgres
[migration_runner] Executing 001_initial_schema_postgres.sql
[migration_runner] All migrations applied successfully. Zero errors.
```

---

## 4. Post-Deployment Verification (Smoke Tests)

Test health and readiness probes from outside the server:

```bash
# 1. Storefront HTTP -> HTTPS Redirect
curl -I http://mus-luxury.com/
# Expected: HTTP/1.1 301 Moved Permanently -> Location: https://mus-luxury.com/

# 2. Storefront HTML Content
curl -I https://mus-luxury.com/
# Expected: HTTP/2 200, Content-Type: text/html, Strict-Transport-Security

# 3. API Subdomain Health Probe
curl -s https://api.mus-luxury.com/api/v1/health | jq .
# Expected: {"status": "ok", "app_env": "production"}

# 4. API Database Readiness Probe
curl -s https://api.mus-luxury.com/api/v1/ready | jq .
# Expected: {"status": "ready", "database": "connected"}

# 5. POS Version Compatibility Probe
curl -s "https://api.mus-luxury.com/api/v1/pos/compat?client_version=1.0.0" | jq .
# Expected: {"supported": true, "deprecated": false}
```

---

## 5. First-Time Store Owner Initialization

On a fresh production installation, the database contains **zero default administrators**:

1. Open the **Mus Luxury Desktop CMS** application on the store owner's Windows workstation.
2. In the setup wizard:
   - Target API URL: `https://api.mus-luxury.com/api/v1`
   - Store Owner Name: e.g. `Mustapha Harbit`
   - Primary Email: e.g. `admin@mus-luxury.com`
   - Master Password: (Minimum 10 characters, strong uppercase, lowercase, numbers)
   - Recovery Contact Phone: e.g. `0550000001`
3. Click **Enregistrer et Sécuriser l'Accès Administrateur**.
4. The system locks the setup wizard permanently in the database.
5. Save the generated emergency backup key (`EMERGENCY-...`) securely in an offline safe.

---

## 6. Rollback Runbook

If a critical bug is detected in a new release:

```bash
# 1. Rollback Git to previous known good commit
cd /opt/luxe
git checkout <PREVIOUS_STABLE_COMMIT_HASH>

# 2. Rebuild and restart services
docker compose build storefront api
docker compose up -d --no-deps storefront api

# 3. Verify health
docker compose exec -T api python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').read().decode())"
```
