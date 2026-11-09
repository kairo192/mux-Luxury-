# Rollback

Deploys are atomic at the symlink level; application rollback is
near-instant. Database rollback is **not** symmetric with app rollback —
read the "Database" section before you consider it.

## Automatic rollback

`release-deploy.sh` performs a rollback automatically when the post-swap
health probe fails (default: `GET /api/v1/health` for 120 s). It flips the
symlink back, restarts docker compose, and exits non-zero. No action needed
from the operator.

## Manual rollback — application only

```bash
ssh luxe@<vps>
cd /opt/luxe
ls -1dt releases/*                             # see what's on disk

bash current/infrastructure/scripts/rollback.sh                       # one step back
bash current/infrastructure/scripts/rollback.sh --to 2026.11.07-abcdef1  # explicit
```

`rollback.sh` logs to `/opt/luxe/logs/rollback.log`. On success the previous
release is now `current`; the containers restart with its code and its
`docker-compose.yml`.

## Database

The migration runner is forward-only. Rolling the symlink back does **not**
roll the schema back. Three scenarios:

1. **The new release only adds nullable columns and new tables** (expand
   phase of expand/contract). The old release's code simply doesn't use
   the new columns — nothing breaks. This is the default and the reason
   we ban destructive migrations.
2. **The new release's code depends on the new schema**, but the schema
   itself is additive. Rolling back means the new fields are ignored;
   features that need them stop working, but no data is lost.
3. **The new release ran a backfill that rewrote existing rows.** Rolling
   the schema back from here is destructive. Restore the pre-migration
   backup instead (see below). The backfill was supposed to be reversible
   — see `MIGRATIONS.md` for how to write it that way.

## Restoring a pre-migration backup

Every `release-deploy.sh` run takes an encrypted DB + media backup *before*
touching the database. The archive is in `/var/lib/luxe/backups/` and
timestamped — pick the newest `luxe_db_YYYYMMDD_HHMMSS.sql.gz.enc` that
pre-dates the bad deploy:

```bash
ssh luxe@<vps>
cd /opt/luxe/current
docker compose stop api storefront       # stop app traffic
BACKUP_ENCRYPTION_KEY=$(grep ^BACKUP_ENCRYPTION_KEY /opt/luxe/shared/.env | cut -d= -f2-) \
  bash infrastructure/backups/restore_backup.sh \
    /var/lib/luxe/backups/luxe_db_YYYYMMDD_HHMMSS.sql.gz.enc \
    /var/lib/luxe/backups/luxe_backup_YYYYMMDD_HHMMSS.sha256 \
    --force
bash infrastructure/scripts/rollback.sh --to <previous-release>
docker compose up -d
```

Expect ~30 s of downtime while Postgres is restored. Media (uploads) can be
restored separately from the matching `luxe_media_*.tar.gz*` archive.

## After any rollback

1. Open an incident note in `docs/incidents/` (one file per event).
2. Capture `/opt/luxe/logs/deploy.log` and `/opt/luxe/logs/rollback.log` into
   the note.
3. Open a PR that either reverts the bad commit or adds a regression test
   that would have caught it.
