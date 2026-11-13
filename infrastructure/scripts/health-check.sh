#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — health probe, run on the VPS (by hand, from Uptime Kuma via a
# "push" monitor, or after a deploy). Exits 0 when everything is green.
#
# Goes through the local nginx over HTTPS with the real domain name (port 80
# only redirects to HTTPS), so it tests what customers get: certificate, nginx,
# API, database and shop page — without depending on DNS from inside the VPS.
# =============================================================================
set -uo pipefail

DOMAIN="${DOMAIN:-mus-luxury.com}"
HOST_IP="${HOST_IP:-127.0.0.1}"
TIMEOUT="${TIMEOUT:-8}"
WARN_DAYS="${WARN_DAYS:-14}"
CA_ARGS=()
[ -n "${CURL_CA:-}" ] && CA_ARGS=(--cacert "$CURL_CA")   # tests only (self-signed)
BASE="https://$DOMAIN"

FAILED=0
check() {
  local name="$1" path="$2" expected="${3:-200}" code
  code=$(curl -s --noproxy "*" -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${CA_ARGS[@]}" \
    --resolve "$DOMAIN:443:$HOST_IP" "$BASE$path" || true)
  if [ "$code" = "$expected" ]; then
    printf '  OK   %-12s %s (%s)\n' "$name" "$path" "$code"
  else
    printf '  FAIL %-12s %s (got %s, want %s)\n' "$name" "$path" "${code:-000}" "$expected"
    FAILED=$((FAILED + 1))
  fi
}

printf 'Mus Luxury health check — %s\n' "$(date -u +%FT%TZ)"
check "api"      "/api/v1/health"
check "ready"    "/api/v1/ready"                 # database + wilayas + photo folder
check "catalog"  "/api/v1/products?page_size=1"
check "shop"     "/"
# Port 80 must send visitors to HTTPS.
code=$(curl -s --noproxy "*" -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" -H "Host: $DOMAIN" "http://$HOST_IP/" || true)
if [ "$code" = "301" ]; then printf '  OK   %-12s %s (%s)\n' "http→https" "port 80" "$code"
else printf '  FAIL %-12s %s (got %s, want 301)\n' "http→https" "port 80" "${code:-000}"; FAILED=$((FAILED + 1)); fi

# Certificate as served to visitors.
end=$(echo | openssl s_client -connect "$HOST_IP:443" -servername "$DOMAIN" 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$end" ]; then
  days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
  if [ "$days" -ge "$WARN_DAYS" ]; then printf '  OK   %-12s %s days left\n' "certificate" "$days"
  else printf '  FAIL %-12s expires in %s days (sudo luxe-certificates setup)\n' "certificate" "$days"; FAILED=$((FAILED + 1)); fi
else
  printf '  FAIL %-12s not readable on port 443\n' "certificate"; FAILED=$((FAILED + 1))
fi

# Disk (40 GB VPS): warn before backups and Docker fill it.
used=$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')
if [ "${used:-0}" -lt 85 ]; then printf '  OK   %-12s %s%% used\n' "disk" "$used"
else printf '  FAIL %-12s %s%% used (docker image prune -a; see OPERATIONS_GUIDE §5)\n' "disk" "$used"; FAILED=$((FAILED + 1)); fi

if [ "$FAILED" -gt 0 ]; then
  printf '\n%d check(s) failed\n' "$FAILED" >&2
  exit 1
fi
printf '\nall checks passed\n'
