#!/usr/bin/env bash
# ============================================================================
# MUS LUXURY (LUXE) — PRODUCTION DEPLOYMENT SCRIPT FOR ALGERIAN UBUNTU LTS VPS
# Compatible with ICOSNET, ISSAL NET, HOSTARTS & standard KVM Ubuntu 22.04/24.04
# ============================================================================
set -euo pipefail

echo "[1/5] Checking environment configuration..."
if [ ! -f .env ]; then
  echo "ERROR: .env file is missing. Copy .env.example to .env and configure production secrets first."
  exit 1
fi

echo "[2/5] Building and starting PostgreSQL, FastAPI, Storefront, and Nginx containers..."
docker compose up -d --build

echo "[3/5] Waiting for PostgreSQL healthcheck..."
sleep 5

echo "[4/5] Running Backend API and Security self-check..."
docker compose exec -T api python3 -m unittest discover -s tests -v

echo "[5/5] Deployment complete! Public website and API are active behind Nginx."
