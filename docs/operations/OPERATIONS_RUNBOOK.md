# Mus Luxury (LUXE) — Operations & Incident Response Runbook

**Audience:** System Administrators, On-Call DevOps, Technical Store Owners  
**Target Host:** Octenium Ubuntu 24.04 VPS (`5.196.163.6`)  
**Base Directory:** `/opt/luxe`

---

## 1. Routine Service Management

All application services run under Docker Compose in `/opt/luxe`.

### 1.1 Status & Health Overview
```bash
cd /opt/luxe
docker compose ps
```
All containers (`luxe_postgres`, `luxe_api`, `luxe_proxy`, `luxe_storefront`) must display status `Up` with `(healthy)` indicators.

### 1.2 Inspecting Live Logs
```bash
# Follow all container logs in real time
docker compose logs -f --tail=50

# Follow backend API logs only
docker compose logs -f --tail=100 api

# Follow Nginx access & error logs
docker compose logs -f --tail=100 nginx

# Follow PostgreSQL logs
docker compose logs -f --tail=100 db
```

### 1.3 Service Restart Commands
```bash
# Soft restart of reverse proxy (reloads Nginx configs and SSL certificates)
docker compose exec nginx nginx -s reload

# Restart backend API only (zero database interruption)
docker compose restart api

# Complete ecosystem restart
docker compose down
docker compose up -d
```

---

## 2. Resource & Performance Monitoring

Because the VPS operates on 1 vCore and 2 GB RAM, periodically check resource consumption:

```bash
# Interactive system overview
htop

# Live container memory and CPU stats
docker stats --no-stream

# Check disk space on root ext4 partition
df -h /

# Check memory and swap utilization
free -m
```

### Alert Thresholds:
- **RAM Available:** If `available` drops below 250 MB, investigate container memory leases.
- **Disk Free:** If free space drops below 5.0 GB, clean unused Docker images:
  ```bash
  docker image prune -a --force
  ```

---

## 3. Incident Response Procedures

### 3.1 Incident: API Returning 502 Bad Gateway
**Symptoms:** Nginx returns `502 Bad Gateway` on `https://api.mus-luxury.com` or `https://mus-luxury.com/api/v1/...`.

**Root Cause Checklist:**
1. Check if backend container crashed:
   ```bash
   docker compose ps api
   ```
2. View crash traceback:
   ```bash
   docker compose logs --tail=100 api
   ```
3. Verify database connectivity:
   ```bash
   docker compose exec db pg_isready -U luxe_app_user -d luxe_ecommerce
   ```
4. Restart API:
   ```bash
   docker compose restart api
   ```

---

### 3.2 Incident: PostgreSQL Connection Pool Exhaustion
**Symptoms:** Requests fail with `CRITICAL: PostgreSQL connection failed` or slow query hangs.

**Investigation & Fix:**
```bash
# Check active connections inside PostgreSQL
docker compose exec -T db psql -U luxe_app_user -d luxe_ecommerce -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Kill idle-in-transaction connections older than 5 minutes
docker compose exec -T db psql -U luxe_app_user -d luxe_ecommerce -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < current_timestamp - INTERVAL '5 minutes';"
```

---

### 3.3 Incident: Store Owner Locked Out / Forgotten Password
**Symptoms:** Store owner forgot admin credentials, or recovery SMS/WhatsApp is unreachable.

**Remediation (Emergency CLI Reset):**
An automated, offline administrative credential reset tool is provided in `backend/scripts/emergency_reset_owner.py`:

```bash
# Execute secure password reset directly against production database
docker compose exec -it api python3 /app/scripts/emergency_reset_owner.py \
  --email admin@mus-luxury.com \
  --new-password "SecureOwnerNewPassword2026!"
```

If `--new-password` is omitted, the script prompts for input securely with hidden terminal typing via `getpass`.

The script:
1. Verifies the owner exists in `admin_users`.
2. Hashes the new password with PBKDF2-SHA256 (600,000 iterations).
3. Unlocks the account (`is_active = 1`).
4. Clears all failed login attempt counters.
5. Invalidates any previously issued JWT tokens by issuing a revocation signal.

---

### 3.4 Incident: SSL / TLS Certificate Expired
**Symptoms:** Browsers show `NET::ERR_CERT_DATE_INVALID`.

**Remediation:**
```bash
# Force renewal via certbot standalone
systemctl stop nginx 2>/dev/null || true
docker compose stop nginx
certbot renew --force-renewal

# Copy renewed certificates
cp /etc/letsencrypt/live/mus-luxury.com/fullchain.pem /opt/luxe/infrastructure/nginx/ssl/fullchain.pem
cp /etc/letsencrypt/live/mus-luxury.com/privkey.pem /opt/luxe/infrastructure/nginx/ssl/privkey.pem

# Restart proxy
docker compose up -d nginx
```

