#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — nightly backup (database + product photos).
#
# Where it runs:
#   * VPS (production): from the host cron installed by install_backup_cron.sh.
#     The database lives in the Docker container `luxe_postgres` and the photos
#     in the `luxe_api` container, so this script reaches them THROUGH DOCKER
#     (`docker exec`). It does not need pg_dump on the host and it does not
#     need the database port to be exposed.
#   * A PC / dev box: falls back to the local SQLite file.
#
# What it produces in $BACKUP_DIR (default /var/lib/luxe/backups):
#   luxe_db_<ts>.sql.gz[.enc]       native PostgreSQL dump (or SQLite SQL dump)
#   luxe_media_<ts>.tar.gz[.enc]    product photos / uploads
#   luxe_app_nightly_<ts>.json.gz.enc  portable snapshot, restorable in one
#                                   click from the CMS (VPS only)
#   luxe_backup_<ts>.sha256         checksums of the files above
#   last_backup_status.json         result of this run (read by monitoring)
#
# Safety: it REFUSES to write a backup when it cannot find a real database
# (the old version silently produced an empty SQLite dump on the VPS).
# =============================================================================
set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
UPLOAD_DIR="${UPLOAD_DIR:-/var/lib/luxe/uploads}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
# Photos: a new archive only when they changed; keep the newest few (never
# pruned by age — unchanged photos keep their last archive however old).
MEDIA_KEEP="${BACKUP_MEDIA_KEEP:-3}"
# Disk guard for a small VPS (40 GB): below this % of free space the photo
# archive is skipped; below half of it, database dumps older than 7 days go.
MIN_FREE_PCT="${BACKUP_MIN_FREE_PCT:-15}"
MEDIA_MANIFEST_FILE="$BACKUP_DIR/.media_manifest"
PG_CONTAINER="${PG_CONTAINER:-luxe_postgres}"
API_CONTAINER="${API_CONTAINER:-luxe_api}"
mkdir -p "$BACKUP_DIR"
umask 077

DB_ARCHIVE="$BACKUP_DIR/luxe_db_${TIMESTAMP}.sql.gz"
MEDIA_ARCHIVE="$BACKUP_DIR/luxe_media_${TIMESTAMP}.tar.gz"
SHA_FILE="$BACKUP_DIR/luxe_backup_${TIMESTAMP}.sha256"
STATUS_FILE="$BACKUP_DIR/last_backup_status.json"
APP_SNAPSHOT=""
WARNINGS=()

container_running() {
  command -v docker >/dev/null 2>&1 &&
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]
}

fail() {
  echo "ERROR: $*" >&2
  printf '{"timestamp":"%s","ok":false,"error":"%s"}\n' "$TIMESTAMP" "${*//\"/\'}" > "$STATUS_FILE" 2>/dev/null || true
  rm -f "$DB_ARCHIVE" "$MEDIA_ARCHIVE"
  exit 1
}

# ------------------------------------------------------------- 1. database --
echo "[1/5] Dumping the database..."
if container_running "$PG_CONTAINER"; then
  MODE="docker-postgres"
  docker exec "$PG_CONTAINER" sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
    | gzip > "$DB_ARCHIVE" || fail "pg_dump through docker failed"
elif [ -n "${DATABASE_URL:-}" ] && command -v pg_dump >/dev/null 2>&1 && [[ "${DATABASE_URL}" != *"@db:"* ]]; then
  MODE="postgres"
  pg_dump "${DATABASE_URL}" --clean --if-exists --no-owner --no-privileges | gzip > "$DB_ARCHIVE" \
    || fail "pg_dump failed"
else
  MODE="sqlite"
  SQLITE_FILE="${LUXE_SQLITE_PATH:-./backend/luxe_store.sqlite3}"
  [ -f "$SQLITE_FILE" ] || fail "no database found (container $PG_CONTAINER not running and $SQLITE_FILE does not exist) — refusing to write an empty backup"
  python3 -c '
