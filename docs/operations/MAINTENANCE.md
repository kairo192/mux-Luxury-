# Mus Luxury (`LUXE`) — Operations & Routine Maintenance Runbook

## 1. Maintenance Scope & Routine Schedule

| Frequency | Routine Task | Impact | Execution Window |
| :--- | :--- | :---: | :--- |
| **Daily** | Automated DB & Media Backup | None | 03:00 UTC |
| **Weekly** | Log rotation audit & Docker image pruning | None | Monday 04:00 UTC |
| **Monthly** | PostgreSQL `VACUUM ANALYZE` & Index Maintenance | Minimal | First Sunday of month |
| **Quarterly** | Ubuntu Security Updates & Kernel patching | Brief restart (< 1 min) | Off-peak hours |
| **60 Days** | Let's Encrypt TLS Certificate Renewal | None (automatic) | Auto-renew via Certbot |

---

## 2. Docker Disk & Image Cleanup

Given the 40 GB NVMe disk limit, orphaned Docker layers and dangling build artifacts must be cleared periodically:

```bash
# Check current Docker disk consumption
docker system df

# Prune unused images and build caches (preserving active containers & volumes)
docker image prune -a --filter "until=168h" -f
docker builder prune --filter "until=168h" -f

# Verify disk headroom
df -h /
```

---

## 3. PostgreSQL Database Maintenance

Run index re-indexing and statistical optimization inside the `luxe_postgres` container:

```bash
# Run VACUUM ANALYZE across all 41 tables
docker exec -t luxe_postgres psql -U luxe_app_user -d luxe_ecommerce -c "VACUUM (VERBOSE, ANALYZE);"

# Check database size on disk
docker exec -t luxe_postgres psql -U luxe_app_user -d luxe_ecommerce -c "
  SELECT pg_size_pretty(pg_database_size('luxe_ecommerce')) AS total_db_size;
"
```

---

## 4. Let's Encrypt SSL / TLS Renewal

Certificates for `mus-luxury.com`, `www.mus-luxury.com`, and `api.mus-luxury.com` are managed via Certbot / Nginx:

```bash
# Test dry-run renewal
certbot renew --dry-run

# Force manual renewal if needed
certbot renew --quiet --no-self-upgrade --post-hook "docker compose restart nginx"
```

---

## 5. Emergency Owner Password Reset

In the event that the administrative password is forgotten, do NOT attempt database updates directly. Use the server-side CLI tool:

```bash
docker exec -it luxe_api python3 scripts/emergency_reset_owner.py \
  --email admin@mus-luxury.com \
  --new-password "SecureOwnerPassword2026!"
```
This updates the PBKDF2 hash (600,000 iterations), invalidates all active sessions via `iat_ns`, and outputs an audit log entry.
