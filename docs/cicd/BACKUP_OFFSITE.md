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
│ upload_to_offsite.sh        │  ← picks newest timestamp, S3 STANDARD_IA
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

1. Pick an S3-compatible bucket. Any of AWS S3, Wasabi, Backblaze B2,
   Scaleway Object Storage, Hetzner, DigitalOcean Spaces, or self-hosted
   MinIO works — we only use the S3 HTTP API.

2. In `/opt/luxe/shared/.env`, set:

   ```
   S3_BACKUP_ENABLED=true
   S3_ENDPOINT_URL=https://s3.eu-west-3.amazonaws.com
   S3_REGION=eu-west-3
   S3_BUCKET_NAME=mus-luxury-backups
   S3_ACCESS_KEY_ID=...
   S3_SECRET_ACCESS_KEY=...
   # optional:
   S3_BUCKET_PREFIX=db-nightly
   OFFSITE_RETENTION_DAYS=90
   ```

3. Install the `aws` CLI (~30 MB, apt is fine):

   ```bash
   sudo apt-get install -y awscli sqlite3
   ```

   `sqlite3` is for the verify step — it restores into a throwaway temp
   DB so the live PG is never touched.

4. Install the cron:

   ```bash
   sudo bash /opt/luxe/current/infrastructure/backups/install_backup_cron.sh
   ```

   This writes `/etc/cron.d/luxe-backup` with the schedule from
   `BACKUP_CRON_SCHEDULE` (default `30 2 * * *` = 02:30 UTC). Re-running
   is idempotent — overwriting the file is fine.

5. Fire a manual round to confirm wiring without waiting for the cron:

   ```bash
   sudo -u luxe bash -lc '
     set -a; . /opt/luxe/shared/.env; set +a
     cd /opt/luxe/current
     bash infrastructure/backups/backup_postgres_and_media.sh
     bash infrastructure/backups/upload_to_offsite.sh
     bash infrastructure/backups/verify_backup.sh
   '
   ```

   Expected output ends with `OK — luxe_db_YYYYMMDD_HHMMSS.sql.gz.enc is
   verifiable`.

## Bucket lifecycle (configure once, outside this repo)

`upload_to_offsite.sh` writes objects with storage class
`STANDARD_IA`. The bucket **must** have a lifecycle rule to expire
them after `OFFSITE_RETENTION_DAYS`; the CLI cannot set the lifecycle
from the host, so the owner configures it in the provider's console
once per bucket:

- **AWS S3**: Bucket → Management → Lifecycle rules → create rule →
  filter by prefix `db-nightly/`, action "Expire current versions" at
  90 days.
- **Wasabi / B2**: equivalent "Delete after N days" lifecycle rule in
  their console.
- **MinIO self-hosted**: `mc ilm add` command.

Without the lifecycle, archives accumulate in the bucket and the owner
pays storage forever.

## Monitoring integration

Uptime Kuma already monitors the shop (see
`infrastructure/monitoring/docker-compose.monitoring.yml`). Point it
at the backup log with a "Keyword" monitor:

- URL: `file:///opt/luxe/logs/backup.log` (if the Kuma container
  bind-mounts `/opt/luxe/logs`) OR a lightweight `curl`-based pull.
- Keyword: `verify-backup] OK` (positive match).
- Interval: 24h, after the scheduled backup hour.

Alternative: emit a "heartbeat" to a Kuma push monitor at the end of
`verify_backup.sh`. Add this line at the bottom of the script:

```bash
# curl -fsS --max-time 10 "https://kuma.example.com/api/push/<token>?status=up&msg=OK" >/dev/null || true
```

The line is commented out in the shipped script because the push token
is per-shop and must not be committed.

## Restore procedure (for the operator, DR)

The actual restore uses `infrastructure/backups/restore_backup.sh`
(already in the repo). The `verify_backup.sh` step is an automated
rehearsal that proves the archive is restorable; it does NOT touch the
live DB. If a real restore is needed:

1. Download the archive from the bucket:

   ```bash
   aws --endpoint-url "$S3_ENDPOINT_URL" \
       s3 cp s3://mus-luxury-backups/db-nightly/<host>/<YYYY/MM/DD>/luxe_db_<ts>.sql.gz.enc \
       /var/lib/luxe/backups/
   ```

2. Follow `docs/cicd/ROLLBACK.md` — it has the full restore-DB-and-flip
   procedure wired for the symlink release layout.

## What this chain does NOT do

- Point-in-time recovery below the 24h granularity. For sub-day RPO,
  add PG WAL archiving (out of scope for this VPS size).
- Cross-region replication — one bucket, one region. If the bucket's
  region has an outage, the only backup copy is the local one on the
  VPS disk.
- Customer media verification — the current chain verifies the DB dump.
  Media (`luxe_media_*.tar.gz*`) is uploaded with the same prefix but
  not restored during verify. A lost media archive is recoverable from
  the bucket; a corrupt one shows up as a 0-byte download at restore
  time.