import gzip, sqlite3, sys
src_db, out_gz = sys.argv[1], sys.argv[2]
# Copy through the online-backup API first: a consistent snapshot even while
# the shop keeps writing (WAL mode).
src = sqlite3.connect(src_db)
snap = sqlite3.connect(":memory:")
src.backup(snap)
src.close()
sql = "\n".join(snap.iterdump())
snap.close()
with open(out_gz, "wb") as f:
    f.write(gzip.compress(sql.encode("utf-8")))
' "$SQLITE_FILE" "$DB_ARCHIVE" || fail "SQLite dump failed"
fi

# A real store dump always contains table definitions. `grep -c` reads the
# whole stream (no SIGPIPE under pipefail).
TABLES_IN_DUMP=$(gunzip -c "$DB_ARCHIVE" | grep -c "CREATE TABLE" || true)
[ "${TABLES_IN_DUMP:-0}" -ge 1 ] || fail "the dump contains no table — database empty or unreachable"
echo "      mode=$MODE, tables=$TABLES_IN_DUMP, size=$(du -h "$DB_ARCHIVE" | cut -f1)"

# --------------------------------------------------------------- 2. photos --
free_pct() { df -P "$BACKUP_DIR" | awk 'NR==2 { gsub("%", "", $5); print 100 - $5 }'; }
media_manifest() {
  # List of photo files with size and date: changes when a photo is added,
  # replaced or removed.
  {
    if container_running "$API_CONTAINER"; then
      docker exec "$API_CONTAINER" sh -c 'cd /var/lib/luxe/uploads 2>/dev/null && find . -type f -printf "%P %s %T@\n" | sort' || true
    else
      (cd "$UPLOAD_DIR" 2>/dev/null && find . -type f -printf "%P %s %T@\n" | sort) || true
    fi
  } | sha256sum | cut -d" " -f1
}
FREE=$(free_pct)
echo "[2/5] Product photos (free disk space: ${FREE}%)..."
NEW_MANIFEST=$(media_manifest)
LAST_MEDIA=$(ls -1t "$BACKUP_DIR"/luxe_media_*.tar.gz* 2>/dev/null | head -n 1 || true)
if [ "${FREE:-100}" -lt "$MIN_FREE_PCT" ]; then
  MEDIA_ARCHIVE=""
  WARNINGS+=("low disk space (${FREE}% free): photo archive skipped — free space on the server")
  echo "      skipped: only ${FREE}% free"
elif [ -n "$LAST_MEDIA" ] && [ -f "$MEDIA_MANIFEST_FILE" ] && [ "$(cat "$MEDIA_MANIFEST_FILE")" = "$NEW_MANIFEST" ]; then
  MEDIA_ARCHIVE=""
  echo "      unchanged since $(basename "$LAST_MEDIA") — no new archive"
else
  mkdir -p "$UPLOAD_DIR"
  if container_running "$API_CONTAINER"; then
    docker exec "$API_CONTAINER" tar -czf - -C /var/lib/luxe/uploads . > "$MEDIA_ARCHIVE" \
      || fail "could not archive uploads from $API_CONTAINER"
  else
    tar --force-local -czf "$MEDIA_ARCHIVE" -C "$UPLOAD_DIR" . || fail "could not archive $UPLOAD_DIR"
  fi
  printf '%s' "$NEW_MANIFEST" > "$MEDIA_MANIFEST_FILE"
  echo "      archived, size=$(du -h "$MEDIA_ARCHIVE" | cut -f1)"
fi

# ------------------------------------------- 3. CMS-restorable app snapshot --
if container_running "$API_CONTAINER"; then
  echo "[3/5] Taking the portable snapshot (restorable from the CMS)..."
  if OUT=$(docker exec "$API_CONTAINER" python -m app.backup_cli create --kind nightly 2>&1); then
    NAME=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))' 2>/dev/null || true)
    if [ -n "$NAME" ] && docker cp "$API_CONTAINER:/var/lib/luxe/backups/$NAME" "$BACKUP_DIR/$NAME" 2>/dev/null; then
      docker cp "$API_CONTAINER:/var/lib/luxe/backups/$NAME.meta.json" "$BACKUP_DIR/$NAME.meta.json" 2>/dev/null || true
      APP_SNAPSHOT="$NAME"
    else
      WARNINGS+=("app snapshot created in the container but not copied to the host")
    fi
  else
    WARNINGS+=("app snapshot failed: $(printf '%s' "$OUT" | tail -c 300)")
  fi
