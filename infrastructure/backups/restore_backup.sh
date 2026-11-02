#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-luxe_db_backup.sql.gz> [optional-sha256-file]"
  exit 1
fi
BACKUP_FILE="$1"
SHA_FILE="${2:-}"
if [ -n "$SHA_FILE" ] && [ -f "$SHA_FILE" ]; then
  echo "[1/3] Verifying SHA-256 cryptographic checksum..."
  sha256sum -c "$SHA_FILE"
fi
echo "[2/3] Verifying gzip archive integrity..."
gzip -t "$BACKUP_FILE"

echo "[3/3] Restoring database..."
if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
  gunzip -c "$BACKUP_FILE" | psql "${DATABASE_URL}"
else
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  python3 -c "import sqlite3, gzip; sql = gzip.open('$BACKUP_FILE', 'rt', encoding='utf-8').read(); conn = sqlite3.connect('$SQLITE_FILE'); conn.executescript(sql); conn.commit(); conn.close()"
fi
echo "Restore completed successfully."
