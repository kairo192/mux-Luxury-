# Database migrations

Forward-only, numbered SQL files applied by `app.migration_runner`. One
migration per PR. The runner:

1. Creates `schema_migrations(version, filename, checksum, applied_at, duration_ms)`.
2. Discovers files in `backend/migrations/versions/NNN_<slug>[.postgres|.sqlite].sql`.
3. For each file not yet recorded, takes a Postgres advisory lock (serialises
   concurrent runners), runs the SQL in its own transaction, records the
   result, commits, releases the lock.

## Golden rules

1. **Nothing destructive.** `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` are
   refused by the validator. Remove things in a *later* release via the
   expand/contract pattern.
2. **Nullable by default.** New non-nullable columns need an explicit
   default so existing rows don't fail NOT NULL.
3. **Backfill in the app, not in the migration.** Long UPDATE statements
   hold table locks; a one-row-at-a-time backfill that runs on a background
   task is safer.
4. **Index creation uses `CREATE INDEX CONCURRENTLY`** on Postgres. SQLite
   doesn't need it.
5. **Keep migrations short.** A migration that takes more than 30 s is
   probably doing something a backfill job should do.

## Expand/contract

Suppose you want to rename `customers.phone` → `customers.msisdn`.

1. **Expand release** — `003_add_msisdn_column.sql`
   ```sql
   ALTER TABLE customers ADD COLUMN msisdn TEXT;
   -- Both app versions can read .phone and write .msisdn
   ```
   Deploy. Verify the next release of the app reads `msisdn` with a fallback
   to `phone`.

2. **Backfill** — one-off job
   ```sql
   UPDATE customers SET msisdn = phone WHERE msisdn IS NULL;
   ```
   Done in batches from a Python script, not a migration.

3. **Contract release** — `010_drop_customers_phone.sql`
   Never ship this until you're *sure* no code still reads `.phone`. Even
   then, consider leaving the column — the storage cost is zero and the
   ability to roll back to the previous app binary is priceless.

## File names

```
002_schema_migrations_tracking.sql       # applies to both engines
003_add_pos_version.postgres.sql         # applies only to Postgres
003_add_pos_version.sqlite.sql           # applies only to SQLite
```

Number sequentially. Never renumber or rewrite an applied file — the runner
would notice the checksum change, but the safe thing is to just land a new
file that undoes or amends the bad one.

## Commands

```bash
python -m app.migration_runner validate     # static check (CI runs this)
python -m app.migration_runner status       # JSON report of applied + pending
python -m app.migration_runner dry-run      # show what up would apply
python -m app.migration_runner up           # apply pending migrations
```

`release-deploy.sh` invokes `up` inside the new release's container BEFORE
swapping the `current` symlink. If migration fails, the symlink stays on the
old release and the deploy aborts.

## Recovery

A migration that applied but produced bad data: restore the pre-migration
backup (`restore_backup.sh`) and then ship a corrective migration. The
pre-migration backup is always the newest file in `/var/lib/luxe/backups/`
because `release-deploy.sh` runs the backup right before migrating.
