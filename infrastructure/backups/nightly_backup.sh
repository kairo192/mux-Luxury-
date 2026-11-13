#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — the nightly backup chain, run by cron from the current release:
#   backup (database + photos, encrypted) → off-site copy → verification.
# The production .env is read with env-file.sh (values taken literally): a
# password with ? # & ; $ or a <FILL_IN_…> placeholder must never stop backups.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/../.."
ENV_FILE="${ENV_FILE:-${INSTALL_ROOT:-/opt/luxe}/shared/.env}"
# shellcheck source=../scripts/env-file.sh
source infrastructure/scripts/env-file.sh
if [ -f "$ENV_FILE" ]; then luxe_load_env "$ENV_FILE"; fi
export BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
bash infrastructure/backups/backup_postgres_and_media.sh
bash infrastructure/backups/upload_to_offsite.sh
bash infrastructure/backups/verify_backup.sh
# Reached only when every step above succeeded (set -e): the line to monitor.
echo "[nightly-backup] OK — backup, off-site copy and verification done"
if [ -n "${BACKUP_HEARTBEAT_URL:-}" ]; then
  curl -fsS --max-time 10 "$BACKUP_HEARTBEAT_URL" >/dev/null || echo "[nightly-backup] heartbeat not delivered" >&2
fi
