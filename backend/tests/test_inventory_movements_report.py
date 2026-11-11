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


class TestInventoryMovementsReport(unittest.TestCase):
    """Inventory movements report: date range, per-reason summary, CSV."""

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
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"imr-{self.suffix}", "name_fr": f"IMR {self.suffix}", "name_ar": "x", "name_en": "IMR",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        self.product = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"imr-product-{self.suffix}", "sku": f"IR-{self.suffix.upper()}",
            "name_fr": "IMR", "selling_price_dzd": 5000, "status": "published",
            "variants": [{"sku": f"IR-{self.suffix.upper()}-A", "title": "A", "stock_qty": 20, "attributes": {"slot": "A"}}]}).json()
        self.variant_id = self.product["variants"][0]["id"]

    def _report(self, **params):
        return self.client.get("/api/v1/admin/reports/inventory-movements", headers=self.headers, params={"from": self.today, "to": self.today, **params})

    # ------------------------------------------------------------------ tests
    def test_01_empty_for_this_variant(self):
        # Scope by variant_id so other tests in the same suite don't pollute totals
        r = self._report(variant_id=self.variant_id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["totals"]["units_in"], 0)
        self.assertEqual(r.json()["totals"]["units_out"], 0)

    def test_02_movements_captured(self):
        # Create movements of different reasons
        self.client.post(f"/api/v1/admin/variants/{self.variant_id}/adjust-stock", headers=self.headers, json={"change_qty": 5, "reason": "manual_in"})
        self.client.post("/api/v1/admin/inventory/write-off", headers=self.headers, json={"variant_id": self.variant_id, "quantity": 2, "reason": "damaged"})
        r = self._report().json()
        self.assertGreaterEqual(r["totals"]["count"], 2)
        reasons = {br["reason"] for br in r["by_reason"]}
        self.assertIn("manual_in", reasons)
        self.assertIn("writeoff_damaged", reasons)

    def test_03_filter_by_variant(self):
        self.client.post(f"/api/v1/admin/variants/{self.variant_id}/adjust-stock", headers=self.headers, json={"change_qty": 3, "reason": "manual_in"})
        r = self._report(variant_id=self.variant_id).json()
        self.assertTrue(all(it["variant_id"] == self.variant_id for it in r["items"]))

    def test_04_csv(self):
        self.client.post(f"/api/v1/admin/variants/{self.variant_id}/adjust-stock", headers=self.headers, json={"change_qty": 1, "reason": "manual_in"})
        r = self.client.get("/api/v1/admin/reports/inventory-movements.csv", headers=self.headers, params={"from": self.today, "to": self.today})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        body = r.text
        self.assertTrue(body.lstrip("\ufeff").splitlines()[0].startswith("Date;SKU;Produit"))
        self.assertIn("TOTAL", body)

    def test_05_invalid_dates(self):
        r = self.client.get("/api/v1/admin/reports/inventory-movements", headers=self.headers, params={"from": "bogus", "to": self.today})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
