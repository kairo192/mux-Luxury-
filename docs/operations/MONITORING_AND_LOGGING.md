# Mus Luxury (LUXE) — Low-Overhead Observability & Logging Guide

**Target Environment:** 1 vCore / 2 GB RAM / 40 GB ext4 Ubuntu VPS (`5.196.163.6`)  
**Design Principle:** High diagnostic visibility with minimal memory (< 20 MB) and CPU overhead (no heavy Prometheus / Elastic / Grafana stacks).

---

## 1. Health & Readiness Probes

The backend exposes dedicated probe endpoints used by Nginx, Docker healthchecks, and external monitoring tools:

### 1.1 Liveness Probe (`GET /api/v1/health`)
- Verifies that FastAPI and Uvicorn event loops are responding to HTTP traffic.
- Lightweight: does not query the database.
- Response: `{"status": "ok", "app_env": "production", "version": "1.0.0"}`

### 1.2 Readiness Probe (`GET /api/v1/ready`)
- Verifies end-to-end connectivity to the PostgreSQL database.
- Runs a fast test query (`SELECT 1`).
- Returns HTTP 200 on success: `{"status": "ready", "database": "connected"}`.
- Returns HTTP 503 if PostgreSQL is unreachable or locked.

---

## 2. Docker Healthcheck Integration

All four containers configure native Docker healthchecks:

| Container | Healthcheck Command | Interval | Timeout | Retries |
| :--- | :--- | :--- | :--- | :--- |
| `luxe_postgres` | `pg_isready -U luxe_app_user -d luxe_ecommerce` | 10s | 5s | 5 |
| `luxe_api` | Python urllib test of `http://127.0.0.1:8000/api/v1/health` | 15s | 5s | 5 |
| `luxe_proxy` | `wget -qO- http://127.0.0.1:80/api/v1/health` | 15s | 5s | 5 |
| `luxe_storefront` | `wget -qO- http://127.0.0.1:80/` | 15s | 5s | 3 |

Inspect health statuses in real time:
```bash
docker compose ps
```

---

## 3. Lightweight Health Monitor Script (`vps_health_monitor.sh`)

Install an automated system health check cron job at `/usr/local/bin/vps_health_monitor.sh`:

```bash
cat << 'EOF' > /usr/local/bin/vps_health_monitor.sh
#!/usr/bin/env bash
set -euo pipefail

ALERT_EMAIL="alerts@mus-luxury.com"
DISK_USAGE=$(df -P / | awk 'NR==2 {print $5}' | tr -d '%')
MEM_AVAILABLE=$(free -m | awk 'NR==2 {print $7}')
SWAP_USED=$(free -m | awk 'NR==3 {print $3}')

# Check Disk Space (Alert if > 85%)
if [ "${DISK_USAGE}" -gt 85 ]; then
  echo "WARNING: Root disk usage is at ${DISK_USAGE}% on Mus Luxury VPS!" | \
    logger -t luxe-alert -p user.warning
fi

# Check Available Memory (Alert if < 200MB)
if [ "${MEM_AVAILABLE}" -lt 200 ]; then
  echo "CRITICAL: Available memory is low (${MEM_AVAILABLE} MB) on Mus Luxury VPS!" | \
    logger -t luxe-alert -p user.crit
fi

# Check Swap Usage (Alert if > 500MB)
if [ "${SWAP_USED}" -gt 500 ]; then
  echo "WARNING: Significant swap space in use (${SWAP_USED} MB) on Mus Luxury VPS!" | \
    logger -t luxe-alert -p user.warning
fi
EOF

chmod 750 /usr/local/bin/vps_health_monitor.sh
```

Run via cron every 5 minutes:
```bash
echo "*/5 * * * * root /usr/local/bin/vps_health_monitor.sh" > /etc/cron.d/luxe-vps-monitor
```

---

## 4. External Uptime Monitoring Setup

Because internal scripts cannot alert if the whole VPS goes offline, configure a free external monitor (e.g. UptimeRobot, BetterUptime, or Healthchecks.io):

1. **Storefront Monitor:**
   - URL: `https://mus-luxury.com/`
   - Check Interval: Every 5 minutes
   - Expected Response: HTTP 200
2. **API Readiness Monitor:**
   - URL: `https://api.mus-luxury.com/api/v1/ready`
   - Check Interval: Every 1 minute
   - Keyword Match: `"database": "connected"`
   - Alerting Channels: Email / Telegram / SMS to store manager

