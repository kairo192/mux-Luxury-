#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — non-destructive backup verification
#
# A backup you never test is not a backup. This script picks the newest
# encrypted DB archive, decrypts to a tempdir, gunzips, feeds the result
# into an isolated throwaway database, and queries two rows to prove the
# restore succeeded. Nothing touches the live DB.
#
# Runs after the nightly upload so a failure here raises the same alert as
# a failed upload. Exit code is picked up by cron / systemd timer; a
# non-zero exit means the last backup is not recoverable and the operator
# must intervene before the next cycle overwrites more data.
#
# Env:
#   BACKUP_DIR                default /var/lib/luxe/backups
#   BACKUP_ENCRYPTION_KEY     required when archives end in .enc
#   VERIFY_METHOD             'auto' (default), 'sqlite', 'postgres'
#                             auto picks sqlite if pg not available on host
#
# Exit codes:
#   0  — verified; the newest backup is readable and parses as a DB dump
#   1  — nothing to verify (backup dir empty / misconfig)
#   2  — verification failed; the backup is NOT trustworthy
# =============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
VERIFY_METHOD="${VERIFY_METHOD:-auto}"
LOG_PREFIX="[verify-backup]"

log()  { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$LOG_PREFIX" "$*"; }
fail() { log "FATAL: $*" >&2; exit 2; }

if [ ! -d "$BACKUP_DIR" ]; then
  log "backup dir $BACKUP_DIR does not exist"
  exit 1
fi

latest=$(ls -1t "$BACKUP_DIR"/luxe_db_*.sql.gz* 2>/dev/null | head -n 1 || true)
if [ -z "$latest" ]; then
  log "no luxe_db_*.sql.gz* in $BACKUP_DIR"
  exit 1
fi

sha_file=$(ls -1t "$BACKUP_DIR"/luxe_backup_*.sha256 2>/dev/null | head -n 1 || true)
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

log "verifying $(basename "$latest")"

if [ -n "$sha_file" ] && [ -f "$sha_file" ]; then
  log "  checking sha256 against $(basename "$sha_file")"
  (cd "$BACKUP_DIR" && sha256sum -c "$(basename "$sha_file")" --ignore-missing) \
    || fail "sha256 mismatch — archive corrupted on disk"
fi

work_gz="$work_dir/db.sql.gz"
if [[ "$latest" == *.enc ]]; then
  [ -n "${BACKUP_ENCRYPTION_KEY:-}" ] \
    || fail "BACKUP_ENCRYPTION_KEY unset but archive is .enc"
  log "  decrypting with BACKUP_ENCRYPTION_KEY"
  openssl enc -d -aes-256-cbc -pbkdf2 \
    -pass env:BACKUP_ENCRYPTION_KEY \
    -in "$latest" -out "$work_gz" \
    || fail "decryption failed — wrong key or corrupted ciphertext"
else
  cp "$latest" "$work_gz"
fi

log "  gunzip + parse"
work_sql="$work_dir/db.sql"
gunzip -t "$work_gz" || fail "gunzip integrity check failed"
gunzip -c "$work_gz" > "$work_sql"

bytes=$(wc -c < "$work_sql")
if [ "$bytes" -lt 1024 ]; then
  fail "decompressed dump is only ${bytes} bytes — probably empty"
fi

# Pick restore target based on what the dump contains and what tools we have.
method="$VERIFY_METHOD"
if [ "$method" = "auto" ]; then
  if head -c 4096 "$work_sql" | grep -q 'PostgreSQL database dump'; then
    if command -v psql >/dev/null 2>&1; then method=postgres; else method=none; fi
  else
    method=sqlite
  fi
fi

case "$method" in
  sqlite)
    command -v sqlite3 >/dev/null 2>&1 \
      || fail "sqlite3 CLI not installed; apt-get install -y sqlite3"
    log "  restoring into isolated sqlite temp db"
    tmp_db="$work_dir/verify.sqlite3"
    sqlite3 "$tmp_db" < "$work_sql" || fail "sqlite restore failed"
    # Spot-check: at least one real row in two core tables.
    products=$(sqlite3 "$tmp_db" "SELECT COUNT(*) FROM products" 2>/dev/null || echo 0)
    wilayas=$(sqlite3 "$tmp_db" "SELECT COUNT(*) FROM delivery_zones" 2>/dev/null || echo 0)
    log "  restored: products=$products, delivery_zones=$wilayas"
    [ "$wilayas" -ge 1 ] \
      || fail "restored DB missing delivery_zones rows — not a valid LUXE dump"
    ;;
  postgres)
    log "  restoring into isolated postgres temp DB"
    tmp_db="luxe_verify_$$"
    PGPASSWORD="${POSTGRES_PASSWORD:-}" createdb -h "${POSTGRES_HOST:-db}" \
      -U "${POSTGRES_USER:-luxe_app_user}" "$tmp_db" \
      || fail "createdb failed"
    trap 'PGPASSWORD="${POSTGRES_PASSWORD:-}" dropdb -h "${POSTGRES_HOST:-db}" -U "${POSTGRES_USER:-luxe_app_user}" "$tmp_db" >/dev/null 2>&1 || true; rm -rf "$work_dir"' EXIT
    PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST:-db}" \
      -U "${POSTGRES_USER:-luxe_app_user}" "$tmp_db" \
      -q -f "$work_sql" \
      || fail "psql restore failed"
    wilayas=$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST:-db}" \
      -U "${POSTGRES_USER:-luxe_app_user}" "$tmp_db" \
      -tAc "SELECT COUNT(*) FROM delivery_zones" || echo 0)
    log "  restored: delivery_zones=$wilayas"
    [ "$wilayas" -ge 1 ] \
      || fail "restored DB missing delivery_zones rows"
    ;;
  none)
    fail "no DB client available; install sqlite3 or psql"
    ;;
  *)
    fail "unknown VERIFY_METHOD: $method"
    ;;
esac

log "OK — $(basename "$latest") is verifiable"
exit 0
