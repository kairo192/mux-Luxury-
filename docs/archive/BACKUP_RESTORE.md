# BACKUP & DISASTER RECOVERY GUIDE — MUS LUXURY (`LUXE`)

---

## 1. Backup Scope & Storage Architecture

The **Mus Luxury (`LUXE`)** platform protects four categories of persistent business data:
1. **Relational Database Records**: Categories, dynamic attributes, products, variants, inventory movements, 69-Wilaya delivery zones & tariffs, guest customers, orders, order items, coupons, admin users, and audit logs.
2. **Uploaded Media Assets**: Product and category images stored under `/uploads/` and `/assets/`.
3. **Store Configuration**: `store_settings`, `homepage_sections`, and `banners`.
4. **Cryptographic Integrity Metadata**: Every backup record in `backup_records` stores the exact `filename`, `size_bytes`, and `sha256_checksum` computed over the compressed archive bytes.

---

## 2. Manual & Automated Backup Mechanisms

### A. On-Demand Encrypted/Compressed Backup via Desktop CMS (`POST /api/v1/admin/backups`)
- Restricted to administrators with the `backups:write` permission (`super_admin`).
- Executes a full SQL dump (`conn.iterdump()`), compresses it with `gzip` into `backend/backups/luxe_backup_<timestamp>_<random>.sql.gz`, computes the **SHA-256** digest over the `.sql.gz` bytes, writes the file to disk, and records the metadata row in `backup_records`.

### B. Production VPS Shell Backup (`infrastructure/backups/backup_postgres_and_media.sh`)
- On a production Linux VPS running PostgreSQL 16, cron invokes `infrastructure/backups/backup_postgres_and_media.sh` daily at `02:30 Africa/Algiers` to dump PostgreSQL (`pg_dump -Fc`), archive uploaded media, compute SHA-256 checksums, and prune archives older than the 30-day retention window.
- **Important Operational Note**: Automated scheduled backups require an active cron daemon or systemd timer on the target Linux VPS. In local/containerized environments without cron enabled, administrators must trigger manual backups via the Desktop CMS (`Tab 8: Sauvegardes & Restauration`).

---

## 3. Non-Destructive Isolated Restoration Verification (`POST /api/v1/admin/backups/{id}/verify-restore`)

A backup is only trustworthy when restoration has been tested. To guarantee that restoration testing **never** overwrites or corrupts the live database:
1. Calling `POST /api/v1/admin/backups/{backup_id}/verify-restore` reads the `.sql.gz` archive from `backend/backups/`.
2. It recomputes the `SHA-256` hash of the file on disk and compares it in constant time (`hmac.compare_digest`) against `backup_records.sha256_checksum`.
3. It decompresses the SQL script and restores it into a fresh, isolated temporary SQLite database inside `tempfile.TemporaryDirectory()`.
4. It queries the restored database tables (`products`, `categories`, `orders`, `delivery_zones`) to verify that all records are readable and intact, logs the verification in `audit_logs`, and automatically cleans up the temporary directory.
5. **Verified by Automated Test**: `test_26_isolated_backup_creation_and_non_destructive_restore_verification` in `backend/tests/test_luxe_api.py`.

---

## 4. Full Production Disaster Recovery Procedure

To restore a production PostgreSQL + Media backup onto a fresh server:
1. Stop the FastAPI worker service (`systemctl stop luxe-backend` or `docker compose stop backend`) so no new orders are written during restoration.
2. Verify the backup archive checksum:
   ```bash
   sha256sum -cuxe_backup_<timestamp>.sql.gz.sha256
   ```
3. Run the restoration script against the target database:
   ```bash
   ./infrastructure/backups/restore_backup.sh /var/backups/luxe/luxe_backup_<timestamp>.sql.gz
   ```
4. Restart the FastAPI service (`docker compose start backend`) and verify `/api/v1/admin/dashboard` health.
