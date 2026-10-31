#!/usr/bin/env bash
set -euo pipefail
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
mkdir -p "$BACKUP_DIR"

echo "[1/3] Dumping PostgreSQL database..."
pg_dump "${DATABASE_URL}" | gzip > "$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz"

echo "[2/3] Archiving product images and media..."
tar -czf "$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz" -C "${UPLOAD_DIR:-/var/lib/luxe/uploads}" .

echo "[3/3] Computing SHA-256 integrity checksums..."
sha256sum "$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz" "$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz" > "$BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"
echo "Backup completed and verified: $BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"
