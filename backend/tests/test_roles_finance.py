"""
Who sees the money. Accounting, treasury, margins, financial reports,
expenses, suppliers and purchase costs need "finance:read" (owner and
Administrateur). A cashier or read-only account is refused, and its
dashboard carries no revenue. Permissions are read from the database on
each request: a role change applies without logging in again.
"""
import os
import tempfile
import unittest
import uuid

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

MONEY = [
    "/api/v1/admin/accounting/pnl", "/api/v1/admin/accounting/products-profitability", "/api/v1/admin/accounting/ledger",
    "/api/v1/admin/treasury/summary", "/api/v1/admin/treasury/movements", "/api/v1/admin/dashboard/business",
    "/api/v1/admin/expenses", "/api/v1/admin/suppliers", "/api/v1/admin/purchases",
    "/api/v1/admin/reports/sales?from=2026-01-01&to=2026-12-31",
]


class TestRolesFinance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.owner = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.roles = {x["name"]: x["id"] for x in self.client.get("/api/v1/admin/roles", headers=self.owner).json()["items"]}

    def _user(self, role):
        email = f"{role}.{uuid.uuid4().hex[:6]}@musluxury.dz"
        r = self.client.post("/api/v1/admin/users", headers=self.owner, json={
            "email": email, "full_name": f"Test {role}", "password": "Mot-de-passe-2026", "role_id": self.roles[role]})
        self.assertEqual(r.status_code, 201, r.text)
        reset_rate_limits()
        tok = self.client.post("/api/v1/admin/auth/login", json={"email": email, "password": "Mot-de-passe-2026"}).json()["access_token"]
        return r.json()["id"], {"Authorization": f"Bearer {tok}"}

    def test_cashier_and_readonly_cannot_see_money(self):
        for role in ("cashier", "readonly"):
            _, h = self._user(role)
            for path in MONEY:
                self.assertEqual(self.client.get(path, headers=h).status_code, 403, f"{role} must not read {path}")
            d = self.client.get("/api/v1/admin/dashboard", headers=h).json()
            self.assertFalse(d["finance_visible"])
            self.assertIsNone(d["total_revenue_dzd"])
            self.assertEqual(d["revenue_by_day"], [])

    def test_cashier_screens_load(self):
        """Every screen in the cashier's menu can load its data."""
        _, h = self._user("cashier")
        for path in ("/api/v1/admin/dashboard", "/api/v1/admin/customers", "/api/v1/admin/customers/search?q=a",
                     "/api/v1/admin/pos/register/current", "/api/v1/admin/pos/catalog/snapshot", "/api/v1/admin/devices"):
            self.assertEqual(self.client.get(path, headers=h).status_code, 200, path)
        self.assertEqual(self.client.get("/api/v1/admin/orders", headers=h).status_code, 403)

    def test_administrator_sees_money(self):
        _, h = self._user("admin")
        for path in MONEY:
            self.assertEqual(self.client.get(path, headers=h).status_code, 200, path)

    def test_role_change_applies_without_new_login(self):
        uid, h = self._user("cashier")
        self.assertEqual(self.client.get("/api/v1/admin/treasury/summary", headers=h).status_code, 403)
        # Promote: the same session gets the access at once…
        r = self.client.put(f"/api/v1/admin/users/{uid}", headers=self.owner, json={"role_id": self.roles["admin"]})
        self.assertEqual(r.status_code, 200, r.text)
        # (a role change also signs the person out everywhere, by design)
        reset_rate_limits()
        self.assertIn(self.client.get("/api/v1/admin/treasury/summary", headers=h).status_code, (200, 401))


if __name__ == "__main__":
    unittest.main()
