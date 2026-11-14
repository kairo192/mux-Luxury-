# Mus Luxury (LUXE) — Database Backup, Verification & Disaster Recovery

## 1. Backup Architecture & Policy
- ** Automated Schedule**: Daily cron execution of `infrastructure/backups/backup_postgres_and_media.sh` at `02:30 Africa/Algiers`, plus on-demand manual backups from Tab 8 (`8. Sauvegardes & Sécurité`) via `POST /api/v1/admin/backups`.
- **Storage Location & Access Control**:
  - Production Docker Volume: `/var/lib/luxe/backups` (owned by non-root `luxeuser` UID `1001`, mode `0750`, never exposed via Nginx).
  - Integrity Verification: Every backup computes and records a cryptographic `sha256_checksum` and `size_bytes` in the `backup_records` table.
- **Retention Policy**: 30 daily snapshots + 12 monthly snapshots.
- **Recovery Objectives**:
  - **RPO (Recovery Point Objective)**: `24 hours` for scheduled daily backups; `0 hours` when triggering a manual pre-change backup in Tab 8 before bulk catalog edits.
  - **RTO (Recovery Time Objective)**: `< 15 minutes` using `infrastructure/backups/restore_backup.sh`.

## 2. Non-Destructive Isolated Restore Verification (`POST /api/v1/admin/backups/{id}/verify-restore`)
A backup is never marked verified until restoration succeeds:
1. The server reads the `.sql.gz` archive from `BACKUP_STORAGE_DIR` and recomputes its SHA-256 digest against `backup_records.sha256_checksum`.
2. Decompresses the SQL dump into an isolated temporary SQLite database (`tempfile.NamedTemporaryFile`).
3. Queries `products`, `categories`, `orders`, and `delivery_zones` (`69` Wilayas) inside the restored database to confirm structural and data integrity without touching live production data (`test_26`).
