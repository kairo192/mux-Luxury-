#!/usr/bin/env bash
set -euo pipefail
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
UPLOAD_DIR="${UPLOAD_DIR:-/var/lib/luxe/uploads}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
mkdir -p "$BACKUP_DIR" "$UPLOAD_DIR"

DB_ARCHIVE="$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz"
MEDIA_ARCHIVE="$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz"
SHA_FILE="$BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"

echo "[1/4] Dumping database (PostgreSQL 16 or SQLite WAL)..."
if [ -n "${DATABASE_URL:-}" ] && command -v pg_dump >/dev/null 2>&1; then
  pg_dump "${DATABASE_URL}" | gzip > "$DB_ARCHIVE"
else
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  python3 -c '
import gzip, sqlite3, sys
src_db, out_gz = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(src_db)
sql = "\n".join(conn.iterdump())
conn.close()
with open(out_gz, "wb") as f:
    f.write(gzip.compress(sql.encode("utf-8")))
' "$SQLITE_FILE" "$DB_ARCHIVE"
fi

echo "[2/4] Archiving product images and media..."
tar --force-local -czf "$MEDIA_ARCHIVE" -C "$UPLOAD_DIR" .

if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ] && [[ "${BACKUP_ENCRYPTION_KEY}" != \<CHANGE_ME* ]] && [[ "${BACKUP_ENCRYPTION_KEY}" != CHANGE_ME* ]]; then
  echo "[3/4] Encrypting archives with AES-256-CBC (PBKDF2)..."
  openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -in "$DB_ARCHIVE" -out "${DB_ARCHIVE}.enc"
  rm -f "$DB_ARCHIVE"
  DB_ARCHIVE="${DB_ARCHIVE}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -in "$MEDIA_ARCHIVE" -out "${MEDIA_ARCHIVE}.enc"
  rm -f "$MEDIA_ARCHIVE"
  MEDIA_ARCHIVE="${MEDIA_ARCHIVE}.enc"
else
  echo "[3/4] Computing integrity checksums..."
fi

(cd "$BACKUP_DIR" && sha256sum "$(basename "$DB_ARCHIVE")" "$(basename "$MEDIA_ARCHIVE")" > "$(basename "$SHA_FILE")")

echo "[4/4] Pruning backup archives older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "luxe_db_*.sql.gz*" -o -name "luxe_media_*.tar.gz*" -o -name "luxe_backup_*.sha256" \) -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true

echo "Backup completed and verified: $SHA_FILE"
