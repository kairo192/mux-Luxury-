#!/usr/bin/env bash
# =============================================================================
# Run ON THE SERVER by the desktop CMS release workflow, appended after
# compose-project.sh (so the folder is decided by the very function
# release-deploy.sh uses — one source of truth):
#
#   cat compose-project.sh downloads-dir.sh | ssh host bash -s -- <install root>
#
# Prints the folder of the desktop CMS update files (the API serves it to
# logged-in CMS apps only)
# (LUXE_DOWNLOADS_DIR from <root>/shared/.env, else <root>/shared/downloads),
# creating it and recording it in the .env when missing.
# =============================================================================
set -euo pipefail
root="${1:?install root (e.g. /opt/luxe)}"
luxe_ensure_downloads_dir "$root/shared/.env" "$root/shared"
# shellcheck disable=SC2154  # exported by luxe_ensure_downloads_dir (compose-project.sh)
printf '%s\n' "$LUXE_DOWNLOADS_DIR"
