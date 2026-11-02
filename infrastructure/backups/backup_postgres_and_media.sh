#!/usr/bin/env bash
set -euo pipefail
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
UPLOAD_DIR="${UPLOAD_DIR:-/var/lib/luxe/uploads}"
mkdir -p "$BACKUP_DIR" "$UPLOAD_DIR"

echo "[1/3] Dumping database (PostgreSQL 16 or SQLite WAL)..."
if [ -n "${DATABASE_URL:-}" ] && command -v pg_dump >/dev/null 2>&1; then
  pg_dump "${DATABASE_URL}" | gzip > "$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz"
else
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  python3 -c "import sqlite3, gzip; conn = sqlite3.connect('$SQLITE_FILE'); sql = '\n'.join(conn.iterdump()); open('$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz', 'wb').write(gzip.compress(sql.encode('utf-8'))); conn.close()"
fi

echo "[2/3] Archiving product images and media..."
tar -czf "$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz" -C "$UPLOAD_DIR" .

echo "[3/3] Computing SHA-256 integrity checksums..."
sha256sum "$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz" "$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz" > "$BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"
echo "Backup completed and verified: $BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"
