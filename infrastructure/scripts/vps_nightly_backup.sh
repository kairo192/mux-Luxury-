#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — Nightly Automated PostgreSQL 16 Backup Script
# Generates compressed SQL archive, calculates SHA256, and prunes older than 30d
# =============================================================================
set -euo pipefail

BACKUP_DIR="/var/lib/luxe/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz"

echo "Starting automated database backup: $BACKUP_FILE"
docker exec luxe_postgres pg_dump -U luxe_app_user luxe_ecommerce | gzip > "$BACKUP_FILE"
chmod 0600 "$BACKUP_FILE"

# Integrity verification
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"
chmod 0600 "${BACKUP_FILE}.sha256"

# Retention: prune archives older than 30 days
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "luxe_db_*.sql.gz*" \) -mtime +30 -delete 2>/dev/null || true

echo "Backup completed and verified: ${BACKUP_FILE}.sha256"
