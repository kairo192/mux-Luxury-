# Versioned migrations

Every schema change lands here as a new, numbered SQL file. The migration
runner (`python -m app.migration_runner up`) applies files in order and records
them in the `schema_migrations` table.

## File naming

```
NNN_short_slug.sql                 # runs on both PostgreSQL and SQLite
NNN_short_slug.postgres.sql        # runs only on PostgreSQL
NNN_short_slug.sqlite.sql          # runs only on SQLite
```

- `NNN` is a monotonically increasing 3-digit integer (`002`, `003`, …).
- `001_initial_schema*.sql` in the parent directory is the baseline; the
  runner records it as version `000` automatically on first run.

## Forward-compatible only

The runner refuses to apply files containing `DROP TABLE`, `DROP COLUMN` or
`TRUNCATE` — those break running pods during a rolling deploy and have no safe
rollback. Model a destructive change as two releases:

1. **Expand** — add the new nullable column / new table / new index. Deploy.
2. **Contract** — in a *later* release, once all code paths are migrated,
   remove the old column / table in a separate migration.

Backups (`infrastructure/backups/backup_postgres_and_media.sh`) are the
recovery path if a migration goes wrong. A migration has no "down" file.

## CLI

```
python -m app.migration_runner validate   # static check of all files
python -m app.migration_runner status     # applied vs pending (JSON)
python -m app.migration_runner dry-run    # show what up would do
python -m app.migration_runner up         # apply pending
```

PostgreSQL runs take a session-level `pg_advisory_lock`, so two runners
(deploy + app boot) cannot race. Each file runs in its own transaction.
