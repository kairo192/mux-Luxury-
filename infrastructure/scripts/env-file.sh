#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — read the production .env safely (bash library + runner).
#
#   source infrastructure/scripts/env-file.sh && luxe_load_env /opt/luxe/shared/.env
#   bash infrastructure/scripts/env-file.sh /opt/luxe/shared/.env <command> [args…]
#
# The .env is written for Docker (KEY=VALUE lines), not for bash: generated
# passwords may hold ? # & ; $ ( ) and unused integrations keep placeholders
# like <FILL_IN_…>. `set -a; . .env` would run those as shell code — a syntax
# error (deploy and nightly backup stop) or worse. Here every value is taken
# literally, the way Docker Compose reads the file:
#   - blank lines and lines starting with # are skipped; "export " is allowed;
#   - "double" or 'single' quotes around the whole value are removed;
#   - in an unquoted value, " #…" (space then #) is a comment; a # inside a
#     word (Pa55#word) is kept.
# =============================================================================

luxe_load_env() {
  local file="$1" line key val
  if [ ! -r "$file" ]; then
    echo "env-file: cannot read $file" >&2
    return 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    if [[ ! "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
      continue
    fi
    key="${BASH_REMATCH[2]}"
    val="${BASH_REMATCH[3]}"
    val="${val#"${val%%[![:space:]]*}"}"            # leading spaces
    if [[ "$val" =~ ^\"(.*)\"[[:space:]]*(#.*)?$ ]]; then
      val="${BASH_REMATCH[1]//\\\"/\"}"
    elif [[ "$val" =~ ^\'(.*)\'[[:space:]]*(#.*)?$ ]]; then
      val="${BASH_REMATCH[1]}"
    else
      val="${val%%[[:space:]]#*}"                    # " # comment"
      val="${val%"${val##*[![:space:]]}"}"           # trailing spaces
    fi
    export "$key=$val"
  done < "$file"
}

# Run as a program: load the file, then run the command with those values.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -euo pipefail
  [ $# -ge 2 ] || { echo "usage: $0 <env-file> <command> [args…]" >&2; exit 2; }
  luxe_load_env "$1"
  shift
  exec "$@"
fi
