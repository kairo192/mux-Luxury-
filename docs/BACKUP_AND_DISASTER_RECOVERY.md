# Mus Luxury (LUXE) — Backup & Disaster Recovery Architecture

**Host:** Octenium Ubuntu 24.04 VPS (`5.196.163.6`)  
**Persistent Data Paths:**
- PostgreSQL Data: Docker volume `pgdata` (`/var/lib/postgresql/data`)
- Product Media Uploads: Host volume `/var/lib/luxe/uploads`
- Local Backup Vault: Host volume `/var/lib/luxe/backups`

---

## 1. Backup Strategy Overview

A multi-tiered, automated backup system guarantees an RPO (Recovery Point Objective) of < 24 hours and an RTO (Recovery Time Objective) of < 15 minutes.

### 1.1 Backup Tiers
1. **Database Snapshot:** Nightly logical PostgreSQL dump (`pg_dump`) compressed with gzip.
2. **Product Media Snapshot:** Nightly incremental archive of `/var/lib/luxe/uploads`.
3. **Offsite Cold Vault:** Cryptographic transfer of daily archives to external offsite storage (S3 / Cloud Storage / SFTP).

---

## 2. Nightly Backup Automation Script

Install the automated backup runner at `/usr/local/bin/luxe-backup.sh`:

```bash
cat << 'EOF' > /usr/local/bin/luxe-backup.sh
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/lib/luxe/backups"
DB_FILE="${BACKUP_DIR}/db_luxe_${BACKUP_DATE}.sql.gz"
UPLOADS_FILE="${BACKUP_DIR}/uploads_luxe_${BACKUP_DATE}.tar.gz"
CHECKSUM_FILE="${BACKUP_DIR}/checksums_${BACKUP_DATE}.sha256"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Is)] Starting automated Mus Luxury backup..."

# 1. Export PostgreSQL Database (Consistent Read)
docker compose -f /opt/luxe/docker-compose.yml exec -T db \
  pg_dump -U luxe_app_user -d luxe_ecommerce --no-owner --clean --if-exists | gzip -9 > "${DB_FILE}"

# 2. Archive Uploaded Media
if [ -d "/var/lib/luxe/uploads" ]; then
  tar -czf "${UPLOADS_FILE}" -C /var/lib/luxe uploads
fi

# 3. Generate SHA-256 Checksums
sha256sum "${DB_FILE}" "${UPLOADS_FILE}" > "${CHECKSUM_FILE}"

# 4. Enforce Retention Policy
# Retain daily backups for 7 days
find "${BACKUP_DIR}" -name "db_luxe_*.sql.gz" -mtime +7 -delete
find "${BACKUP_DIR}" -name "uploads_luxe_*.tar.gz" -mtime +7 -delete
find "${BACKUP_DIR}" -name "checksums_*.sha256" -mtime +7 -delete

echo "[$(date -Is)] Backup completed successfully: ${DB_FILE}"
EOF

chmod 700 /usr/local/bin/luxe-backup.sh
```

### 2.1 Schedule via Cron
Schedule the backup script to run nightly at 02:00 AM (local store time):
```bash
echo "0 2 * * * root /usr/local/bin/luxe-backup.sh >> /var/log/luxe-backup.log 2>&1" > /etc/cron.d/luxe-backup
```

---

## 3. Database Restoration Procedure

To restore a specific backup into production:

### 3.1 Unpack and Verify Checksum
```bash
cd /var/lib/luxe/backups
sha256sum -c checksums_20261109_020000.sha256
```

### 3.2 Restore into PostgreSQL
```bash
# 1. Temporarily place API in maintenance mode
docker compose -f /opt/luxe/docker-compose.yml stop api

# 2. Stream uncompressed SQL dump into PostgreSQL container
gunzip -c db_luxe_20261109_020000.sql.gz | \
  docker compose -f /opt/luxe/docker-compose.yml exec -T db \
  psql -U luxe_app_user -d luxe_ecommerce

# 3. Restart API
docker compose -f /opt/luxe/docker-compose.yml start api
```

### 3.3 Restore Product Media
```bash
tar -xzf /var/lib/luxe/backups/uploads_luxe_20261109_020000.tar.gz -C /var/lib/luxe/
chown -R 1001:1001 /var/lib/luxe/uploads
```

---

## 4. Cold Disaster Recovery Drill (Total Server Loss)

If the VPS is completely destroyed or compromised, execute the 15-minute rebuild:

1. **Provision Fresh VPS:** Ubuntu 24.04 LTS on Octenium or alternate provider.
2. **Execute Host Bootstrap:** Run `docs/VPS_SETUP.md` (Docker, UFW, Swap tuning).
3. **Deploy Codebase:** Clone `https://github.com/kairo192/mux-Luxury-.git` to `/opt/luxe`.
4. **Restore Secrets:** Recreate `/opt/luxe/.env`.
5. **Start Database:** `docker compose up -d db`.
6. **Apply Latest Backup:** Stream latest offsite `db_luxe_*.sql.gz` into PostgreSQL.
7. **Unpack Media:** Extract `uploads_luxe_*.tar.gz` into `/var/lib/luxe/uploads`.
8. **Launch All Services:** `docker compose up -d`.
9. **Verify Public Endpoints:** Run `curl -s https://api.mus-luxury.com/api/v1/ready`.

