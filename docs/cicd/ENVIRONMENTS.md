# Environments

Three environments, strictly isolated. No environment reads another's
database, `.env`, or storage.

| Env         | Where                                | Deploys on                     | Data            |
| ----------- | ------------------------------------ | ------------------------------ | --------------- |
| development | `docker compose up` on your machine  | manually                       | Synthetic seed  |
| staging     | Dedicated 2 GB VPS                   | Every push to `main` (auto)    | Synthetic seed  |
| production  | Dedicated 2 GB VPS                   | `v*` tag + approval            | Real customers  |

## Hard rules

1. **No shared databases.** Staging never connects to the production Postgres
   instance, even read-only. Testing a migration on staging data is only
   meaningful if staging data looks like production — see "Refreshing
   staging" below.
2. **No shared secrets.** Each environment has its own `SECRET_KEY`,
   `CMS_HMAC_SIGNING_SECRET`, `BACKUP_ENCRYPTION_KEY`, DB password, and
   third-party tokens. Rotate independently.
3. **Staging uses sandbox tokens** for WhatsApp, Chargily, SMS couriers.
   Point them at provider sandboxes — a mis-sent SMS from staging is
   embarrassing and bills real money.
4. **The .env file never travels through git.** It lives at
   `/opt/luxe/shared/.env` on the VPS, created there once by hand (see
   `VPS_PREPARATION.md`).

## Refreshing staging from production (safely)

When a migration or a reporting feature needs realistic data to test, dump
production and re-import on staging with PII redacted:

```bash
# On production:
pg_dump "$DATABASE_URL" | gzip > /tmp/prod.sql.gz

# On your workstation:
scp luxe@<prod>:/tmp/prod.sql.gz .
gunzip -c prod.sql.gz \
  | python infrastructure/scripts/scrub_pii.py \
  > scrubbed.sql
scp scrubbed.sql luxe@<staging>:/tmp/

# On staging:
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < /tmp/scrubbed.sql
```

> `infrastructure/scripts/scrub_pii.py` is not part of this repository yet.
> If you need it, write it to redact `customers.phone`, `customers.email`,
> `orders.ship_address`, `admin_users.email` and any WhatsApp numbers before
> uploading anything to staging.

## Why these numbers

The production VPS runs very close to its memory ceiling (Postgres is
tuned for ~400 MB working set; FastAPI holds ~150 MB; Nginx is negligible).
Keeping staging on a separate VPS is non-negotiable not for safety reasons
alone — a staging migration run simultaneously with production traffic on
the same box would OOM-kill Postgres.
