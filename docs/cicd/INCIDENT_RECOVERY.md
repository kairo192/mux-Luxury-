# Incident recovery

A short checklist, in order of severity. The order matters: the first thing
to do during a storefront outage is restore service, not diagnose.

## 1. Storefront returns 5xx / nothing loads

```bash
ssh luxe@<vps>
cd /opt/luxe/current
docker compose ps                                  # which container is down?
docker compose logs --tail=200 api nginx storefront
```

Common first suspects:

- Out of memory → `free -h`, `docker stats --no-stream`. If so, `docker
  compose restart api` and consider increasing swap (`VPS_PREPARATION.md`).
- Disk full → `df -h`. Prune old release directories (`ls -1dt
  /opt/luxe/releases | tail -n +6 | xargs rm -rf`) and old Docker images
  (`docker image prune -af`).
- Postgres lost → `docker compose logs db | tail`. If the DB container is
  looping on "database already exists" or similar, restore the latest
  backup (see `ROLLBACK.md`).

Restore service first (rollback or restart), *then* investigate.

## 2. Deploy failed

Read `/opt/luxe/logs/deploy.log`. If release-deploy.sh exited non-zero but
auto-rollback succeeded, you're already on the previous release. If it
failed before the swap, the previous release is still `current` and the new
one is in `releases/<version>/` ready for inspection.

The whole deploy is idempotent — fixing the issue in a new commit and
re-running the CD workflow is always safe.

## 3. Migration failed

`release-deploy.sh` runs migrations *before* swapping the symlink. If it
failed, the old release is still live. Two paths:

- **The migration partially applied.** Inspect `schema_migrations` — if the
  failing migration is recorded, data was already modified. Restore the
  pre-migration backup (`ROLLBACK.md`), then ship a corrected migration.
- **The migration did not apply at all.** Just fix and re-deploy.

## 4. The VPS is unreachable

If SSH itself times out:

1. Check the hosting panel — is the VM up? Rebooting from the panel is the
   nuclear option but sometimes necessary.
2. Check that your IP isn't in the UFW/fail2ban blocklist. The hosting
   panel's "VNC console" (serial) can get you in and run:
   ```bash
   sudo fail2ban-client unban <your-ip>
   ```
3. If the VM is up but SSH won't accept your key: VNC in as root, verify
   `/home/luxe/.ssh/authorized_keys` still contains your key and has
   permissions 0600 owned by luxe:luxe.

While SSH is down, no deploy and no backup can happen. If this lasts more
than 30 minutes, boot a spare VPS from the latest off-site backup
(`../OPERATIONS_GUIDE.md` §5.4, "Getting a copy back") and change DNS.

## 5. Data corruption / bad write

1. Freeze writes: `docker compose stop api` (storefront can keep reading
   the public Nginx cache for a few minutes).
2. Take an emergency backup: `bash infrastructure/backups/backup_postgres_and_media.sh`.
3. Identify the window of corruption from application logs.
4. Restore the newest pre-corruption backup. The backup dumps are
   plain `pg_dump` compressed SQL; selective restores (one table) are
   possible with `pg_restore --table=...` after you `gunzip` the archive.

## 6. Secret leak

1. **Rotate**, then audit the blast radius. See `SECRETS.md § Accidentally
   committed a secret?`.
2. Invalidate the compromised credential at the provider (WhatsApp token,
   S3 key, admin password).
3. Update `/opt/luxe/shared/.env` and `docker compose up -d` to reload.

## Writing an incident note

For anything worse than a one-minute blip, open `docs/incidents/YYYY-MM-DD-slug.md`:

```
## What happened
## Timeline (UTC)
## Impact
## Root cause
## Fix
## Action items
```

One or two lines per section is fine. The point is to make the same
mistake once.
