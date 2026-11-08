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

from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestTreasuryReport(unittest.TestCase):
    """Treasury report: date-ranged flow by account / source + CSV."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        self.today = date.today().isoformat()

    def _add_movement(self, mtype: str, amount: int, account: str = "cash_box", source: str = "manual"):
        return self.client.post("/api/v1/admin/treasury/movements", headers=self.headers, json={
            "account_type": account, "movement_type": mtype, "amount_dzd": amount,
            "description": f"Test {self.suffix}", "source_reference": f"ref-{self.suffix}",
        })

    def _report(self):
        return self.client.get("/api/v1/admin/reports/treasury", headers=self.headers, params={"from": self.today, "to": self.today})

    # ------------------------------------------------------------------ tests
    def test_01_invalid_dates(self):
        r = self.client.get("/api/v1/admin/reports/treasury", headers=self.headers, params={"from": "bogus", "to": self.today})
        self.assertEqual(r.status_code, 422)
        r2 = self.client.get("/api/v1/admin/reports/treasury", headers=self.headers, params={"from": "2026-12-01", "to": "2026-01-01"})
        self.assertEqual(r2.status_code, 422)

    def test_02_flow_captured_in_totals(self):
        base = self._report().json()["totals"]
        self._add_movement("inflow", 10000)
        self._add_movement("withdrawal", 3000)
        after = self._report().json()["totals"]
        self.assertEqual(after["inflow_dzd"] - base["inflow_dzd"], 10000)
        self.assertEqual(after["outflow_dzd"] - base["outflow_dzd"], 3000)
        self.assertEqual(after["net_dzd"] - base["net_dzd"], 7000)

    def test_03_grouped_by_account(self):
        self._add_movement("inflow", 5000, account="cash_box")
        self._add_movement("inflow", 2000, account="bank_account")
        r = self._report().json()
        by_acc = {b["account_type"]: b for b in r["by_account"]}
        self.assertIn("cash_box", by_acc)
        self.assertIn("bank_account", by_acc)

    def test_04_csv(self):
        self._add_movement("inflow", 1500)
        r = self.client.get("/api/v1/admin/reports/treasury.csv", headers=self.headers, params={"from": self.today, "to": self.today})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        body = r.text
        self.assertTrue(body.splitlines()[0].startswith("date,account,movement_type"))
        self.assertIn("TOTAL", body)


if __name__ == "__main__":
    unittest.main()
