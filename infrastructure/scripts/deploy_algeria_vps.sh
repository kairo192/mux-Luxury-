#!/usr/bin/env bash
# ============================================================================
# MUS LUXURY (LUXE) — PRODUCTION DEPLOYMENT SCRIPT FOR ALGERIAN UBUNTU LTS VPS
# Compatible with ICOSNET, ISSAL NET, HOSTARTS & standard KVM Ubuntu 22.04/24.04
# ============================================================================
set -euo pipefail

echo "[1/5] Checking environment configuration (.env)..."
if [ ! -f .env ]; then
  echo "ERROR: .env file is missing. Copy .env.example to .env and configure production secrets first."
  exit 1
fi
chmod 600 .env || true

echo "[2/5] Ensuring TLS certificates exist in ./infrastructure/nginx/ssl/..."
mkdir -p ./infrastructure/nginx/ssl
if [ -f /etc/letsencrypt/live/mus-luxury.com/fullchain.pem ] && [ -f /etc/letsencrypt/live/mus-luxury.com/privkey.pem ]; then
  cp /etc/letsencrypt/live/mus-luxury.com/fullchain.pem ./infrastructure/nginx/ssl/fullchain.pem
  cp /etc/letsencrypt/live/mus-luxury.com/privkey.pem ./infrastructure/nginx/ssl/privkey.pem
elif [ -f /etc/letsencrypt/live/musluxury.dz/fullchain.pem ] && [ -f /etc/letsencrypt/live/musluxury.dz/privkey.pem ]; then
  cp /etc/letsencrypt/live/musluxury.dz/fullchain.pem ./infrastructure/nginx/ssl/fullchain.pem
  cp /etc/letsencrypt/live/musluxury.dz/privkey.pem ./infrastructure/nginx/ssl/privkey.pem
elif [ ! -f ./infrastructure/nginx/ssl/fullchain.pem ]; then
  echo "================================================================================"
  echo "[WARNING] Let's Encrypt certificate not found at /etc/letsencrypt/live/musluxury.dz/"
  echo "[WARNING] Generating a temporary SELF-SIGNED bootstrap certificate for Nginx startup."
  echo "[WARNING] Replace with a valid Let's Encrypt certificate before serving public traffic!"
  echo "================================================================================"
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ./infrastructure/nginx/ssl/privkey.pem \
    -out ./infrastructure/nginx/ssl/fullchain.pem \
    -subj "/C=DZ/ST=Blida/L=OuledYaich/O=MusLuxury/CN=musluxury.dz" 2>/dev/null
fi

echo "[3/5] Building and starting PostgreSQL 16, FastAPI, Storefront, and Nginx containers..."
docker compose up -d --build

echo "[4/5] Polling /api/v1/health until PostgreSQL & FastAPI are healthy..."
HEALTH_OK=0
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:80/api/v1/health >/dev/null 2>&1 || wget -qO- http://127.0.0.1:80/api/v1/health >/dev/null 2>&1; then
    HEALTH_OK=1
    echo "Health check passed on attempt ${attempt}!"
    break
  fi
  sleep 2
done

if [ "$HEALTH_OK" -ne 1 ]; then
  echo "ERROR: Service failed to pass /api/v1/health within 60 seconds."
  docker compose ps
  exit 1
fi

echo "[5/5] Deployment complete! Public website and API are active behind Nginx."
