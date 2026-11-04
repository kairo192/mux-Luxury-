import os
import sys

os.environ["SECRET_KEY"] = "dev_secret_key_mus_luxury_2026_very_secure_long_string_1234567890"
os.environ["APP_ENV"] = "development"
os.environ["LUXE_DB_ENGINE"] = "sqlite"
os.environ["LUXE_SQLITE_PATH"] = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend\luxe_store.sqlite3"
sys.path.insert(0, r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend")

from app.database import db_session
from app.main import serialize_product

query_count = 0
queries = []

class CountingCursor:
    def __init__(self, real_cur):
        self._cur = real_cur
    def execute(self, sql, params=()):
        global query_count
        query_count += 1
        queries.append(sql.strip().replace('\n', ' '))
        return self._cur.execute(sql, params)
    def fetchall(self):
        return self._cur.fetchall()
    def fetchone(self):
        return self._cur.fetchone()
    def __getattr__(self, name):
        return getattr(self._cur, name)

class CountingConnection:
    def __init__(self, real_conn):
        self._conn = real_conn
    def cursor(self):
        return CountingCursor(self._conn.cursor())
    def execute(self, sql, params=()):
        global query_count
        query_count += 1
        queries.append(sql.strip().replace('\n', ' '))
        return self._conn.execute(sql, params)
    def __getattr__(self, name):
        return getattr(self._conn, name)

with db_session() as conn:
    c_conn = CountingConnection(conn)
    cur = c_conn.cursor()
    cur.execute("SELECT * FROM products WHERE status='published' AND deleted_at IS NULL")
    prods = cur.fetchall()
    query_count = 0
    queries.clear()
    for p in prods:
        serialize_product(c_conn, dict(p))
    print(f"Products count: {len(prods)}")
    print(f"Total SQL queries executed for {len(prods)} products: {query_count}")
    print(f"Average queries per product: {query_count / max(1, len(prods)):.1f}")
    print("\nSample queries:")
    for q in queries[:10]:
        print("  -", q[:100])
