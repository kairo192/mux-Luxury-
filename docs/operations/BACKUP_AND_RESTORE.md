# Mus Luxury (`LUXE`) — Backup, Disaster Recovery & Restoration Runbook

## 1. Backup Strategy Overview

Given the 40 GB NVMe disk capacity on the Octenium VPS, backups are designed to be lightweight, compressed, non-blocking, and isolated.

```text
               CRON (Daily 03:00 UTC)
                         │
                         ▼
          ┌─────────────────────────────┐
          │ backup_postgres_and_media.sh│
          └──────────────┬──────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ 1. PostgreSQL Database  │     │ 2. Product Media        │
│ pg_dump --clean         │     │ tar -czf uploads.tar.gz │
│ gzip -> .sql.gz         │     │ Product images/visuals  │
│ SHA-256 Checksum file   │     │                         │
└──────────────┬──────────┘     └───────────┬─────────────┘
               │                            │
               └──────────────┬─────────────┘
                              ▼
               ┌─────────────────────────────┐
               │ /var/backups/luxe/          │
               │ (chmod 0700, 7-day retention│
               └──────────────┬──────────────┘
                              ▼
               ┌─────────────────────────────┐
               │ Offsite S3 / Cold Storage   │
               │ (Optional sync via rclone)  │
               └─────────────────────────────┘
```

---

## 2. Automated Daily Backup Execution

The backup script lives at `infrastructure/backups/backup_postgres_and_media.sh`. It runs non-interactively and executes atomic dumps:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/luxe"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_BACKUP_FILE="${BACKUP_DIR}/luxe_db_${TIMESTAMP}.sql.gz"
MEDIA_BACKUP_FILE="${BACKUP_DIR}/luxe_media_${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"
chmod 0700 "${BACKUP_DIR}"

# 1. Dump PostgreSQL from running container
docker exec -t luxe_postgres pg_dump -U luxe_app_user -d luxe_ecommerce --clean --if-exists | gzip > "${DB_BACKUP_FILE}"

# 2. Compute SHA-256 integrity hash
sha256sum "${DB_BACKUP_FILE}" > "${DB_BACKUP_FILE}.sha256"

# 3. Archive uploaded product media
tar -czf "${MEDIA_BACKUP_FILE}" -C /var/lib/docker/volumes/luxe-ecommerce_luxe_uploads/_data .

# 4. Enforce 7-Day Retention (Delete older archives)
find "${BACKUP_DIR}" -type f -name "luxe_db_*.sql.gz*" -mtime +7 -delete
find "${BACKUP_DIR}" -type f -name "luxe_media_*.tar.gz" -mtime +7 -delete
```

### Scheduling via System Crontab:
```bash
# Add to /etc/crontab:
0 3 * * * root /var/www/luxe-ecommerce/infrastructure/backups/backup_postgres_and_media.sh >> /var/log/luxe-backup.log 2>&1
```

---

## 3. Disaster Recovery & Database Restoration

To restore a backup into production (or an isolated recovery database):

```bash
# 1. Verify archive integrity
cd /var/backups/luxe
sha256sum -c luxe_db_20261110_030000.sql.gz.sha256

# 2. Stop frontend to prevent concurrent transactions during restore
docker compose stop api storefront

# 3. Restore PostgreSQL database
gunzip -c luxe_db_20261110_030000.sql.gz | docker exec -i luxe_postgres psql -U luxe_app_user -d luxe_ecommerce

# 4. Restore Media Files
tar -xzf luxe_media_20261110_030000.tar.gz -C /var/lib/docker/volumes/luxe-ecommerce_luxe_uploads/_data/

# 5. Restart services and verify health
docker compose start api storefront
curl -f http://127.0.0.1:8000/api/v1/health
```

---

## 4. Desktop POS Local Database Recovery

The Desktop CMS utilizes an independent embedded SQLite database at `%APPDATA%\com.musluxury.cms\pos_mirror.sqlite3`.

- **Crash Recovery:** SQLite WAL (Write-Ahead Logging) is enabled by default. If the Windows POS machine experiences a sudden power loss, uncommitted transactions roll back cleanly upon the next app startup.
- **Queue Protection:** Queued offline transactions are stored in durable SQLite tables until the central API confirms receipt with an HTTP `200` response.

