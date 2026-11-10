# Mus Luxury (LUXE) — PostgreSQL 16 Database Maintenance Guide

**Engine:** PostgreSQL 16 Alpine in Docker (`luxe_postgres`)  
**Database Name:** `luxe_ecommerce`  
**Application User:** `luxe_app_user`  
**Host Target:** Octenium 2 GB RAM VPS

---

## 1. Routine Maintenance & Autovacuum

PostgreSQL uses Multiversion Concurrency Control (MVCC). When orders, stock items, or cart sessions are updated, dead rows accumulate and must be vacuumed to prevent table bloat and disk expansion.

### 1.1 Autovacuum Configuration
PostgreSQL is configured with proactive autovacuum defaults. On a small server with e-commerce write traffic, table bloat is minimized:

```sql
-- Check autovacuum worker activity
SELECT pid, phase, autovacuum_mode, relation::regclass FROM pg_stat_progress_vacuum;
```

### 1.2 Weekly Routine Vacuum & Analyze
Schedule a weekly `VACUUM ANALYZE` during off-peak hours (Sunday 03:00 AM):

```bash
docker compose -f /opt/luxe/docker-compose.yml exec -T db \
  psql -U luxe_app_user -d luxe_ecommerce -c "VACUUM ANALYZE;"
```

---

## 2. Index Health & Query Optimization

### 2.1 Identify Bloated or Duplicate Indexes
Run the following query to inspect index utilization:
```sql
SELECT
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS number_of_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```
Indexes with `number_of_scans = 0` after 30 days of production operation should be reviewed for removal.

### 2.2 Reindexing Heavy Tables
Under heavy retail barcode scanning and stock count updates, indexes on `product_variants` and `inventory_movements` should be periodically reindexed without locking writes:

```sql
REINDEX TABLE CONCURRENTLY product_variants;
REINDEX TABLE CONCURRENTLY inventory_movements;
REINDEX TABLE CONCURRENTLY orders;
```

---

## 3. Schema Evolution & Migration Runner

All database schema evolutions must be declarative and additive.

### 3.1 Migration File Organization
Migrations reside in `backend/migrations/`:
- `001_initial_schema.sql`: Canonical baseline schema (SQLite syntax).
- `001_initial_schema_postgres.sql`: PostgreSQL 16 equivalent schema.

### 3.2 Running Migrations
The automated runner (`backend/app/migration_runner.py`) connects to the active database engine, verifies existing columns via `information_schema.columns`, and safely applies non-destructive additions:

```bash
docker compose exec -T api python3 -m app.migration_runner
```

### 3.3 Additive Column Evolution Rules
Never drop columns or change types in production. Always add columns as nullable or with safe defaults:
```sql
ALTER TABLE product_variants ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER NOT NULL DEFAULT 3;
```

