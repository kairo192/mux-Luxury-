"""
The production server runs PostgreSQL; PCs and tests run SQLite. All SQL goes
through translate_sql_for_postgres, and PostgreSQL rows are reshaped like
SQLite rows. These rules caused real production failures when missing:
crashed shop product/category lists (datetime in ETag), crashed sales and
treasury reports (substr on timestamps), crashed POS refunds (MAX(a, b)),
and a failed first deploy (RETURNING id on schema_migrations).
"""
import datetime as dt
import unittest
from decimal import Decimal

from app.database import TABLES_WITHOUT_ID, _sqlite_shaped, translate_sql_for_postgres as t


class TestPostgresCompat(unittest.TestCase):
    def test_sqlite_functions_rewritten(self):
        self.assertEqual(t("SELECT substr(created_at, 1, 10) AS day FROM orders")[0],
                         "SELECT substr(CAST(created_at AS TEXT), 1, 10) AS day FROM orders")
        self.assertEqual(t("SELECT 1 FROM p WHERE datetime(p.updated_at) >= datetime(?)")[0],
                         "SELECT 1 FROM p WHERE CAST(p.updated_at AS TIMESTAMP) >= CAST(%s AS TIMESTAMP)")
        self.assertEqual(t("UPDATE products SET sales_count = MAX(0, sales_count - ?) WHERE id = ?")[0],
                         "UPDATE products SET sales_count = GREATEST(0, sales_count - %s) WHERE id = %s")
        # The aggregate MAX(x) is untouched.
        self.assertEqual(t("SELECT COALESCE(MAX(display_order), 0) FROM banners")[0],
                         "SELECT COALESCE(MAX(display_order), 0) FROM banners")

    def test_like_is_case_insensitive_like_sqlite(self):
        self.assertEqual(t("SELECT 1 FROM customers WHERE full_name LIKE ? OR phone NOT LIKE ?")[0],
                         "SELECT 1 FROM customers WHERE full_name ILIKE %s OR phone NOT ILIKE %s")

    def test_returning_id_only_for_tables_with_an_id(self):
        self.assertTrue(t("INSERT INTO banners (title_fr) VALUES (?)")[1])
        for table in TABLES_WITHOUT_ID:
            sql, returning = t(f"INSERT INTO {table} (a) VALUES (?)")
            self.assertFalse(returning, table)
            self.assertNotIn("RETURNING", sql)

    def test_rows_have_sqlite_shapes(self):
        self.assertEqual(_sqlite_shaped(dt.datetime(2026, 11, 11, 9, 5, 0)), "2026-11-11 09:05:00")
        self.assertEqual(_sqlite_shaped(dt.date(2026, 11, 11)), "2026-11-11")
        self.assertEqual(_sqlite_shaped(Decimal("12500")), 12500)
        self.assertIsInstance(_sqlite_shaped(Decimal("12500")), int)
        self.assertEqual(_sqlite_shaped(Decimal("2.5")), 2.5)
        self.assertEqual(_sqlite_shaped("x"), "x")


if __name__ == "__main__":
    unittest.main()
