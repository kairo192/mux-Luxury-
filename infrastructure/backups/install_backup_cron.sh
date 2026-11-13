#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — one-shot backup cron installer
#
# Wires the nightly backup + off-site upload + verification chain into
# /etc/cron.d/ on the VPS. Idempotent: re-running leaves a configured host
# alone. Reads $BACKUP_CRON_SCHEDULE from /opt/luxe/shared/.env so the
# operator picks the schedule once in the env file and never has to edit
# a crontab by hand.
#
# Usage:
#   sudo bash infrastructure/backups/install_backup_cron.sh
#
# What ends up in /etc/cron.d/luxe-backup after a successful run:
#
#   SHELL=/bin/bash
#   PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#   MAILTO=""
#   30 2 * * * luxe INSTALL_ROOT=/opt/luxe ENV_FILE=/opt/luxe/shared/.env \
#     bash /opt/luxe/current/infrastructure/backups/nightly_backup.sh
#   (nightly_backup.sh = backup → off-site copy → verify; reads the .env
#    safely, never with ". .env" — see infrastructure/scripts/env-file.sh)
#     >> /opt/luxe/logs/backup.log 2>&1
#
# The `&&` chain is deliberate: if the dump fails we do NOT upload a stale
# archive; if upload fails we still verify what's on disk; a verify failure
# writes a loud line to the log that Uptime Kuma watches.
# =============================================================================
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: run this as root (or via sudo)." >&2
  exit 1
fi

INSTALL_ROOT="${INSTALL_ROOT:-/opt/luxe}"
DEPLOY_USER="${DEPLOY_USER:-luxe}"
ENV_FILE="${ENV_FILE:-$INSTALL_ROOT/shared/.env}"
CRON_FILE="/etc/cron.d/luxe-backup"
LOG_DIR="$INSTALL_ROOT/logs"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Create it from infrastructure/environments/production.env.example first." >&2
  exit 1
fi

# Default schedule if the env file does not pin one. 02:30 UTC = ~03:30 Algiers.
# (|| true: no such line is normal — grep's "no match" must not stop the script.)
schedule=$(grep -E '^BACKUP_CRON_SCHEDULE=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
[ -n "$schedule" ] || schedule='30 2 * * *'

mkdir -p "$LOG_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$LOG_DIR"

cat > "$CRON_FILE" <<CRON
# Mus Luxury nightly backup chain — written by install_backup_cron.sh.
# Editing this file by hand is discouraged: re-running the installer
# overwrites it. The chain respects the env file in /opt/luxe/shared/.env.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
$schedule $DEPLOY_USER INSTALL_ROOT=$INSTALL_ROOT ENV_FILE=$ENV_FILE bash $INSTALL_ROOT/current/infrastructure/backups/nightly_backup.sh >> $LOG_DIR/backup.log 2>&1
CRON
chmod 0644 "$CRON_FILE"
chown root:root "$CRON_FILE"

echo "Installed $CRON_FILE with schedule: $schedule"
echo "Log destination: $LOG_DIR/backup.log"
echo
echo "Next cron tick will fire the dump + off-site upload + verify chain."
echo "Tail the log to confirm the first run:  tail -f $LOG_DIR/backup.log"
