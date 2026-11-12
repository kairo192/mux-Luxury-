#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — HTTPS certificates (Let's Encrypt) that renew by themselves.
#
#   sudo certificates.sh setup        first certificate + automatic renewal
#   sudo certificates.sh deploy-hook  (called by certbot after each renewal)
#        certificates.sh check        days left; exit 1 under WARN_DAYS (14)
#
# Why: nginx (Docker) holds port 80, so certbot's "standalone" mode cannot
# renew while the shop runs, and nginx reads a COPY of the certificate in
# $INSTALL_ROOT/shared/nginx-ssl. Without this, the certificate silently
# expires after 90 days and every visitor gets a browser security error.
#
# How: renewals use the "webroot" method — nginx serves
# /.well-known/acme-challenge/ from $WEBROOT on port 80 (nginx.conf, mounted
# by docker-compose.yml) — so renewals need no downtime. After each renewal the
# deploy hook copies the files and reloads nginx (no restart, no lost visits).
# certbot's own systemd timer (installed with the package) runs the renewals.
# =============================================================================
set -euo pipefail

# Values saved by "setup", so the renewal hook (run later by certbot) uses
# the same folders. Environment variables still take precedence.
CONF_FILE=/etc/luxe-certificates.env
# shellcheck disable=SC1090
[ -r "$CONF_FILE" ] && . "$CONF_FILE"

DOMAIN="${DOMAIN:-mus-luxury.com}"
EXTRA_DOMAINS="${EXTRA_DOMAINS:-www.$DOMAIN api.$DOMAIN}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/luxe}"
WEBROOT="${WEBROOT:-/var/www/certbot}"
SSL_DIR="${SSL_DIR:-$INSTALL_ROOT/shared/nginx-ssl}"
PROXY_CONTAINER="${PROXY_CONTAINER:-luxe_proxy}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
WARN_DAYS="${WARN_DAYS:-14}"
LIVE_DIR="${LIVE_DIR:-/etc/letsencrypt/live/$DOMAIN}"
# Stable copy used by certbot's hook: release folders are pruned by deploys.
HOOK_BIN=/usr/local/sbin/luxe-certificates

log() { printf '[certificates] %s\n' "$*"; }
fail() { printf '[certificates] ERROR: %s\n' "$*" >&2; exit 1; }
need_root() { [ "$EUID" -eq 0 ] || fail "run as root (sudo)"; }

domain_args() {
  local args=(-d "$DOMAIN") d
  for d in $EXTRA_DOMAINS; do args+=(-d "$d"); done
  printf '%s\n' "${args[@]}"
}

proxy_running() {
  command -v docker >/dev/null 2>&1 && [ "$(docker inspect -f '{{.State.Running}}' "$PROXY_CONTAINER" 2>/dev/null)" = "true" ]
}

# Copies the live certificate where nginx reads it and reloads nginx.
deploy_hook() {
  need_root
  [ -f "$LIVE_DIR/fullchain.pem" ] || fail "no certificate in $LIVE_DIR"
  install -d -m 0755 "$SSL_DIR"
  install -m 0644 "$LIVE_DIR/fullchain.pem" "$SSL_DIR/fullchain.pem"
  install -m 0600 "$LIVE_DIR/privkey.pem" "$SSL_DIR/privkey.pem"
  if proxy_running; then
    docker exec "$PROXY_CONTAINER" nginx -t >/dev/null 2>&1 && docker exec "$PROXY_CONTAINER" nginx -s reload
    log "nginx reloaded with the new certificate"
  else
    log "nginx is not running; it will use the new certificate when it starts"
  fi
}

days_left() {
  local f="$1" end
  end=$(openssl x509 -enddate -noout -in "$f" | cut -d= -f2)
  echo $(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
}

check() {
  local f="$SSL_DIR/fullchain.pem"
  [ -r "$f" ] || { echo "certificate: MISSING ($f)"; exit 1; }
  local d; d=$(days_left "$f")
  if [ "$d" -lt "$WARN_DAYS" ]; then
    echo "certificate: EXPIRES IN $d DAYS — run: sudo certbot renew && sudo $HOOK_BIN deploy-hook"
    exit 1
  fi
  echo "certificate: OK ($d days left)"
}

setup() {
  need_root
  command -v certbot >/dev/null 2>&1 || { apt-get update -y && apt-get install -y certbot; }
  install -d -m 0755 "$WEBROOT"
  install -m 0755 "$(readlink -f "$0")" "$HOOK_BIN"
  umask 077
  printf 'DOMAIN=%q\nEXTRA_DOMAINS=%q\nINSTALL_ROOT=%q\nWEBROOT=%q\nSSL_DIR=%q\nPROXY_CONTAINER=%q\n' \
    "$DOMAIN" "$EXTRA_DOMAINS" "$INSTALL_ROOT" "$WEBROOT" "$SSL_DIR" "$PROXY_CONTAINER" > "$CONF_FILE"
  umask 022
  local email_args=(--register-unsafely-without-email)
  [ -n "$CERTBOT_EMAIL" ] && email_args=(-m "$CERTBOT_EMAIL")
  mapfile -t doms < <(domain_args)

  if [ ! -f "$LIVE_DIR/fullchain.pem" ]; then
    # First certificate: nginx cannot start without one, so certbot answers
    # on port 80 itself (nginx stopped for a minute if it is already up).
    local was_running=0
    if proxy_running; then was_running=1; docker stop "$PROXY_CONTAINER" >/dev/null; fi
    certbot certonly --standalone --non-interactive --agree-tos "${email_args[@]}" "${doms[@]}" \
      || { [ "$was_running" = 1 ] && docker start "$PROXY_CONTAINER" >/dev/null; fail "first certificate refused (DNS pointing to this server? port 80 open?)"; }
    deploy_hook
    [ "$was_running" = 1 ] && docker start "$PROXY_CONTAINER" >/dev/null
  fi

  local conf="/etc/letsencrypt/renewal/$DOMAIN.conf"
  if grep -q '^authenticator = webroot' "$conf" 2>/dev/null && grep -q "^renew_hook = $HOOK_BIN deploy-hook" "$conf" 2>/dev/null; then
    log "automatic renewal already set up (webroot, no downtime)"
  elif proxy_running; then
    # Switch renewals to webroot through the running nginx. This issues one
    # fresh certificate (well within Let's Encrypt limits) and stores the
    # method + hook in $conf for every future renewal.
    certbot certonly --webroot -w "$WEBROOT" --non-interactive --agree-tos "${email_args[@]}" \
      --cert-name "$DOMAIN" --force-renewal --deploy-hook "$HOOK_BIN deploy-hook" "${doms[@]}"
    certbot renew --dry-run --cert-name "$DOMAIN" >/dev/null && log "renewal test (dry run): OK"
  else
    log "Start the shop (first deploy), then run 'sudo $HOOK_BIN setup' again to switch renewals to"
    log "the no-downtime method. Until then the certificate is valid for 90 days."
  fi
  systemctl enable --now certbot.timer >/dev/null 2>&1 || log "note: certbot.timer not found; add a daily 'certbot renew' cron"
  check
}

case "${1:-}" in
  setup) setup ;;
  deploy-hook) deploy_hook ;;
  check) check ;;
  *) echo "usage: $0 setup | deploy-hook | check" >&2; exit 2 ;;
esac
