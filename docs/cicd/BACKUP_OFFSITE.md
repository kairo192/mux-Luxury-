# Off-site backup & nightly verification

Nightly chain on the production VPS: **dump → upload → verify**. If any
link fails, cron writes a loud line to `/opt/luxe/logs/backup.log` that
Uptime Kuma scrapes. Backup you never test is not a backup; the verify
step is what makes this policy worth anything.

## Design

```
┌─────────────────────────────┐
│ backup_postgres_and_media.sh│  ← dump + optional AES-256 + sha256 + 30d retention
└──────────────┬──────────────┘
               │ && (stop on failure)
               ▼
┌─────────────────────────────┐
│ upload_to_offsite.sh        │  ← last backup set → S3 (rclone), prunes old copies
└──────────────┬──────────────┘
               │ && (upload failure still runs verify on what's on disk via ||)
               ▼
┌─────────────────────────────┐
│ verify_backup.sh            │  ← non-destructive restore to isolated sqlite/pg temp DB
└─────────────────────────────┘
```

All three live under `infrastructure/backups/`. The cron installer
(`install_backup_cron.sh`) wires them to `/etc/cron.d/luxe-backup`.

## Operator steps on the VPS

1. Pick S3-compatible storage. **Free 10 GB: Backblaze B2 or Cloudflare R2**
   (step by step for B2: `docs/OPERATIONS_GUIDE.md` §5.4). Paid: Wasabi,
   Scaleway, OVH, AWS, MinIO… Only the standard storage class is used.
   On B2, set the bucket lifecycle to *Keep only the last version* (deleted
   files are otherwise only hidden and still use space).

2. In `/opt/luxe/shared/.env`, set:

   ```
   S3_BACKUP_ENABLED=true
   S3_ENDPOINT_URL=https://s3.eu-central-003.backblazeb2.com
   S3_REGION=eu-central-003            # R2: auto
   S3_BUCKET_NAME=mus-luxury-backups
   S3_ACCESS_KEY_ID=...
   S3_SECRET_ACCESS_KEY=...
   # optional:
   S3_BUCKET_PREFIX=luxe
   OFFSITE_RETENTION_DAYS=30           # database copies; newest BACKUP_MEDIA_KEEP photo archives always kept
   ```

3. Tools (installed by `vps-bootstrap.sh`; on an older server):

   ```bash
   sudo apt-get install -y rclone sqlite3
   ```

   `rclone` sends the files (configured from the values above, no config
   file). `sqlite3` is for the verify step — it restores into a throwaway
   temp DB so the live PG is never touched.

   After each upload the script deletes, **in the bucket**, database files
   older than `OFFSITE_RETENTION_DAYS` and photo archives beyond the newest
   `BACKUP_MEDIA_KEEP`, so a free plan never fills up. A failed upload exits 2
   (cron alerts); a failed clean-up only warns. Test:
   `backend/tests/test_offsite_upload.py`.

4. Install the cron:

   ```bash
   sudo bash /opt/luxe/current/infrastructure/backups/install_backup_cron.sh
   ```

   This writes `/etc/cron.d/luxe-backup` with the schedule from
   `BACKUP_CRON_SCHEDULE` (default `30 2 * * *` = 02:30 UTC). Re-running
   is idempotent — overwriting the file is fine.

5. Fire a manual round to confirm wiring without waiting for the cron
   (reads the .env safely, then backup → off-site copy → verification):

   ```bash
   sudo bash /opt/luxe/current/infrastructure/backups/nightly_backup.sh
   ```

   Expected output ends with `OK — luxe_db_YYYYMMDD_HHMMSS.sql.gz.enc is
   verifiable`.

## Bucket lifecycle

Old copies are deleted **by the upload script itself** (see step 3), so no
lifecycle rule is needed to stop the bucket growing. Two provider settings
still matter:

- **Backblaze B2**: lifecycle *Keep only the last version of the file*.
  B2 keeps deleted files as hidden versions otherwise.
- **AWS S3 / others with versioning on**: leave versioning off, or add a
  rule that removes non-current versions after a few days.

## Monitoring integration

`nightly_backup.sh` prints `[nightly-backup] OK — backup, off-site copy and
verification done` only when **all three** steps succeeded (a failed upload
stops the chain). Monitor that, not the verify line alone:

- **Push monitor (recommended)**: create a Kuma *Push* monitor (heartbeat
  interval 25 h) and put its URL in `BACKUP_HEARTBEAT_URL` in
  `/opt/luxe/shared/.env`. The chain calls it only after a fully successful
  night; Kuma alerts when a night is missed or fails.
- **Keyword monitor**: on `/opt/luxe/logs/backup.log`, keyword
  `[nightly-backup] OK`, checked daily after the backup hour.

## Restore procedure (for the operator, DR)

The actual restore uses `infrastructure/backups/restore_backup.sh`. The
`verify_backup.sh` step is an automated rehearsal that proves the archive is
restorable; it does NOT touch the live DB. If a real restore is needed (on a
new server: same `S3_*` values in `/opt/luxe/shared/.env`, `rclone` installed):

1. List and download from the bucket with the same settings the upload uses:

   ```bash
   cd /opt/luxe/current
   sudo bash -c 'source infrastructure/scripts/env-file.sh && luxe_load_env /opt/luxe/shared/.env &&
     bash infrastructure/backups/upload_to_offsite.sh list'
   # e.g. <host>/2026/11/13/luxe_db_20261113_023000.sql.gz.enc   and   <host>/media/luxe_media_….tar.gz.enc
   sudo bash -c 'source infrastructure/scripts/env-file.sh && luxe_load_env /opt/luxe/shared/.env &&
     bash infrastructure/backups/upload_to_offsite.sh download <host>/2026/11/13/luxe_db_20261113_023000.sql.gz.enc'
   ```

   Files land in `BACKUP_DIR` (`/var/lib/luxe/backups`). For a restore from
   the CMS instead, download the `luxe_app_….json.gz.enc` of the same night.

2. Follow `docs/cicd/ROLLBACK.md` — it has the full restore-DB-and-flip
   procedure wired for the symlink release layout.

## What this chain does NOT do

- Point-in-time recovery below the 24h granularity. For sub-day RPO,
  add PG WAL archiving (out of scope for this VPS size).
- Cross-region replication — one bucket, one region. If the bucket's
  region has an outage, the only backup copy is the local one on the
  VPS disk.
- Customer media verification — the current chain verifies the DB dump.
  Media (`luxe_media_*.tar.gz.enc`) is uploaded once to `<host>/media/` but
  not restored during verify. A lost media archive is recoverable from
  the bucket; a corrupt one shows up as a 0-byte download at restore
  time.
