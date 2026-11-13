"""Forward-only versioned-migration runner (PostgreSQL + SQLite).

Discovers files in ``backend/migrations/versions/NNN_<slug>[.postgres|.sqlite].sql``
and applies the ones not yet present in ``schema_migrations``. Each file runs in
its own transaction; on PostgreSQL a session-level advisory lock serialises
concurrent runners (deploy + another deploy, or app boot + CI).

The runner is intentionally minimal — no Python migrations, no down-migrations
(the project uses forward-compatible schema changes + backups for recovery).
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.database import (
    SCHEMA_PATH,
    PG_SCHEMA_PATH,
    PostgresCompatConnection,
    get_connection,
)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations", "versions")
ADVISORY_LOCK_KEY = 7430297142  # arbitrary stable int for pg_advisory_lock

VERSION_RE = re.compile(r"^(\d{3,4})_([a-z0-9][a-z0-9_]*?)(?:\.(postgres|sqlite))?\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    slug: str
    dialect: Optional[str]  # "postgres", "sqlite", or None (both)
    path: str

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def body(self) -> str:
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def checksum(self) -> str:
        return hashlib.sha256(self.body().encode("utf-8")).hexdigest()


def discover_migrations() -> List[Migration]:
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    found: List[Migration] = []
    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        m = VERSION_RE.match(name)
        if not m:
            continue
        found.append(
            Migration(
                version=m.group(1),
                slug=m.group(2),
                dialect=m.group(3),
                path=os.path.join(MIGRATIONS_DIR, name),
            )
        )
    found.sort(key=lambda x: (x.version, x.dialect or ""))
    return found


def applicable(migrations: Iterable[Migration], is_postgres: bool) -> List[Migration]:
    want = "postgres" if is_postgres else "sqlite"
    out: List[Migration] = []
    for mig in migrations:
        if mig.dialect is None or mig.dialect == want:
            out.append(mig)
    return out


def _ensure_tracking_table(conn, is_postgres: bool) -> None:
    if is_postgres:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                checksum    TEXT NOT NULL,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                duration_ms INTEGER NOT NULL DEFAULT 0
            );
            """
        )
    else:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                checksum    TEXT NOT NULL,
                applied_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER NOT NULL DEFAULT 0
            );
            """
        )
    conn.commit()


def _applied_versions(conn) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT version, checksum, filename FROM schema_migrations")
    return {row[0] if not isinstance(row, dict) else row["version"]:
            {"checksum": (row[1] if not isinstance(row, dict) else row["checksum"]),
             "filename": (row[2] if not isinstance(row, dict) else row["filename"])}
            for row in cur.fetchall()}


def _acquire_pg_lock(conn) -> None:
    conn.execute(f"SELECT pg_advisory_lock({ADVISORY_LOCK_KEY})", ())


def _release_pg_lock(conn) -> None:
    try:
        conn.execute(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_KEY})", ())
    except Exception:
        pass


def _apply_one(conn, mig: Migration, is_postgres: bool) -> int:
    started = time.time()
    body = mig.body()
    if is_postgres:
        conn.executescript(body)
        conn.execute(
            "INSERT INTO schema_migrations (version, filename, checksum, duration_ms) "
            "VALUES (%s, %s, %s, %s)",
            (mig.version, mig.filename, mig.checksum(),
             int((time.time() - started) * 1000)),
        )
    else:
        conn.executescript(body)
        conn.execute(
            "INSERT INTO schema_migrations (version, filename, checksum, duration_ms) "
            "VALUES (?, ?, ?, ?)",
            (mig.version, mig.filename, mig.checksum(),
             int((time.time() - started) * 1000)),
        )
    conn.commit()
    return int((time.time() - started) * 1000)


def ensure_baseline(conn, is_postgres: bool) -> None:
    """If an older schema (001 initial) was applied before this runner existed,
    mark the baseline as applied so we don't try to re-run it."""
    cur = conn.cursor()
    _ensure_tracking_table(conn, is_postgres)
    # Done once the baseline record exists — not merely the tracking table: a
    # first start interrupted while creating the base tables must be able to
    # finish on the next start.
    cur.execute("SELECT 1 FROM schema_migrations WHERE version = '000'")
    if cur.fetchone():
        return
    schema_path = PG_SCHEMA_PATH if is_postgres else SCHEMA_PATH
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            body = f.read()
        checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
    except OSError:
        return
    # A new (or half-created) database: create the missing base tables first,
    # otherwise every later migration fails on a missing table. The base
    # schema only uses CREATE ... IF NOT EXISTS, so running it again is safe.
    base_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", body, re.IGNORECASE))
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        if is_postgres else
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    existing = {(r[0] if not isinstance(r, dict) else next(iter(r.values()))) for r in cur.fetchall()}
    if base_tables - existing:
        conn.executescript(body)
    if is_postgres:
        conn.execute(
            "INSERT INTO schema_migrations (version, filename, checksum) "
            "VALUES (%s, %s, %s) ON CONFLICT (version) DO NOTHING",
            ("000", "001_initial_schema_postgres.sql", checksum),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, filename, checksum) "
            "VALUES (?, ?, ?)",
            ("000", "001_initial_schema.sql", checksum),
        )
    conn.commit()


