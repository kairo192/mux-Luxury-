#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-luxe_db_backup.sql.gz[.enc]> [optional-sha256-file] [--force]"
  exit 1
fi
BACKUP_FILE="$1"
SHA_FILE=""
FORCE_OVERWRITE="${FORCE_OVERWRITE:-0}"

for arg in "${@:2}"; do
  if [ "$arg" = "--force" ]; then
    FORCE_OVERWRITE=1
  elif [ -z "$SHA_FILE" ]; then
    SHA_FILE="$arg"
  fi
done

if [ -n "$SHA_FILE" ] && [ -f "$SHA_FILE" ]; then
  echo "[1/3] Verifying SHA-256 cryptographic checksum..."
  (cd "$(dirname "$SHA_FILE")" && sha256sum -c "$(basename "$SHA_FILE")")
fi

WORK_GZ="$BACKUP_FILE"
CLEANUP_TMP_GZ=""
if [[ "$BACKUP_FILE" == *.enc ]]; then
  if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: Encrypted backup (.enc) requires BACKUP_ENCRYPTION_KEY environment variable."
    exit 1
  fi
  CLEANUP_TMP_GZ="$(mktemp --suffix=.sql.gz)"
  trap 'rm -f "$CLEANUP_TMP_GZ"' EXIT
  openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -in "$BACKUP_FILE" -out "$CLEANUP_TMP_GZ"
  WORK_GZ="$CLEANUP_TMP_GZ"
fi

echo "[2/3] Verifying gzip archive integrity..."
gzip -t "$WORK_GZ"

echo "[3/3] Restoring database atomically (all-or-nothing transaction)..."
if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
  gunzip -c "$WORK_GZ" | psql -v ON_ERROR_STOP=1 --single-transaction "${DATABASE_URL}"
else
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  if [ -f "$SQLITE_FILE" ] && [ "$FORCE_OVERWRITE" != "1" ]; then
    echo "ERROR: Target SQLite database '$SQLITE_FILE' already exists. Pass --force (or FORCE_OVERWRITE=1) to move it aside (.pre-restore-<ts>) and restore."
    exit 1
  fi
  TMP_RESTORE="${SQLITE_FILE}.restore_tmp"
  rm -f "$TMP_RESTORE"
  python3 -c '
import gzip, sqlite3, sys
gz_path, tmp_db = sys.argv[1], sys.argv[2]
with gzip.open(gz_path, "rt", encoding="utf-8") as f:
    sql = f.read()
conn = sqlite3.connect(tmp_db)
conn.executescript(sql)
conn.execute("SELECT COUNT(*) FROM roles").fetchone()
conn.commit()
conn.close()
' "$WORK_GZ" "$TMP_RESTORE"
  if [ -f "$SQLITE_FILE" ]; then
    PRESERVE_PATH="${SQLITE_FILE}.pre-restore-$(date +%Y%m%d_%H%M%S)"
    mv "$SQLITE_FILE" "$PRESERVE_PATH"
    echo "Existing database preserved at: $PRESERVE_PATH"
  fi
  mv "$TMP_RESTORE" "$SQLITE_FILE"
fi
echo "Atomic restore completed and verified successfully."
