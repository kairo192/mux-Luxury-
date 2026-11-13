#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — ONE Docker Compose project for every release (bash library).
#
# Each release lives in its own folder (releases/<version>) and Docker Compose
# names a project after the folder by default. Without a fixed name, the
# migration step (run in releases/<version>) and the start (run in current/)
# were two different projects: a second "luxe_postgres" container (name
# clash: the first deploy fails) and a second, EMPTY database volume.
#
#   luxe_ensure_compose_project /opt/luxe/shared/.env
#       Makes sure the shared .env (linked into every release, read by Compose
#       for every command, manual ones included) holds COMPOSE_PROJECT_NAME.
#       If missing, it keeps the project of the database already running
#       (its Compose label), else "luxe" for a new server. Exports it.
#   luxe_check_db_volume
#       Refuses to go on when this project's database volume does not exist
#       but another shop database volume does (it would start an empty shop).
# =============================================================================

luxe_ensure_compose_project() {
  local env_file="$1" name
  name=$(grep -E '^[[:space:]]*COMPOSE_PROJECT_NAME[[:space:]]*=' "$env_file" 2>/dev/null \
    | tail -n 1 | cut -d= -f2- | tr -d "\"' \r\t" || true)   # no such line: use the fallback below
  if [ -z "$name" ]; then
    name=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' luxe_postgres 2>/dev/null || true)
    [ -n "$name" ] || name="luxe"
    printf '\n# Docker Compose project of the shop (added by release-deploy.sh). The same for\n# every release, so the database volume (%s_pgdata) is always the same one.\nCOMPOSE_PROJECT_NAME=%s\n' \
      "$name" "$name" >> "$env_file"
  fi
  export COMPOSE_PROJECT_NAME="$name"
}

# Folder served at https://mus-luxury.com/downloads/ (desktop CMS installer and
# signed update files, uploaded by the release workflow). Kept in shared/ so it
# survives every release; recorded in the shared .env so manual `docker compose`
# commands mount the same folder.
luxe_ensure_downloads_dir() {
  local env_file="$1" shared_dir="$2" dir
  dir=$(grep -E '^[[:space:]]*LUXE_DOWNLOADS_DIR[[:space:]]*=' "$env_file" 2>/dev/null \
    | tail -n 1 | cut -d= -f2- | tr -d "\"' \r\t" || true)
  if [ -z "$dir" ]; then
    dir="$shared_dir/downloads"
    printf '\n# Desktop CMS installer + update files, served at /downloads/ (added by release-deploy.sh).\nLUXE_DOWNLOADS_DIR=%s\n' \
      "$dir" >> "$env_file"
  fi
  mkdir -p "$dir/cms"
  export LUXE_DOWNLOADS_DIR="$dir"
}

luxe_check_db_volume() {
  local want="${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME not set}_pgdata" others
  docker volume inspect "$want" >/dev/null 2>&1 && return 0
  others=$(docker volume ls -q | grep -E '_pgdata$' | grep -vx "$want" || true)
  if [ -n "$others" ]; then
    echo "database volume '$want' does not exist, but these do: $(echo "$others" | tr '\n' ' ')" >&2
    echo "→ starting now would open an EMPTY shop. Put the right name in shared/.env:" >&2
    echo "  COMPOSE_PROJECT_NAME=<the part before _pgdata>, then deploy again." >&2
    return 1
  fi
  return 0   # brand-new server: the volume is created on first start
}
