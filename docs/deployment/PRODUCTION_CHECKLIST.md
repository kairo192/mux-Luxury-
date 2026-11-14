# Mus Luxury (LUXE) — Pre-Flight Production Checklist

**Target Go-Live Date:** November 2026  
**Target Domains:** `https://mus-luxury.com` | `https://api.mus-luxury.com`  
**Host IP:** `5.196.163.6` (Octenium Ubuntu 24.04 LTS VPS)

---

## 1. Infrastructure & OS Verification

- [ ] **DNS Records Active:** `mus-luxury.com`, `www.mus-luxury.com`, and `api.mus-luxury.com` all resolve to `5.196.163.6`.
- [ ] **UFW Firewall Enabled:** Only ports 22, 80, 443 are open. Port 5432 and 8000 are blocked from public internet.
- [ ] **Swap Configured:** 2 GB active swap verified (`swapon --show`).
- [ ] **Sysctl Tuned:** `vm.swappiness = 10` and `vm.vfs_cache_pressure = 50` persisted in `/etc/sysctl.d/99-luxe-vps.conf`.
- [ ] **Docker Daemon Logs Bounded:** `/etc/docker/daemon.json` configured with `max-size: 10m` and `max-file: 3`.

---

## 2. Docker & Environment Configuration

- [ ] **Production `.env` Created:** Cryptographically random 64-char `SECRET_KEY` and `POSTGRES_PASSWORD` generated.
- [ ] **Fail-Closed Engine Set:** `LUXE_DB_ENGINE=postgres` and valid `DATABASE_URL` configured in `.env`.
- [ ] **Resource Limits Enforced:** `docker-compose.yml` specifies memory limits: API (256M), DB (256M), Nginx (64M), Storefront (32M).
- [ ] **Postgres Tuned for 2GB RAM:** `-c shared_buffers=128MB -c work_mem=4MB -c max_connections=30` verified in docker compose command.
- [ ] **TLS Certificates Installed:** Let's Encrypt certificates mounted in `/opt/luxe/infrastructure/nginx/ssl/`.
- [ ] **Auto-Renewal Cron Configured:** Certbot renewal cron active in `/etc/cron.d/certbot-renew`.

---

## 3. Database & Application Bootstrap

- [ ] **Database Healthy:** `docker compose ps db` displays `(healthy)`.
- [ ] **Migrations Executed:** `docker compose exec api python3 -m app.migration_runner` reports 0 errors.
- [ ] **Zero Admin Accounts Seeded:** Confirmed `SELECT count(*) FROM admin_users` returns `0` in production.
- [ ] **First-Time Setup Performed:** Store owner initialized via Desktop CMS setup wizard.
- [ ] **Emergency Token Backed Up:** Emergency recovery token printed and stored in physical safe.
- [ ] **Setup Wizard Locked:** Re-accessing `/api/v1/admin/auth/initialize-owner` returns `403 Forbidden` (`SETUP_ALREADY_INITIALIZED`).

---

## 4. Point-of-Sale (POS) & Store Operations

- [ ] **POS Version Probe Verified:** `GET /api/v1/pos/compat?client_version=1.0.0` returns `supported: true`.
- [ ] **Local SQLite Mirror Active:** Desktop CMS downloads snapshot to `%APPDATA%/dz.musluxury.cms/pos_mirror.sqlite3`.
- [ ] **Offline Barcode Scan Loop:** EAN-13 barcodes scan and look up products under 5 ms without active internet.
- [ ] **Durable Offline Queue:** Offline transactions persist in `offline_sales_queue` table in SQLite and survive reboot.
- [ ] **Offline Sales Sync:** Queued transactions sync cleanly to central server with zero duplicate entries.
- [ ] **Thermal Receipt Printer:** ESC/POS test receipt prints cleanly with luxury header and partial paper cut.
- [ ] **Cash Drawer Kick:** Cash drawer auto-opens on Cash checkout.

---

## 5. Security & Observability

- [ ] **HTTPS Enforced:** Port 80 redirects with HTTP 301 to HTTPS.
- [ ] **Security Headers Present:** HSTS, CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff present in response headers.
- [ ] **Rate Limiting Active:** Excessive rapid requests to `/api/v1/admin/auth/` trigger `HTTP 429 Too Many Requests`.
- [ ] **Health Probe Monitoring:** External uptime monitor configured for `https://api.mus-luxury.com/api/v1/ready`.
- [ ] **Nightly Backup Active:** Automated backup script installed at `/usr/local/bin/luxe-backup.sh` and verified with test restore.
- [ ] **VPS Health Monitor Script Active:** `/usr/local/bin/vps_health_monitor.sh` scheduled via cron every 5 minutes.

