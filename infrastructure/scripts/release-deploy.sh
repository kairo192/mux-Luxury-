#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — on-VPS release deployer.
# Invoked over SSH by cd-staging.yml / cd-production.yml. Receives the release
# tarball on stdin or at a path, the version string, and does the rest.
#
# Guarantees:
#   - Refuses to deploy if disk or memory are below safe thresholds.
#   - Takes an encrypted backup BEFORE running migrations.
#   - Applies forward-only migrations under a Postgres advisory lock.
#   - Atomic release swap via symlink (new release is prepared beside the old
#     one, then the `current` symlink is pointed at it).
#   - Health-checks after swap; on failure, flips the symlink back to the
#     previous release and reports a non-zero exit code.
#   - Preserves the last N releases (default 5) for fast rollback.
#
# Usage, from the deploy user:
#   release-deploy.sh --version 2026.11.09-abc1234 --archive /tmp/release.tar.gz
#
# Env vars read:
#   INSTALL_ROOT          default /opt/luxe
#   MIN_FREE_DISK_MB      default 2048
#   MIN_FREE_MEM_MB       default 300
#   KEEP_RELEASES         default 5
#   HEALTH_URL            default http://127.0.0.1/api/v1/health
#   HEALTH_TIMEOUT_SEC    default 120
# =============================================================================
set -euo pipefail

VERSION=""
ARCHIVE=""
INSTALL_ROOT="${INSTALL_ROOT:-/opt/luxe}"
MIN_FREE_DISK_MB="${MIN_FREE_DISK_MB:-2048}"
MIN_FREE_MEM_MB="${MIN_FREE_MEM_MB:-300}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/v1/health}"
HEALTH_TIMEOUT_SEC="${HEALTH_TIMEOUT_SEC:-120}"

log()  { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { log "FATAL: $*"; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --version)  VERSION="$2";  shift 2 ;;
    --archive)  ARCHIVE="$2";  shift 2 ;;
    --install)  INSTALL_ROOT="$2"; shift 2 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[ -n "$VERSION" ]  || fail "--version required"
[ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ] || fail "--archive must exist"
[ -d "$INSTALL_ROOT" ] || fail "install root $INSTALL_ROOT missing — run vps-bootstrap.sh"
[ -f "$INSTALL_ROOT/shared/.env" ] || fail "$INSTALL_ROOT/shared/.env missing"

RELEASES_DIR="$INSTALL_ROOT/releases"
SHARED_DIR="$INSTALL_ROOT/shared"
LOGS_DIR="$INSTALL_ROOT/logs"
CURRENT_LINK="$INSTALL_ROOT/current"
NEW_RELEASE="$RELEASES_DIR/$VERSION"
PREVIOUS_RELEASE=""
if [ -L "$CURRENT_LINK" ]; then
  PREVIOUS_RELEASE="$(readlink -f "$CURRENT_LINK")"
fi

mkdir -p "$RELEASES_DIR" "$LOGS_DIR"
exec > >(tee -a "$LOGS_DIR/deploy.log") 2>&1

# -------------------------------------------------- 1. Preflight
log "== preflight =="
FREE_DISK_MB=$(df -Pm "$INSTALL_ROOT" | awk 'NR==2 {print $4}')
if [ "$FREE_DISK_MB" -lt "$MIN_FREE_DISK_MB" ]; then
  fail "only ${FREE_DISK_MB}MB free on $INSTALL_ROOT (need ${MIN_FREE_DISK_MB}MB)"
fi
log "disk free: ${FREE_DISK_MB}MB (ok)"

FREE_MEM_MB=$(awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo)
if [ "$FREE_MEM_MB" -lt "$MIN_FREE_MEM_MB" ]; then
  fail "only ${FREE_MEM_MB}MB RAM available (need ${MIN_FREE_MEM_MB}MB)"
fi
log "mem available: ${FREE_MEM_MB}MB (ok)"

docker info >/dev/null 2>&1 || fail "docker daemon not responding"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin not installed"

if [ -d "$NEW_RELEASE" ]; then
  log "WARNING: $NEW_RELEASE already exists; removing before extraction"
  rm -rf "$NEW_RELEASE"
fi

# -------------------------------------------------- 2. Extract release
log "== extracting release =="
mkdir -p "$NEW_RELEASE"
tar -xzf "$ARCHIVE" -C "$NEW_RELEASE"
echo "$VERSION" > "$NEW_RELEASE/.release-version"
ln -snf "$SHARED_DIR/.env" "$NEW_RELEASE/.env"
if [ -d "$SHARED_DIR/nginx-ssl" ]; then
  rm -rf "$NEW_RELEASE/infrastructure/nginx/ssl"
  ln -snf "$SHARED_DIR/nginx-ssl" "$NEW_RELEASE/infrastructure/nginx/ssl"
