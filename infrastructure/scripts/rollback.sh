#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — on-VPS rollback.
#
# Flips the `current` symlink to the previous release (or a named one) and
# brings its docker-compose stack back up. Does NOT touch the database —
# rolling the schema back is explicitly out of scope (see docs/cicd/ROLLBACK.md).
#
# Usage:
#   rollback.sh                   # roll back to the next-most-recent release
#   rollback.sh --to 2026.11.08-abc1234
# =============================================================================
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/luxe}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/v1/health}"
HEALTH_TIMEOUT_SEC="${HEALTH_TIMEOUT_SEC:-90}"
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --to)      TARGET="$2"; shift 2 ;;
    --install) INSTALL_ROOT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

RELEASES_DIR="$INSTALL_ROOT/releases"
CURRENT_LINK="$INSTALL_ROOT/current"
LOGS_DIR="$INSTALL_ROOT/logs"
mkdir -p "$LOGS_DIR"
exec > >(tee -a "$LOGS_DIR/rollback.log") 2>&1

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

[ -L "$CURRENT_LINK" ] || { log "no current symlink — nothing to roll back"; exit 1; }
CURRENT_RELEASE="$(readlink -f "$CURRENT_LINK")"
CURRENT_NAME="$(basename "$CURRENT_RELEASE")"

if [ -z "$TARGET" ]; then
  # Pick the newest release other than the current one.
  TARGET=$(ls -1dt "$RELEASES_DIR"/* 2>/dev/null \
            | while IFS= read -r r; do
                if [ "$(basename "$r")" != "$CURRENT_NAME" ]; then
                  basename "$r"; break
                fi
              done)
fi

[ -n "$TARGET" ] || { log "no target release found"; exit 1; }
TARGET_DIR="$RELEASES_DIR/$TARGET"
[ -d "$TARGET_DIR" ] || { log "target $TARGET_DIR does not exist"; exit 1; }

log "rolling back: $CURRENT_NAME -> $TARGET"
ln -snf "$TARGET_DIR" "${CURRENT_LINK}.new"
mv -Tf  "${CURRENT_LINK}.new" "$CURRENT_LINK"
(cd "$CURRENT_LINK" && docker compose up -d --remove-orphans)

DEADLINE=$(( $(date +%s) + HEALTH_TIMEOUT_SEC ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    log "rollback OK — now on $TARGET"
    exit 0
  fi
  sleep 3
done
log "rollback UNHEALTHY — manual intervention required"
exit 1
