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
| `luxe_storefront` | React 18 Storefront | 32 MB | 0.15 | 80 | **None** (Internal bridge) |
| `luxe_proxy` | Nginx 1.27 Alpine | 64 MB | 0.25 | 80, 443 | **80, 443** (Public) |
| **Total** | | **608 MB** | **1.40** | | |

*Remaining RAM (~1.4 GB) is reserved for Ubuntu OS kernel, disk buffers, SSH daemon, and system maintenance tasks.*

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