fi

# -------------------------------------------------- 3. Pre-migration backup
log "== pre-migration backup =="
# Read as Docker reads it (values taken literally, never run as shell code:
# passwords may hold ? # & ; $ and unused services keep <FILL_IN_…>).
# shellcheck source=env-file.sh
source "$NEW_RELEASE/infrastructure/scripts/env-file.sh"
luxe_load_env "$SHARED_DIR/.env" || fail "cannot read $SHARED_DIR/.env"
# Every setting production needs must be there before anything changes
# (backend/app/settings.py; values are never printed).
if command -v python3 >/dev/null 2>&1; then
  (cd "$NEW_RELEASE/backend" && python3 -m app.settings check "$SHARED_DIR/.env") \
    || fail "required settings missing in $SHARED_DIR/.env (see above) — nothing was changed"
fi
# One Compose project for every release (else: second database container and
# an empty database volume) — see compose-project.sh.
# shellcheck source=compose-project.sh
source "$NEW_RELEASE/infrastructure/scripts/compose-project.sh"
luxe_ensure_compose_project "$SHARED_DIR/.env"
log "compose project: $COMPOSE_PROJECT_NAME"
luxe_check_db_volume || fail "database volume check failed — nothing was changed"
# Back up the data of the CURRENTLY RUNNING shop (it lives in the Docker
# containers, not in the release folder). The backup SCRIPT is taken from the
# NEW release so backup fixes apply from this deploy on.
if [ -L "$CURRENT_LINK" ] && [ -d "$CURRENT_LINK" ]; then
  (cd "$NEW_RELEASE" && BACKUP_DIR=/var/lib/luxe/backups UPLOAD_DIR=/var/lib/luxe/uploads \
      bash infrastructure/backups/backup_postgres_and_media.sh) \
      || fail "pre-migration backup failed — aborting deploy"
else
  log "first deploy — no previous release to back up yet"
fi

# -------------------------------------------------- 4. Build new images (does not disturb running containers)
log "== building images for $VERSION =="
(cd "$NEW_RELEASE" && docker compose build --pull) || fail "docker compose build failed"

# -------------------------------------------------- 5. Migrate
log "== running migrations =="
(cd "$NEW_RELEASE" && docker compose run --rm --entrypoint "" api \
    python -m app.migration_runner up) \
    || { log "migration FAILED — new release not activated"; exit 1; }

# -------------------------------------------------- 6. Atomic swap
log "== swapping symlink =="
ln -snf "$NEW_RELEASE" "${CURRENT_LINK}.new"
mv -Tf  "${CURRENT_LINK}.new" "$CURRENT_LINK"

# -------------------------------------------------- 7. Start new stack (compose takes it from here)
log "== starting new stack =="
(cd "$CURRENT_LINK" && docker compose up -d --remove-orphans)

# -------------------------------------------------- 8. Health check
log "== health check =="
HEALTH_OK=0
DEADLINE=$(( $(date +%s) + HEALTH_TIMEOUT_SEC ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    HEALTH_OK=1; break
  fi
  sleep 3
done

if [ "$HEALTH_OK" -ne 1 ]; then
  log "HEALTH CHECK FAILED — rolling back to previous release"
  if [ -n "$PREVIOUS_RELEASE" ] && [ -d "$PREVIOUS_RELEASE" ]; then
    ln -snf "$PREVIOUS_RELEASE" "${CURRENT_LINK}.new"
    mv -Tf  "${CURRENT_LINK}.new" "$CURRENT_LINK"
    # --build: the images of the release that just failed carry the same
    # names; rebuild the previous release's code (layers are cached).
    (cd "$CURRENT_LINK" && docker compose up -d --build --remove-orphans) || true
    log "rolled back to $PREVIOUS_RELEASE"
  else
    log "no previous release to roll back to — manual intervention needed"
  fi
  exit 1
fi
log "health check OK"

# -------------------------------------------------- 9. Prune old releases
log "== pruning old releases (keep $KEEP_RELEASES) =="
# shellcheck disable=SC2012
ls -1dt "$RELEASES_DIR"/* 2>/dev/null \
  | tail -n +$((KEEP_RELEASES + 1)) \
  | while IFS= read -r old; do
      if [ "$old" != "$(readlink -f "$CURRENT_LINK")" ]; then
        rm -rf "$old"
        log "pruned $old"
      fi
    done

# -------------------------------------------------- 10. Free disk (40 GB server)
# Images replaced by this build and build cache older than a week. Images in
# use and the database/photo volumes are never touched.
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f --filter until=168h >/dev/null 2>&1 || true
log "old images and build cache removed"

log "== deploy SUCCESS: $VERSION =="
