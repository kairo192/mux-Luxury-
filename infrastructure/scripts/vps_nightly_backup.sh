#!/usr/bin/env bash
# Kept for compatibility: the nightly backup is now ONE script,
# infrastructure/backups/backup_postgres_and_media.sh (PostgreSQL dump through
# Docker + photos + CMS-restorable snapshot + encryption + checksums).
# It is scheduled by vps-bootstrap.sh / install_backup_cron.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec bash infrastructure/backups/backup_postgres_and_media.sh "$@"