def run(dry_run: bool = False) -> List[str]:
    """Apply any pending migrations. Returns the list of filenames applied
    (or that would be applied in dry-run mode)."""
    conn = get_connection()
    is_postgres = isinstance(conn, PostgresCompatConnection)
    applied_now: List[str] = []
    try:
        if is_postgres:
            _acquire_pg_lock(conn)
        ensure_baseline(conn, is_postgres)
        _ensure_tracking_table(conn, is_postgres)
        already = _applied_versions(conn)
        pending = [m for m in applicable(discover_migrations(), is_postgres)
                   if m.version not in already]
        for mig in pending:
            if dry_run:
                applied_now.append(mig.filename)
                continue
            _apply_one(conn, mig, is_postgres)
            applied_now.append(mig.filename)
    finally:
        if is_postgres:
            _release_pg_lock(conn)
        conn.close()
    return applied_now


def validate() -> List[str]:
    """Parse-only validation of every migration file. Returns a list of errors."""
    errors: List[str] = []
    seen_versions: set = set()
    for mig in discover_migrations():
        if mig.version in seen_versions and mig.dialect is None:
            errors.append(f"{mig.filename}: duplicate version {mig.version}")
        seen_versions.add(mig.version)
        try:
            body = mig.body().strip()
        except OSError as e:
            errors.append(f"{mig.filename}: unreadable ({e})")
            continue
        if not body:
            errors.append(f"{mig.filename}: empty migration file")
            continue
        upper = body.upper()
        for danger in ("DROP TABLE ", "DROP COLUMN ", "TRUNCATE "):
            if danger in upper:
                errors.append(
                    f"{mig.filename}: contains forbidden statement '{danger.strip()}' — "
                    "migrations must be forward-compatible (use a new nullable column "
                    "and a cleanup migration in the NEXT release instead)"
                )
    return errors


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Mus Luxury schema migrator")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up", help="apply pending migrations")
    sub.add_parser("status", help="list applied vs pending migrations")
    sub.add_parser("validate", help="static validation of migration files")
    sub.add_parser("dry-run", help="show what up would do without applying")
    args = parser.parse_args()

    if args.cmd == "validate":
        errs = validate()
        if errs:
            for e in errs:
                print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        print("OK: all migration files pass static validation")
        sys.exit(0)

    if args.cmd == "status":
        conn = get_connection()
        is_pg = isinstance(conn, PostgresCompatConnection)
        try:
            ensure_baseline(conn, is_pg)
            _ensure_tracking_table(conn, is_pg)
            applied = _applied_versions(conn)
        finally:
            conn.close()
        all_migs = applicable(discover_migrations(), is_pg)
        pending = [m.filename for m in all_migs if m.version not in applied]
        print(json.dumps(
            {"applied": sorted(applied.keys()), "pending": pending}, indent=2))
        sys.exit(0)

    if args.cmd == "dry-run":
        pending = run(dry_run=True)
        if pending:
            print("Would apply:")
            for f in pending:
                print(f"  - {f}")
        else:
            print("No pending migrations.")
        sys.exit(0)

    if args.cmd == "up":
        applied = run(dry_run=False)
        if applied:
            print("Applied:")
            for f in applied:
                print(f"  - {f}")
        else:
            print("Database already up to date.")
        sys.exit(0)
