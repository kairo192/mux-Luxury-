import os
import tempfile
import unittest
import uuid
from datetime import date

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from fastapi.testclient import TestClient

from app.main import app, _shop_today
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestExpenseReport(unittest.TestCase):
    """Expense report: per-category breakdown + CSV export."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        self.today = _shop_today()

    def _add_expense(self, category: str, amount: int, method: str = "cash", status: str = "paid"):
        return self.client.post("/api/v1/admin/expenses", headers=self.headers, json={
            "description": f"Test {self.suffix}",
            "category": category,
            "amount_dzd": amount,
            "expense_date": self.today,
            "payment_method": method,
            "payment_status": status,
        })

    # ------------------------------------------------------------------ tests
    def test_01_empty_range(self):
        r = self.client.get("/api/v1/admin/reports/expenses", headers=self.headers, params={"from": "2000-01-01", "to": "2000-01-02"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["totals"]["total_dzd"], 0)
        self.assertEqual(r.json()["by_category"], [])

    def test_02_grouped_by_category(self):
        cat_a = f"rent-{self.suffix}"
        cat_b = f"utility-{self.suffix}"
        self._add_expense(cat_a, 50000)
        self._add_expense(cat_a, 30000)
        self._add_expense(cat_b, 10000, method="bank_transfer")
        r = self.client.get("/api/v1/admin/reports/expenses", headers=self.headers, params={"from": self.today, "to": self.today})
        self.assertEqual(r.status_code, 200)
        cats = {c["category"]: c for c in r.json()["by_category"]}
        self.assertIn(cat_a, cats)
        self.assertEqual(cats[cat_a]["total_dzd"], 80000)
        self.assertEqual(cats[cat_a]["count"], 2)
        self.assertEqual(cats[cat_b]["by_method"]["bank_transfer"], 10000)

    def test_03_pending_total(self):
        self._add_expense(f"pend-{self.suffix}", 20000, status="pending")
        r = self.client.get("/api/v1/admin/reports/expenses", headers=self.headers, params={"from": self.today, "to": self.today})
        self.assertGreaterEqual(r.json()["totals"]["pending_dzd"], 20000)

    def test_04_csv(self):
        self._add_expense(f"csv-{self.suffix}", 7500)
        r = self.client.get("/api/v1/admin/reports/expenses.csv", headers=self.headers, params={"from": self.today, "to": self.today})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        body = r.text
        self.assertTrue(body.startswith("\ufeff"), "UTF-8 BOM for Excel")
        self.assertTrue(body.lstrip("\ufeff").splitlines()[0].startswith("Date;Catégorie;Description"))
        self.assertIn("TOTAL", body)

    def test_05_invalid_dates(self):
        self.assertEqual(self.client.get("/api/v1/admin/reports/expenses", headers=self.headers, params={"from": "bogus", "to": self.today}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
