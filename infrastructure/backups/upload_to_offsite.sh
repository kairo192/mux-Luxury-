#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — off-site copy of the nightly backup.
#
# Sends the files of the last backup run (the newest luxe_backup_<ts>.sha256
# manifest and every file it lists) to S3-compatible storage, then deletes
# old copies there so a FREE plan never fills up:
#   - database files older than OFFSITE_RETENTION_DAYS (default 30) days;
#   - photo archives beyond the newest BACKUP_MEDIA_KEEP (default 3) — the
#     newest ones are kept whatever their age (photos may not change for months).
#
# Works with any S3-compatible storage. Free plans: Backblaze B2 and
# Cloudflare R2 (10 GB each). Paid: Wasabi, Scaleway, OVH, AWS…
# Only the standard storage class is used (the one free plans cover).
#
# Tool: rclone (`apt-get install -y rclone`; installed by vps-bootstrap.sh).
# It is configured from the .env values below — no rclone config file.
#
# Settings (from /opt/luxe/shared/.env):
#   S3_BACKUP_ENABLED=true
#   S3_ENDPOINT_URL      e.g. https://s3.eu-central-003.backblazeb2.com
#                        or   https://<account-id>.r2.cloudflarestorage.com
#   S3_REGION            e.g. eu-central-003 (B2) / auto (R2)
#   S3_BUCKET_NAME, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
#   S3_BUCKET_PREFIX     folder inside the bucket (default luxe)
#   OFFSITE_RETENTION_DAYS, BACKUP_MEDIA_KEEP
#
# Getting a copy back (e.g. on a new server, same .env values):
#   upload_to_offsite.sh list               every file in the bucket folder
#   upload_to_offsite.sh download <path>    one file (path as listed) → $BACKUP_DIR
#
# Exit codes: 0 uploaded (or off-site copy switched off) · 1 nothing to
# upload · 2 upload failed (cron alerts). A failed clean-up only warns.
# =============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/lib/luxe/backups}"
LOG_PREFIX="[offsite-upload]"

log()  { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$LOG_PREFIX" "$*"; }
fail() { log "FATAL: $*" >&2; exit 2; }

MODE="${1:-upload}"
case "$MODE" in upload|list|download) ;; *) fail "usage: $0 [upload | list | download <path>]" ;; esac
enabled="${S3_BACKUP_ENABLED:-false}"
if [ "$MODE" = "upload" ]; then
  case "${enabled,,}" in
    true|1|yes) ;;
    *) log "S3_BACKUP_ENABLED is not on: off-site copy skipped (backups stay on this server)."
       exit 0 ;;
  esac
fi

for v in S3_ENDPOINT_URL S3_BUCKET_NAME S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
  value="${!v:-}"
  if [ -z "$value" ] || [[ "$value" == \<* ]]; then
    fail "$v is not configured in /opt/luxe/shared/.env"
  fi
done

command -v rclone >/dev/null 2>&1 || fail "rclone not found; install it with: sudo apt-get install -y rclone"

