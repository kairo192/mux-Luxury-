# Mus Luxury (`LUXE`) — Octenium VPS Deployment Guide

## 1. Production VPS Specifications

- **Hosting Provider:** Octenium Cloud
- **Public IPv4:** `5.196.163.6`
- **Operating System:** Ubuntu 24.04 LTS (Noble Numbat)
- **CPU:** 1 vCore
- **RAM:** 2 GB
- **Disk:** 40 GB NVMe Storage
- **Swap:** 2 GB (`vm.swappiness = 10`)
- **Public Domains:**
  - `https://mus-luxury.com` (Storefront)
  - `https://www.mus-luxury.com` (Storefront canonical redirect)
  - `https://api.mus-luxury.com` (FastAPI backend & WebSocket gateway)

> [!IMPORTANT]
> **Active Host Status:** The host `5.196.163.6` timed out on SSH port 22 and ICMP ping during the latest automated pre-flight audit. The VPS must be powered on or rebooted via the Octenium Control Panel before executing remote SSH deployments.

---

## 2. Docker Container Resource Allocation (Total Footprint: ~608 MB)

To ensure high stability on the 2 GB RAM / 1 vCore Octenium VPS, strict memory and CPU caps are enforced via `docker-compose.yml`:

| Container | Service | Memory Limit | CPU Limit | Internal Port | Public Exposure |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `luxe_postgres` | PostgreSQL 16 Alpine | 256 MB | 0.50 | 5432 | **None** (Private bridge) |
| `luxe_api` | FastAPI Python 3.11 | 256 MB | 0.50 | 8000 | **None** (Internal bridge) |
| `luxe_storefront` | Online shop (static index.html) | 32 MB | 0.15 | 80 | **None** (Internal bridge) |
| `luxe_proxy` | Nginx 1.27 Alpine | 64 MB | 0.25 | 80, 443 | **80, 443** (Public) |
| **Total** | | **608 MB** | **1.40** | | |

*Remaining RAM (~1.4 GB) is reserved for Ubuntu OS kernel, disk buffers, SSH daemon, and system maintenance tasks.*

### Keeping a 1 vCPU / 2 GB / 40 GB server comfortable

| Pressure | What keeps it small |
|---|---|
| Disk (40 GB) | Photos reduced to 1600 px / ~300 KB on upload; nightly photo archive only when photos changed, newest 3 kept; database dumps 30 days; backup skips photos under 15 % free disk and drops dumps older than 7 days under 7 % (warning in `last_backup_status.json`); Docker logs rotated (10 MB); copies of every backup on the owner's PC |
| Memory (API 256 MB) | Backup snapshot streamed table by table (≈1.5 MB peak instead of the whole database); photos decoded at reduced scale; one API process, database pool 15 ≤ 30 connections |
| CPU (1 vCPU) | Shop lists (products, categories, delivery) computed once and shared for 5 s, emptied by any change; shop pages poll once a minute and only while visible; builds and tests run on GitHub, never on the VPS; backups at 03:30 |

Check on the server: `nproc; free -h; df -h /; docker stats --no-stream; sudo du -sh /var/lib/luxe/backups`.

---

## 3. Server Preparation & Bootstrap

When connecting via SSH (`root@5.196.163.6`), execute the bootstrap sequence:

```bash
# 1. Update OS packages
apt-get update && apt-get upgrade -y
apt-get install -y curl ufw ca-certificates gnupg lsb-release

# 2. Configure UFW Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Let’s Encrypt'
ufw allow 443/tcp comment 'HTTPS Production'
ufw enable

# 3. Optimize Virtual Memory
sysctl vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.d/99-luxe-swappiness.conf

# 4. Install Official Docker Engine (APT - NOT Snap)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 4. Production Deployment Steps

Deploying via the automated release script (`infrastructure/scripts/deploy_algeria_vps.sh`):

```bash
# 1. Clone or pull latest code
cd /var/www/luxe-ecommerce
git pull origin feat/pos-core-cash-register

