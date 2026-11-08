import json
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Optional, Tuple

DB_PATH = os.getenv("LUXE_SQLITE_PATH", os.path.join(os.path.dirname(__file__), "..", "luxe_store.sqlite3"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_initial_schema.sql")
PG_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_initial_schema_postgres.sql")


def translate_sql_for_postgres(sql: str) -> Tuple[str, bool]:
    """
    Translates SQLite-flavored parameterized SQL into PostgreSQL 16 SQL:
    1. Converts `?` positional placeholders outside string literals into `%s`.
    2. Converts `INSERT OR IGNORE INTO <table> ...` into `INSERT INTO <table> ... ON CONFLICT DO NOTHING`.
    3. Converts `BEGIN IMMEDIATE` into `BEGIN`.
    4. Appends `RETURNING id` on standard `INSERT INTO` statements so `cursor.lastrowid` works seamlessly.
    """
    stripped = sql.strip()
    upper = stripped.upper()

    if upper.startswith("PRAGMA "):
        return "SELECT 1", False

    if upper == "BEGIN IMMEDIATE":
        return "BEGIN", False

    is_insert_ignore = False
    if re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", stripped, flags=re.IGNORECASE):
        is_insert_ignore = True
        stripped = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", stripped, count=1, flags=re.IGNORECASE)

    # Replace ? with %s outside single-quoted literals
    out_chars = []
    in_quote = False
    for ch in stripped:
        if ch == "'":
            in_quote = not in_quote
            out_chars.append(ch)
        elif ch == "?" and not in_quote:
            out_chars.append("%s")
        else:
            out_chars.append(ch)
    pg_sql = "".join(out_chars).rstrip(";")

    if is_insert_ignore and "ON CONFLICT" not in pg_sql.upper():
        pg_sql += " ON CONFLICT DO NOTHING"

    needs_returning_id = (
        pg_sql.upper().startswith("INSERT INTO ")
        and "RETURNING " not in pg_sql.upper()
        and "role_permissions" not in pg_sql.lower()
        and "store_settings" not in pg_sql.lower()
    )
    if needs_returning_id:
        pg_sql += " RETURNING id"

    return pg_sql, needs_returning_id


class PostgresCompatCursor:
    def __init__(self, raw_cur):
        self._cur = raw_cur
        self.lastrowid: Optional[int] = None
        self.rowcount: int = 0

    def execute(self, sql: str, params: Iterable[Any] = ()):
        pg_sql, has_returning = translate_sql_for_postgres(sql)
        norm_params = tuple(int(p) if isinstance(p, bool) else p for p in params)
        self._cur.execute(pg_sql, norm_params)
        self.rowcount = self._cur.rowcount
        if has_returning:
            row = self._cur.fetchone()
            if row:
                self.lastrowid = row["id"] if isinstance(row, dict) else row[0]
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class PostgresCompatConnection:
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self.in_transaction = False

    def cursor(self) -> PostgresCompatCursor:
        return PostgresCompatCursor(self._conn.cursor())

    def execute(self, sql: str, params: Iterable[Any] = ()):
        cur = self.cursor()
        cur.execute(sql, params)
        if sql.strip().upper().startswith("BEGIN"):
            self.in_transaction = True
        return cur._cur

    def executescript(self, sql_script: str):
        with self._conn.cursor() as cur:
            cur.execute(sql_script)

    def iterdump(self):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n")
        dump_tables = [
            "roles", "permissions", "role_permissions", "admin_users",
            "brands", "categories", "category_attributes", "category_attribute_options",
            "products", "product_images", "product_attribute_values", "product_variants",
            "variant_attribute_values", "delivery_zones", "delivery_rates",
            "customers", "orders", "order_items", "inventory_movements",
            "homepage_sections", "banners", "static_pages", "store_settings",
            "coupons", "customer_phone_blacklist"
        ]
        def _sql_literal(v: Any) -> str:
            if v is None:
                return "NULL"
            if isinstance(v, bool):
                return "1" if v else "0"
            if isinstance(v, (int, float)):
                return str(v)
            s = str(v).replace("'", "''")
            return f"'{s}'"
        cur = self.cursor()
        for tbl in dump_tables:
            try:
                cur.execute(f"SELECT * FROM {tbl}")
                rows = cur.fetchall()
                for r in rows:
                    rd = dict(r)
                    cols = ", ".join(rd.keys())
                    vals = ", ".join(_sql_literal(rd[k]) for k in rd.keys())
                    yield f"INSERT OR IGNORE INTO {tbl} ({cols}) VALUES ({vals});"
            except Exception:
                continue

    def commit(self):
        self._conn.commit()
        self.in_transaction = False

    def rollback(self):
        self._conn.rollback()
        self.in_transaction = False

    def close(self):
        self._conn.close()


def normalize_postgres_url(raw_url: str) -> str:
    """
    Normalizes SQLAlchemy-style URLs (`postgresql+psycopg://...` or `postgres://...`)
    into standard libpq connection URIs (`postgresql://...`) accepted by psycopg 3.
    """
    u = (raw_url or "").strip()
    u = re.sub(r"^postgresql\+[a-zA-Z0-9_]+://", "postgresql://", u)
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    return u


def get_connection():
    """
    Connects to PostgreSQL 16 when LUXE_DB_ENGINE=postgres.
    Fails closed (raises RuntimeError) if LUXE_DB_ENGINE=postgres and PostgreSQL is unreachable,
    preventing silent fallback to ephemeral container SQLite in production.
    """
    engine = os.getenv("LUXE_DB_ENGINE", "").strip().lower()
    raw_db_url = os.getenv("DATABASE_URL", "").strip()
    if engine == "postgres":
        if not raw_db_url or "<CHANGE_ME" in raw_db_url:
            raise RuntimeError("CRITICAL: LUXE_DB_ENGINE=postgres requires a valid DATABASE_URL")
        pg_url = normalize_postgres_url(raw_db_url)
        try:
            import psycopg
            from psycopg.rows import dict_row
            raw_pg = psycopg.connect(pg_url, row_factory=dict_row)
            return PostgresCompatConnection(raw_pg)
        except Exception as exc:
            raise RuntimeError(f"CRITICAL: PostgreSQL connection failed (silent SQLite fallback is disabled): {exc}") from exc

    target_db_path = os.getenv("LUXE_SQLITE_PATH") or DB_PATH
    conn = sqlite3.connect(target_db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


@contextmanager
def db_session(commit: bool = False):
    conn = get_connection()
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Columns introduced after the first schema release. They are added in place with
# ALTER TABLE so an existing store database upgrades without a destructive rebuild.
_ADDITIVE_COLUMNS = [
    ("product_variants", "purchase_cost_dzd", "INTEGER"),
    ("product_variants", "weight_grams", "INTEGER"),
    ("product_variants", "low_stock_threshold", "INTEGER NOT NULL DEFAULT 3"),
    ("products", "weight_grams", "INTEGER"),
    ("products", "dimensions_cm", "VARCHAR(60)"),
    ("products", "tags", "VARCHAR(400)"),
    # POS: link stock movements to in-store sales (shared inventory ledger)
    ("inventory_movements", "pos_sale_id", "INTEGER"),
    # Customer management: optional contact + CRM notes (walk-in friendly)
    ("customers", "email", "VARCHAR(255)"),
    ("customers", "notes", "TEXT"),
]


def _existing_columns(conn, table: str) -> set:
    if isinstance(conn, PostgresCompatConnection):
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        )
        return {r["column_name"] for r in cur.fetchall()}
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def ensure_schema_columns(conn) -> None:
    """Idempotently adds post-release columns to an existing database."""
    for table, column, ddl in _ADDITIVE_COLUMNS:
        try:
            existing = _existing_columns(conn, table)
        except Exception:
            continue
        if not existing or column in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    conn = get_connection()
    try:
        if isinstance(conn, PostgresCompatConnection):
            with open(PG_SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        else:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.execute("PRAGMA foreign_keys = ON;")
        ensure_schema_columns(conn)
        conn.commit()
    finally:
        conn.close()