RETENTION_DAYS="${OFFSITE_RETENTION_DAYS:-30}"
MEDIA_KEEP="${BACKUP_MEDIA_KEEP:-3}"
[[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [ "$RETENTION_DAYS" -ge 1 ] || fail "OFFSITE_RETENTION_DAYS must be a number of days"
[[ "$MEDIA_KEEP" =~ ^[0-9]+$ ]] && [ "$MEDIA_KEEP" -ge 1 ] || fail "BACKUP_MEDIA_KEEP must be 1 or more"

# rclone remote "offsite", defined only through the environment of this script.
export RCLONE_CONFIG_OFFSITE_TYPE=s3
export RCLONE_CONFIG_OFFSITE_PROVIDER=Other
export RCLONE_CONFIG_OFFSITE_ENDPOINT="$S3_ENDPOINT_URL"
export RCLONE_CONFIG_OFFSITE_REGION="${S3_REGION:-auto}"
export RCLONE_CONFIG_OFFSITE_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID"
export RCLONE_CONFIG_OFFSITE_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY"
# Keys limited to one bucket (B2 / R2) may not list or create buckets.
export RCLONE_CONFIG_OFFSITE_NO_CHECK_BUCKET=true
export RCLONE_CONFIG=/dev/null
RCLONE=(rclone --retries 3 --low-level-retries 5 --contimeout 30s --timeout 5m)
prefix="${S3_BUCKET_PREFIX:-luxe}"

if [ "$MODE" = "list" ]; then
  "${RCLONE[@]}" lsf -R --files-only "offsite:${S3_BUCKET_NAME}/${prefix}" || fail "could not list the bucket"
  exit 0
fi
if [ "$MODE" = "download" ]; then
  path="${2:-}"
  [ -n "$path" ] && [[ "$path" != *..* ]] || fail "usage: $0 download <path as shown by: $0 list>"
  mkdir -p "$BACKUP_DIR"
  "${RCLONE[@]}" copyto "offsite:${S3_BUCKET_NAME}/${prefix}/${path}" "$BACKUP_DIR/${path##*/}" \
    || fail "download of $path failed"
  log "downloaded to $BACKUP_DIR/${path##*/}"
  exit 0
fi

if [ ! -d "$BACKUP_DIR" ]; then
  log "backup dir $BACKUP_DIR does not exist; nothing to upload"
  exit 1
fi

manifest=$(ls -1t "$BACKUP_DIR"/luxe_backup_*.sha256 2>/dev/null | head -n 1 || true)
if [ -z "$manifest" ]; then
  log "no luxe_backup_*.sha256 manifest found in $BACKUP_DIR"
  exit 1
fi
latest_ts=$(basename "$manifest" | grep -oE '[0-9]{8}_[0-9]{6}' | head -n 1)
mapfile -t set_files < <(awk '{print $2}' "$manifest" | sed 's/^\*//')
set_files+=("$(basename "$manifest")")

host="${HOSTNAME:-$(hostname -s 2>/dev/null || echo server)}"
base="offsite:${S3_BUCKET_NAME}/${prefix}/${host}"
date_folder="${latest_ts:0:4}/${latest_ts:4:2}/${latest_ts:6:2}"

# Only encrypted archives leave the server (plus the checksum list, which holds
# file names and hashes only). A backup made without BACKUP_ENCRYPTION_KEY is
# refused here rather than stored readable at the storage provider.
for name in "${set_files[@]}"; do
  case "$name" in
    *.enc|luxe_backup_*.sha256) ;;
    *) fail "$name is not encrypted: set BACKUP_ENCRYPTION_KEY in /opt/luxe/shared/.env (nothing was uploaded)" ;;
  esac
done

log "uploading the backup of $latest_ts to ${S3_BUCKET_NAME}/${prefix}/${host}/${date_folder}"
uploaded=0
failed=0
for name in "${set_files[@]}"; do
  f="$BACKUP_DIR/$name"
  [ -f "$f" ] || { log "  missing $name"; failed=$((failed + 1)); continue; }
  # Photo archives live in one folder and are sent once: the same archive is
  # listed again on the nights when the photos did not change.
  dest="$base/$date_folder/$name"
  if [[ "$name" == luxe_media_* ]]; then
    dest="$base/media/$name"
    if [ -n "$("${RCLONE[@]}" lsf "$dest" 2>/dev/null || true)" ]; then
      log "  = $name (already there)"
      uploaded=$((uploaded + 1))
      continue
    fi
  fi
  log "  → $name"
  if "${RCLONE[@]}" copyto "$f" "$dest"; then
    uploaded=$((uploaded + 1))
  else
    failed=$((failed + 1))
    log "    upload failed for $name"
  fi
done

[ "$uploaded" -gt 0 ] || fail "no file uploaded (failed: $failed)"
[ "$failed" -eq 0 ] || fail "uploaded $uploaded file(s) but $failed failed"
log "uploaded $uploaded file(s)"

# ---- Clean-up: keep the storage under a free plan's limit -------------------
listing=$("${RCLONE[@]}" lsf -R --files-only "$base" 2>/dev/null) || {
  log "WARNING: could not list the off-site copies; old ones were not removed"
  exit 0
}
cutoff=$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%d)
mapfile -t media_keep < <(printf '%s\n' "$listing" | grep -E '(^|/)luxe_media_[0-9]{8}_[0-9]{6}' \
  | awk -F/ '{print $NF "\t" $0}' | sort -r | head -n "$MEDIA_KEEP" | cut -f2)

removed=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  name="${path##*/}"
  ts=$(printf '%s' "$name" | grep -oE '[0-9]{8}_[0-9]{6}' | head -n 1 || true)
  [ -n "$ts" ] || continue                       # not a backup file: leave it
  if [[ "$name" == luxe_media_* ]]; then
    keep=0
    for k in "${media_keep[@]}"; do [ "$k" = "$path" ] && keep=1; done
    [ "$keep" -eq 1 ] && continue
  elif [ "${ts:0:8}" -ge "$cutoff" ]; then
    continue
  fi
  if "${RCLONE[@]}" deletefile "$base/$path"; then
    removed=$((removed + 1))
  else
    log "WARNING: could not remove old copy $path"
  fi
done <<< "$listing"

log "clean-up: removed $removed old file(s) (database files older than ${RETENTION_DAYS} days, photo archives beyond the newest ${MEDIA_KEEP})"
exit 0
