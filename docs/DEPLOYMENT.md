# Mus Luxury (LUXE) — Production Deployment & Algerian Hosting Guide

## 1. Target Hosting Compatibility (Algerian VPS & Cloud Providers)
Validated for standard KVM Ubuntu 22.04 / 24.04 LTS VPS environments (ICOSNET, ISSAL NET, DzSecurity, Hostarts, or European low-latency nodes serving Algeria):
- **Minimum Specs**: 2 vCPU, 4 GB RAM, 40 GB NVMe SSD, Docker Engine 24+ & Docker Compose v2.
- **Network Ports**: Only TCP `80` (HTTP -> 301 HTTPS redirect) and TCP `443` (HTTPS TLS 1.3 via Nginx) are exposed publicly. PostgreSQL (`5432`) and FastAPI (`8000`) run on an internal Docker bridge (`internal: true`).

## 2. Step-by-Step Reproducible Production Deployment
```bash
# 1. Clone repository and configure production environment variables
cp .env.example .env
chmod 600 .env
# Edit .env: set strong POSTGRES_PASSWORD, SECRET_KEY (64+ hex chars), and WHATSAPP_CLOUD_API_TOKEN

# 2. Launch production stack (PostgreSQL 16, FastAPI, Storefront, Nginx)
./infrastructure/scripts/deploy_algeria_vps.sh
```

## 3. Production Smoke-Test Procedure
After deployment, run the following verification checks:
```bash
# 1. Liveness & Readiness check (must report status="ready" and active_wilayas=69)
curl -fsS http://127.0.0.1:8000/api/v1/ready

# 2. Public Storefront Settings & Security Headers check
curl -I http://127.0.0.1:8000/api/v1/store/settings

# 3. Full 64-Test Automated Verification Suite
docker compose exec -T api python3 -m unittest discover -s tests -v
```

## 4. Building the Windows Desktop CMS Installer (`.exe` / `.msi`)
- **Automated via GitHub Actions**: Push to `main` or trigger `.github/workflows/build-desktop-cms.yml` (`windows-latest` runner) to produce the signed NSIS `.exe` and WiX `.msi` installers in GitHub Actions Artifacts.
- **Local Windows 10/11 Build**:
  ```powershell
  cd apps/desktop-cms
  npm install
  npx tauri build
  ```