# 2. Ensure environment secrets are configured
# Copy production template and generate cryptographically secure values
cp infrastructure/environments/production.env.example .env
nano .env

# Generate real production keys:
# openssl rand -hex 64  -> for SECRET_KEY
# openssl rand -hex 64  -> for CMS_HMAC_SIGNING_SECRET
# openssl rand -base64 32 -> for POSTGRES_PASSWORD

# Restrict permissions
chmod 600 .env

# 3. Launch Docker Compose Stack
docker compose -f docker-compose.yml up -d --build

# 4. Verify Container Health
docker compose ps
docker compose logs -f api
```

---

## 5. Domain & DNS Checklist

Prior to requesting production Let's Encrypt certificates, verify DNS records point to `5.196.163.6`:

| Record Type | Hostname / Name | Target / Value | Purpose |
| :---: | :---: | :---: | :---: |
| **A** | `mus-luxury.com` | `5.196.163.6` | Public Storefront Apex |
| **A** | `www.mus-luxury.com` | `5.196.163.6` | Public Storefront Subdomain |
| **A** | `api.mus-luxury.com` | `5.196.163.6` | API Gateway & Desktop CMS Host |

> [!CAUTION]
> Preserve existing DNS MX, SPF, DKIM, and DMARC records for corporate email delivery. Do not alter MX records during deployment.


---

## 6. HTTPS certificate that renews by itself

Let's Encrypt certificates last **90 days**. Without automatic renewal the shop shows a browser security error
on day 91. `infrastructure/scripts/certificates.sh` handles everything:

```bash
# Release layout (/opt/luxe, CD deploys):
sudo CERTBOT_EMAIL=<owner e-mail> bash infrastructure/scripts/certificates.sh setup
# One-command layout (§4, /var/www/luxe-ecommerce): tell it where nginx reads the certificate
sudo SSL_DIR=/var/www/luxe-ecommerce/infrastructure/nginx/ssl CERTBOT_EMAIL=<owner e-mail> \
     bash infrastructure/scripts/certificates.sh setup
```

1. **First run, before the shop is up:** gets the first certificate (certbot answers on port 80 itself; if nginx
   is already running it is stopped for about a minute) and copies it where nginx reads it.
2. **Run `sudo luxe-certificates setup` once more after the shop is up:** renewals switch to the *webroot*
   method — nginx answers Let's Encrypt from `/var/www/certbot` (`/.well-known/acme-challenge/`, port 80), so
   **renewals never stop the shop**. A renewal test (dry run) is made.
3. From then on certbot's own timer renews about 30 days before expiry; after each renewal the hook copies the
   files and **reloads** nginx (no restart, no lost visit).

Check at any time: `sudo luxe-certificates check` (exit 1 under 14 days left).

## 6b. Things the deploy script now takes care of

- **One Docker project for every release.** `shared/.env` gets `COMPOSE_PROJECT_NAME` on the first deploy (the
  project of the database already running, else `luxe`). Never change it on a running shop: the database
  volume is `<name>_pgdata`. If the deploy stops with "database volume … does not exist, but these do: …", put the
  name before `_pgdata` in `shared/.env` and deploy again — nothing was changed.
- **The `.env` is read like Docker reads it** (placeholders and special characters in passwords are fine); the
  nightly backup runs `infrastructure/backups/nightly_backup.sh`. On a server installed before 12 Nov 2026, run
  `sudo bash infrastructure/backups/install_backup_cron.sh` once after the next deploy.
- **Disk:** old images and build cache are removed after each successful deploy.

## 7. Health check

`bash infrastructure/scripts/health-check.sh` (on the VPS) tests what customers get, through the local nginx
over HTTPS: API, readiness (database, wilayas, photo folder), product list, shop page, HTTP→HTTPS redirect,
certificate days left (fails under 14) and disk use (fails at 85 %). Exit 0 = all green — usable as an Uptime
Kuma *push* monitor or a cron job.
