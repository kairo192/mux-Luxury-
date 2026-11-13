"""
First start of the migration runner on a new SQLite database: an interrupted
first start (tracking table created, base tables not) must finish on the next
start instead of leaving a database every migration fails on.
Runs in a child process so the shop database of the other tests is untouched.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
RUN = "from app.migration_runner import run; run()"


class TestMigrationBaseline(unittest.TestCase):
    def _migrate(self, db_path: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL",)}
        env.update({"LUXE_DB_ENGINE": "sqlite", "LUXE_SQLITE_PATH": db_path, "APP_ENV": "test"})
        return subprocess.run([sys.executable, "-c", RUN], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)

    def _tables(self, db_path: str) -> set:
        with sqlite3.connect(db_path) as c:
            return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def test_interrupted_first_start_finishes_on_next_start(self):
        fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            with sqlite3.connect(db_path) as c:   # state left by an interrupted first start
                c.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, filename TEXT NOT NULL, "
                          "checksum TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                          "duration_ms INTEGER NOT NULL DEFAULT 0)")
            r = self._migrate(db_path)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            tables = self._tables(db_path)
            self.assertTrue({"products", "orders", "roles"} <= tables)
            with sqlite3.connect(db_path) as c:
                versions = {row[0] for row in c.execute("SELECT version FROM schema_migrations")}
            self.assertIn("000", versions)
            self.assertGreater(len(versions), 1)            # later migrations applied too
            r = self._migrate(db_path)                      # and a further start changes nothing
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
