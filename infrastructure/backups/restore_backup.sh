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

echo "[3/3] Restoring database atomically (all-or-nothing transaction)..."
if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
  gunzip -c "$BACKUP_FILE" | psql --single-transaction -v ON_ERROR_STOP=1 "${DATABASE_URL}"
else
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  TMP_RESTORE="${SQLITE_FILE}.restore_tmp"
  rm -f "$TMP_RESTORE"
  python3 -c "import sqlite3, gzip; sql = gzip.open('$BACKUP_FILE', 'rt', encoding='utf-8').read(); conn = sqlite3.connect('$TMP_RESTORE'); conn.executescript(sql); conn.execute('SELECT COUNT(*) FROM products').fetchone(); conn.commit(); conn.close()"
  mv "$TMP_RESTORE" "$SQLITE_FILE"
fi
echo "Atomic restore completed and verified successfully."
