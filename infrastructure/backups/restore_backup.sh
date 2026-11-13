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

case "$(basename "$BACKUP_FILE")" in
  luxe_app_*)
    # Portable snapshot (CMS format): restored by the application itself,
    # which takes a safety backup first and works on PostgreSQL and SQLite.
    NAME="$(basename "$BACKUP_FILE")"
    if command -v docker >/dev/null 2>&1 && [ "$(docker inspect -f '{{.State.Running}}' "${API_CONTAINER:-luxe_api}" 2>/dev/null || true)" = "true" ]; then
      docker cp "$BACKUP_FILE" "${API_CONTAINER:-luxe_api}:/var/lib/luxe/backups/$NAME"
      [ -f "$BACKUP_FILE.meta.json" ] && docker cp "$BACKUP_FILE.meta.json" "${API_CONTAINER:-luxe_api}:/var/lib/luxe/backups/$NAME.meta.json"
      exec docker exec "${API_CONTAINER:-luxe_api}" python -m app.backup_cli restore "$NAME" --yes
    fi
    echo "ERROR: $NAME is a CMS snapshot: restore it from the CMS (Sauvegardes & Sécurité)" >&2
    echo "       or with: cd backend && python -m app.backup_cli restore $NAME --yes" >&2
    exit 1
    ;;
esac

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
PG_CONTAINER="${PG_CONTAINER:-luxe_postgres}"
API_CONTAINER="${API_CONTAINER:-luxe_api}"
container_running() {
  command -v docker >/dev/null 2>&1 &&
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]
}

if container_running "$PG_CONTAINER"; then
  # VPS: the database is inside Docker. Pause the API so nobody writes during
  # the restore, replay the dump in ONE transaction, then start the API again.
  # Dumps made by backup_postgres_and_media.sh use --clean --if-exists, so
  # they replace the existing tables.
  API_WAS_RUNNING=0
  if container_running "$API_CONTAINER"; then
    API_WAS_RUNNING=1
    echo "      stopping $API_CONTAINER during the restore..."
    docker stop "$API_CONTAINER" >/dev/null
  fi
  set +e
  gunzip -c "$WORK_GZ" | docker exec -i "$PG_CONTAINER" sh -c \
    'psql -q -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
  RC=$?
  set -e
  if [ "$API_WAS_RUNNING" = "1" ]; then
    docker start "$API_CONTAINER" >/dev/null
    echo "      $API_CONTAINER started again."
  fi
  if [ "$RC" -ne 0 ]; then
    echo "ERROR: restore failed — the transaction was rolled back, the database is unchanged." >&2
    exit "$RC"
  fi
elif [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1 && [[ "${DATABASE_URL}" != *"@db:"* ]]; then
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
