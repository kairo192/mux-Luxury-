# Mus Luxury (LUXE) — VPS Setup & Initialization Guide

**Target Environment:** Octenium Ubuntu 24.04.5 LTS VPS  
**Specifications:** 1 vCore, 2 GB RAM, 2 GB swap, 40 GB ext4  
**Public IPv4:** `5.196.163.6`  
**Canonical Production Domains:**  
- `https://mus-luxury.com` (Main Storefront)  
- `https://www.mus-luxury.com` (Storefront Alias)  
- `https://api.mus-luxury.com` (API Gateway)

---

## 1. Initial Access & System Hardening

### 1.1 First SSH Connection
Connect as root:
```bash
ssh root@5.196.163.6
```

### 1.2 System Upgrade & Base Tools
Update the package repository and install essential system utilities:
```bash
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git ufw htop iotop fail2ban unzip ca-certificates gnupg lsb-release
```

### 1.3 Dedicated Deployer User Setup
Create an unprivileged user `luxe` with sudo access:
```bash
adduser --gecos "" --disabled-password luxe
usermod -aG sudo luxe
echo "luxe ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-luxe-deployer
chmod 0440 /etc/sudoers.d/99-luxe-deployer

# Authorize your deployment SSH public key for luxe user
mkdir -p /home/luxe/.ssh
chmod 700 /home/luxe/.ssh
cp /root/.ssh/authorized_keys /home/luxe/.ssh/authorized_keys
chown -R luxe:luxe /home/luxe/.ssh
chmod 600 /home/luxe/.ssh/authorized_keys
```

### 1.4 Persistent Swap Space & Memory Pressure Tuning
Verify swap exists (2 GB). Configure `vm.swappiness=10` and `vm.vfs_cache_pressure=50` to conserve memory and preserve file cache:
```bash
# Verify existing swap
swapon --show

# Persist sysctl parameters
cat << 'EOF' > /etc/sysctl.d/99-luxe-vps.conf
# Aggressive memory preservation for 2GB VPS
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.overcommit_memory = 0

# Network backlog tuning
net.core.somaxconn = 2048
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_slow_start_after_idle = 0
EOF

sysctl --system
```

---

## 2. Firewall Configuration (UFW)

Enforce strict inbound filtering. Only SSH (22), HTTP (80), and HTTPS (443) are publicly exposed. Database port 5432 and backend port 8000 are **NEVER** exposed publicly.

```bash
# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow operational ports
ufw allow 22/tcp comment 'SSH Secure Administration'
ufw allow 80/tcp comment 'HTTP Let’s Encrypt Verification'
ufw allow 443/tcp comment 'HTTPS Production Traffic'

# Enable firewall
ufw --force enable
ufw status verbose
```

---

## 3. Docker Engine & Compose Installation

Install official Docker Engine from the Docker repository (do not use distro `docker.io` packages):

```bash
# Install Docker GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add luxe user to docker group
usermod -aG docker luxe
```

### 3.1 Daemon Configuration: Default Log Limits
Configure Docker daemon to enforce log rotation globally across all containers as a safety net:
```bash
cat << 'EOF' > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true
}
EOF

systemctl restart docker
```

---

## 4. Production Directory Structure

Prepare the persistent host directories with correct file ownership:
```bash
# Base application directory
mkdir -p /opt/luxe
chown -R luxe:luxe /opt/luxe

# Persistent state volumes
mkdir -p /var/lib/luxe/uploads
mkdir -p /var/lib/luxe/backups
mkdir -p /var/lib/luxe/ssl

# Backend non-root container UID is 1001 (luxeuser)
chown -R 1001:1001 /var/lib/luxe/uploads
chown -R 1001:1001 /var/lib/luxe/backups
chmod 750 /var/lib/luxe/uploads
chmod 700 /var/lib/luxe/backups
```

---

## 5. SSL / TLS Bootstrap (Certbot)

Install Certbot for automated Let's Encrypt certificates:
```bash
apt-get install -y certbot

# Obtain initial certificate (stop any temp listeners on port 80 first)
certbot certonly --standalone \
  -d mus-luxury.com \
  -d www.mus-luxury.com \
  -d api.mus-luxury.com \
  --agree-tos \
  --email contact@mus-luxury.com \
  --non-interactive

# Copy certificates to the expected Nginx mount location
mkdir -p /opt/luxe/infrastructure/nginx/ssl
cp /etc/letsencrypt/live/mus-luxury.com/fullchain.pem /opt/luxe/infrastructure/nginx/ssl/fullchain.pem
cp /etc/letsencrypt/live/mus-luxury.com/privkey.pem /opt/luxe/infrastructure/nginx/ssl/privkey.pem
chmod 644 /opt/luxe/infrastructure/nginx/ssl/fullchain.pem
chmod 600 /opt/luxe/infrastructure/nginx/ssl/privkey.pem
```

Setup auto-renewal cron in `/etc/cron.d/certbot-renew`:
```bash
cat << 'EOF' > /etc/cron.d/certbot-renew
0 3 * * 1 root certbot renew --quiet --deploy-hook "cp /etc/letsencrypt/live/mus-luxury.com/fullchain.pem /opt/luxe/infrastructure/nginx/ssl/fullchain.pem && cp /etc/letsencrypt/live/mus-luxury.com/privkey.pem /opt/luxe/infrastructure/nginx/ssl/privkey.pem && docker compose -f /opt/luxe/docker-compose.yml exec -T nginx nginx -s reload"
EOF
```

---

## 6. Verification Checklist

Before deploying code, verify that all system invariants hold:
1. `swapon --show` reports 2 GB active swap.
2. `sysctl vm.swappiness` returns `10`.
3. `ufw status` shows active with ports 22, 80, 443 only.
4. `docker run --rm hello-world` executes cleanly without sudo as user `luxe`.
5. Host port 5432 and 8000 are **NOT** listening on public interfaces (`ss -tulpn`).

