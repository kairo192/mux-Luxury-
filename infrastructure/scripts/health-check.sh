#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — comprehensive health probe.
# Run manually, from Uptime Kuma (via "push" monitor), or as the smoke test at
# the end of release-deploy.sh. Checks API, DB connectivity (via the API) and
# storefront reachability. Exits 0 on green, non-zero otherwise.
# =============================================================================
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1/api/v1}"
STOREFRONT_URL="${STOREFRONT_URL:-http://127.0.0.1/}"
TIMEOUT="${TIMEOUT:-8}"

FAILED=0
check() {
  local name="$1"; shift
  local url="$1";  shift
  local expected="${1:-200}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" || echo "000")
  if [ "$code" = "$expected" ]; then
    printf '  OK   %-20s %s (%s)\n' "$name" "$url" "$code"
  else
    printf '  FAIL %-20s %s (got %s, want %s)\n' "$name" "$url" "$code" "$expected"
    FAILED=$((FAILED + 1))
  fi
}

printf 'Mus Luxury health check — %s\n' "$(date -u +%FT%TZ)"
check "api-health"   "$API_BASE/health"           200
check "api-catalog"  "$API_BASE/catalog/products" 200
check "storefront"   "$STOREFRONT_URL"            200

if [ "$FAILED" -gt 0 ]; then
  printf '\n%d check(s) failed\n' "$FAILED" >&2
  exit 1
fi
printf '\nall checks passed\n'
