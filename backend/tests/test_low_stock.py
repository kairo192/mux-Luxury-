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


class TestLowStockReport(unittest.TestCase):
    """Low-stock report with on-order quantity and reorder suggestions."""

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
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"ls-{self.suffix}", "name_fr": f"LS {self.suffix}", "name_ar": "x", "name_en": "LS",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}, {"value": "B", "label_fr": "B"}]})
        self.product = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"ls-product-{self.suffix}", "sku": f"LS-{self.suffix.upper()}",
            "name_fr": "LS", "selling_price_dzd": 5000, "purchase_cost_dzd": 2000, "status": "published",
            "variants": [
                {"sku": f"LS-{self.suffix.upper()}-A", "title": "A", "stock_qty": 1, "low_stock_threshold": 3, "attributes": {"slot": "A"}},
                {"sku": f"LS-{self.suffix.upper()}-B", "title": "B", "stock_qty": 0, "low_stock_threshold": 3, "attributes": {"slot": "B"}},
            ]}).json()

    def _report(self, **params):
        return self.client.get("/api/v1/admin/inventory/low-stock", headers=self.headers, params=params)

    # ------------------------------------------------------------------ tests
    def test_01_lists_low_and_out_of_stock(self):
        r = self._report()
        self.assertEqual(r.status_code, 200)
        skus = {it["sku"] for it in r.json()["items"]}
        self.assertIn(self.product["variants"][0]["sku"], skus)
        self.assertIn(self.product["variants"][1]["sku"], skus)  # out of stock
        s = r.json()["summary"]
        self.assertGreaterEqual(s["out_of_stock_count"], 1)
        self.assertGreaterEqual(s["low_stock_count"], 1)

    def test_02_filter_excludes_out_of_stock(self):
        r = self._report(include_out_of_stock=False)
        skus = {it["sku"] for it in r.json()["items"]}
        self.assertIn(self.product["variants"][0]["sku"], skus)
        self.assertNotIn(self.product["variants"][1]["sku"], skus)

    def test_03_on_order_quantity_from_purchase_order(self):
        # Create a supplier + a purchase order for 10 units of variant A
        sup = self.client.post("/api/v1/admin/suppliers", headers=self.headers, json={"name": f"Sup {self.suffix}"}).json()
        po = self.client.post("/api/v1/admin/purchases", headers=self.headers, json={
            "supplier_id": sup["id"], "shipping_dzd": 0, "tax_dzd": 0,
            "items": [{"product_id": self.product["id"], "variant_id": self.product["variants"][0]["id"],
                       "quantity": 10, "unit_cost_dzd": 2000}],
        })
        self.assertEqual(po.status_code, 201, po.text)
        r = self._report()
        a = next(it for it in r.json()["items"] if it["sku"] == self.product["variants"][0]["sku"])
        self.assertEqual(a["on_order_qty"], 10)
        # Suggestion drops because 10 are already incoming
        self.assertEqual(a["suggested_reorder_qty"], 0)

    def test_04_suggested_reorder_covers_two_months(self):
        # Variant A: stock 1, low threshold 3, no velocity → target = 4, on_order = 0 → suggested = 3
        r = self._report()
        a = next(it for it in r.json()["items"] if it["sku"] == self.product["variants"][0]["sku"])
        self.assertEqual(a["suggested_reorder_qty"], 3)
        self.assertEqual(a["unit_cost_dzd"], 2000)


if __name__ == "__main__":
    unittest.main()