else
  echo "[3/5] Portable snapshot: skipped (no $API_CONTAINER container on this machine)."
fi

# ----------------------------------------------------------- 4. encryption --
KEY="${BACKUP_ENCRYPTION_KEY:-}"
if [ -n "$KEY" ] && [[ "$KEY" != \<CHANGE_ME* ]] && [[ "$KEY" != CHANGE_ME* ]] && [[ "$KEY" != your* ]]; then
  echo "[4/5] Encrypting with AES-256-CBC (PBKDF2)..."
  openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -in "$DB_ARCHIVE" -out "${DB_ARCHIVE}.enc"
  rm -f "$DB_ARCHIVE"
  DB_ARCHIVE="${DB_ARCHIVE}.enc"
  if [ -n "$MEDIA_ARCHIVE" ]; then
    openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -in "$MEDIA_ARCHIVE" -out "${MEDIA_ARCHIVE}.enc"
    rm -f "$MEDIA_ARCHIVE"
    MEDIA_ARCHIVE="${MEDIA_ARCHIVE}.enc"
  fi
else
  echo "[4/5] WARNING: BACKUP_ENCRYPTION_KEY not set — archives are NOT encrypted."
  WARNINGS+=("archives not encrypted (BACKUP_ENCRYPTION_KEY missing)")
fi

FILES=("$(basename "$DB_ARCHIVE")")
if [ -n "$MEDIA_ARCHIVE" ]; then
  FILES+=("$(basename "$MEDIA_ARCHIVE")")
elif [ -n "$LAST_MEDIA" ] && [ -f "$LAST_MEDIA" ]; then
  # Photos unchanged (or skipped): list the archive that still covers them, so
  # the off-site copy picks it up if an earlier upload of it failed.
  FILES+=("$(basename "$LAST_MEDIA")")
fi
[ -n "$APP_SNAPSHOT" ] && FILES+=("$APP_SNAPSHOT")
(cd "$BACKUP_DIR" && sha256sum "${FILES[@]}" > "$(basename "$SHA_FILE")")

# --------------------------------------------------------------- 5. prune --
echo "[5/5] Removing old archives (database ${RETENTION_DAYS} days, newest ${MEDIA_KEEP} photo archives)..."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "luxe_db_*.sql.gz*" \
  -o -name "luxe_backup_*.sha256" -o -name "luxe_app_*.json.gz*" \) -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
ls -1t "$BACKUP_DIR"/luxe_media_*.tar.gz* 2>/dev/null | tail -n "+$((MEDIA_KEEP + 1))" | xargs -r rm -f
FREE=$(free_pct)
if [ "${FREE:-100}" -lt $((MIN_FREE_PCT / 2)) ]; then
  # Emergency: keep the server running — older database dumps go first
  # (copies stay on the owner's PC and off-site).
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "luxe_db_*.sql.gz*" -o -name "luxe_app_*.json.gz*" \) -mtime +7 -delete 2>/dev/null || true
  WARNINGS+=("disk almost full (${FREE}% free): backups older than 7 days removed from the server")
fi

WARN_JSON=$(printf '%s\n' "${WARNINGS[@]+"${WARNINGS[@]}"}" | python3 -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))' 2>/dev/null || echo '[]')
MEDIA_NAME=$([ -n "$MEDIA_ARCHIVE" ] && basename "$MEDIA_ARCHIVE" || basename "${LAST_MEDIA:-}")
printf '{"timestamp":"%s","ok":true,"mode":"%s","database":"%s","media":"%s","app_snapshot":"%s","disk_free_pct":%s,"warnings":%s}\n' \
  "$TIMESTAMP" "$MODE" "$(basename "$DB_ARCHIVE")" "$MEDIA_NAME" "$APP_SNAPSHOT" "${FREE:-null}" "$WARN_JSON" > "$STATUS_FILE"

for w in "${WARNINGS[@]+"${WARNINGS[@]}"}"; do echo "WARNING: $w"; done
echo "Backup completed and verified: $SHA_FILE"
