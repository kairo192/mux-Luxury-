#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — one-shot VPS bootstrap.
# Run ONCE as root on a fresh Ubuntu 22.04 / 24.04 LTS VPS. Idempotent:
# re-running leaves a configured host alone.
#
# Prepares:
#   - Dedicated `luxe` deploy user with authorized_keys and sudo for docker only
#   - Docker Engine + Compose plugin
#   - UFW firewall (22, 80, 443 only — PostgreSQL stays internal to Docker)
#   - Automatic security updates
#   - /opt/luxe release layout (releases/, current symlink, shared/)
#   - Encrypted backup cron (03:30 nightly)
#   - Log rotation
#   - systemd timer for `vps-metrics.sh`
#
# What this script does NOT do:
#   - Install certificates. Run `infrastructure/scripts/certificates.sh setup` after this
#     (first certificate + renewals without downtime).
#   - Create the first release. That's `release-deploy.sh`'s job, invoked by CD.
# =============================================================================
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: run this as root (or via sudo)." >&2
  exit 1
fi

DEPLOY_USER="${DEPLOY_USER:-luxe}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/luxe}"
DOMAIN="${DOMAIN:-mus-luxury.com}"
DEPLOY_PUBLIC_KEY="${DEPLOY_PUBLIC_KEY:-}"

log() { printf '\n==[bootstrap]== %s\n' "$*"; }

# -------------------------------------------------- 1. OS hygiene
log "Updating apt and installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg openssl unzip jq ufw \
  unattended-upgrades fail2ban logrotate tzdata rsync rclone sqlite3 \
  python3 python3-venv python3-pip
dpkg-reconfigure --frontend=noninteractive unattended-upgrades || true

# -------------------------------------------------- 2. Deploy user
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  log "Creating deploy user: $DEPLOY_USER"
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi
install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
if [ -n "$DEPLOY_PUBLIC_KEY" ]; then
  echo "$DEPLOY_PUBLIC_KEY" > "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chmod 0600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
elif [ ! -s "/home/$DEPLOY_USER/.ssh/authorized_keys" ]; then
  log "WARNING: no DEPLOY_PUBLIC_KEY given and no authorized_keys exists yet"
  log "         You MUST add the GitHub Actions deploy public key before enabling CD."
fi

# -------------------------------------------------- 3. Docker
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"
systemctl enable --now docker

# -------------------------------------------------- 4. Firewall
log "Configuring UFW (22, 80, 443 only — PostgreSQL stays internal)"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'ssh'
ufw allow 80/tcp comment 'http'
ufw allow 443/tcp comment 'https'
ufw --force enable

# -------------------------------------------------- 5. Release layout
log "Preparing release layout at $INSTALL_ROOT"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$INSTALL_ROOT"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$INSTALL_ROOT/releases"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$INSTALL_ROOT/shared"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$INSTALL_ROOT/shared/nginx-ssl"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$INSTALL_ROOT/logs"

# /var/lib/luxe holds the actual data that must survive a reinstall
install -d -m 0750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /var/lib/luxe
install -d -m 0750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /var/lib/luxe/uploads
# The nightly cron runs as $DEPLOY_USER: it must be able to write here.
install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /var/lib/luxe/backups
# docker volumes bind-mount to these via docker-compose override

# -------------------------------------------------- 6. Backup cron
# Same line as infrastructure/backups/install_backup_cron.sh: nightly_backup.sh
# reads the production .env safely (encryption key, off-site target), dumps
# PostgreSQL THROUGH DOCKER, copies off-site, verifies, and logs everything.
log "Installing nightly encrypted backup cron (03:30)"
cat > /etc/cron.d/luxe-backup <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
30 3 * * * $DEPLOY_USER INSTALL_ROOT=$INSTALL_ROOT bash $INSTALL_ROOT/current/infrastructure/backups/nightly_backup.sh >> $INSTALL_ROOT/logs/backup.log 2>&1
CRON
chmod 0644 /etc/cron.d/luxe-backup

# -------------------------------------------------- 7. System metrics timer
log "Installing lightweight system-metrics timer (every 5 min)"
cat > /etc/systemd/system/luxe-metrics.service <<UNIT
[Unit]
Description=Mus Luxury lightweight metrics sampler
After=network.target

[Service]
Type=oneshot
User=$DEPLOY_USER
ExecStart=/bin/bash $INSTALL_ROOT/current/infrastructure/scripts/vps-metrics.sh
UNIT

cat > /etc/systemd/system/luxe-metrics.timer <<UNIT
[Unit]
Description=Run luxe-metrics every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=luxe-metrics.service

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now luxe-metrics.timer

# -------------------------------------------------- 8. Log rotation
cat > /etc/logrotate.d/luxe <<LOGROTATE
$INSTALL_ROOT/logs/*.log {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    create 0640 $DEPLOY_USER $DEPLOY_USER
    sharedscripts
}
LOGROTATE

# -------------------------------------------------- 9. Sanity
log "Docker version:"
docker --version
log "Compose plugin:"
docker compose version
log "UFW status:"
ufw status verbose | head -20

cat <<NEXT

===== Bootstrap complete =====
  Deploy user:  $DEPLOY_USER
  Install root: $INSTALL_ROOT
  Domain:       $DOMAIN

Next steps (as the deploy user):
  1. Put the production \`.env\` at  $INSTALL_ROOT/shared/.env  (chmod 0600, owner $DEPLOY_USER)
  2. HTTPS certificate (DNS of $DOMAIN, www and api must point to this server):
       sudo DOMAIN=$DOMAIN INSTALL_ROOT=$INSTALL_ROOT CERTBOT_EMAIL=<owner e-mail> \
            bash infrastructure/scripts/certificates.sh setup
     Run it again once after the first deploy: renewals then happen by themselves,
     without stopping the shop (check: sudo luxe-certificates check).
  3. Add the GitHub Actions deploy public key to  /home/$DEPLOY_USER/.ssh/authorized_keys  (if not already)
  4. Trigger the first deploy from GitHub Actions (cd-staging.yml / cd-production.yml)

Monitoring:
  - Uptime Kuma:  docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml up -d
  - Metrics log:  $INSTALL_ROOT/logs/metrics.log
NEXT
