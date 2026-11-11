#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — off-site backup upload
#
# Picks the newest encrypted archives + sha256 manifest in $BACKUP_DIR and
# pushes them to an S3-compatible bucket. Default target is AWS S3 (eu-west-3
# per the shop's existing .env.example) but any endpoint speaking the S3 HTTP
# API works: Wasabi, Backblaze B2, Scaleway, MinIO, Hetzner, DigitalOcean
# Spaces. The transport is the only thing the operator picks; we never run
# a provider SDK.
#
# Why its own script: the nightly cron needs three steps (dump → upload →
# verify). Keeping each in its own file means a single failing step does not
# tie up the retention pruning that lives in the dump script, and the cron
# installer can chain them with && so a failure on upload actually alerts
# instead of being swallowed by "|| true".
#
# Required env (from /opt/luxe/shared/.env):
#   S3_BACKUP_ENABLED=true
#   S3_ENDPOINT_URL=https://s3.eu-west-3.amazonaws.com
#   S3_REGION=eu-west-3
#   S3_BUCKET_NAME=mus-luxury-backups
#   S3_ACCESS_KEY_ID=...
#   S3_SECRET_ACCESS_KEY=...
#   (optional)  S3_BUCKET_PREFIX=db-nightly  — path inside the bucket.
#   (optional)  OFFSITE_RETENTION_DAYS=90    — lifecycle hint used in logs.
#
# Depends on the `aws` CLI being installed on the VPS. The CLI's small,
# `apt-get install -y awscli` adds ~30 MB. We deliberately do NOT install
# it from pip inside the app container — upload runs on the host, not in
# the container, and tying it to the app would couple deploy cadences.
#
# Exit codes:
#   0  — one or more archives uploaded successfully
#   1  — nothing to upload (empty backup dir, misconfig)
#   2  — upload failed; message on stderr, cron should alert
# =============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
LOG_PREFIX="[offsite-upload]"

log()  { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$LOG_PREFIX" "$*"; }
fail() { log "FATAL: $*" >&2; exit 2; }

if [ "${S3_BACKUP_ENABLED:-false}" != "true" ]; then
  log "S3_BACKUP_ENABLED is not 'true'; off-site copy skipped. Set it in"
  log "/opt/luxe/shared/.env to enable the nightly upload."
  exit 0
fi

for v in S3_ENDPOINT_URL S3_REGION S3_BUCKET_NAME S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
  if [ -z "${!v:-}" ] || [[ "${!v}" == \<CHANGE_ME* ]] || [[ "${!v}" == \<FILL_IN* ]]; then
    fail "$v is not configured in /opt/luxe/shared/.env"
  fi
done

command -v aws >/dev/null 2>&1 || fail "aws CLI not found; install with: apt-get install -y awscli"

if [ ! -d "$BACKUP_DIR" ]; then
  log "backup dir $BACKUP_DIR does not exist; nothing to upload"
  exit 1
fi

# Upload exactly the set written by the last backup run: the newest
# luxe_backup_<ts>.sha256 manifest and every file it lists (database dump,
# photos, CMS snapshot). Picking by "newest timestamp in any file name" could
# upload a partial set when two files were written in different seconds.
manifest=$(ls -1t "$BACKUP_DIR"/luxe_backup_*.sha256 2>/dev/null | head -n 1 || true)
if [ -z "$manifest" ]; then
  log "no luxe_backup_*.sha256 manifest found in $BACKUP_DIR"
  exit 1
fi
latest_ts=$(basename "$manifest" | grep -oE '[0-9]{8}_[0-9]{6}' | head -n 1)
mapfile -t set_files < <(awk '{print $2}' "$manifest" | sed 's/^\*//')
set_files+=("$(basename "$manifest")")

log "uploading archive set for timestamp $latest_ts"

prefix="${S3_BUCKET_PREFIX:-db-nightly}"
host="${HOSTNAME:-$(hostname -s 2>/dev/null || echo unknown-host)}"
date_folder="$(date -u -d "${latest_ts:0:8}" +%Y/%m/%d 2>/dev/null || date -u +%Y/%m/%d)"
s3_path="s3://${S3_BUCKET_NAME}/${prefix}/${host}/${date_folder}"

uploaded=0
failed=0
for name in "${set_files[@]}"; do
  f="$BACKUP_DIR/$name"
  [ -f "$f" ] || { log "  missing $name"; failed=$((failed + 1)); continue; }
  log "  → $(basename "$f")"
  if AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" \
     AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
     AWS_DEFAULT_REGION="$S3_REGION" \
     aws --endpoint-url "$S3_ENDPOINT_URL" \
         s3 cp "$f" "$s3_path/$(basename "$f")" \
         --only-show-errors \
         --storage-class STANDARD_IA; then
    uploaded=$((uploaded + 1))
  else
    failed=$((failed + 1))
    log "    upload failed for $(basename "$f")"
  fi
done

if [ "$uploaded" -eq 0 ]; then
  fail "no archives uploaded (failed: $failed)"
fi

log "uploaded $uploaded file(s) to $s3_path (failed: $failed)"

retention_hint="${OFFSITE_RETENTION_DAYS:-}"
if [ -n "$retention_hint" ]; then
  log "reminder: configure bucket lifecycle to expire after ${retention_hint}d"
  log "          aws CLI cannot set this without the bucket's own policy"
fi

exit 0
