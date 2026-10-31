import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("LUXE_SQLITE_PATH", os.path.join(os.path.dirname(__file__), "..", "luxe_store.sqlite3"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_initial_schema.sql")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
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

def init_db() -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with db_session(commit=True) as conn:
        conn.executescript(schema_sql)
        conn.execute("PRAGMA foreign_keys = ON;")
