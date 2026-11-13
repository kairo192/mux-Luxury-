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


class TestBusinessDashboard(unittest.TestCase):
    """Unified dashboard: real deltas from online + in-store sales, margins, health."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:8]
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]  # stock 10, cost 1000, price 3000

    def _biz(self):
        r = self.client.get("/api/v1/admin/dashboard/business", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _create_category(self) -> int:
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"dash-{self.suffix}", "name_fr": f"Dash {self.suffix}", "name_ar": "x", "name_en": "Dash",
            "display_order": 99, "is_active": True, "show_on_homepage": False,
        })
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        a = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}],
        })
        assert a.status_code == 201, a.text
        return cid

    def _create_product(self) -> dict:
        sku = f"DA-{self.suffix.upper()}"
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"dash-product-{self.suffix}", "sku": sku,
            "name_fr": f"Dash {self.suffix}", "selling_price_dzd": 3000, "purchase_cost_dzd": 1000, "status": "published",
            "variants": [{"sku": f"{sku}-A", "title": "Slot A", "stock_qty": 10, "purchase_cost_dzd": 1000, "attributes": {"slot": "A"}}],
        })
        assert r.status_code == 201, r.text
        return r.json()

    # ------------------------------------------------------------------ tests
    def test_01_in_store_sale_reflected(self):
        d0 = self._biz()
        # open register + sell 2 units
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 5000})
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 6000}],
        })
        self.assertEqual(sale.status_code, 201, sale.text)
        d1 = self._biz()
        self.assertEqual(
            d1["sales"]["in_store"]["month"]["revenue_dzd"] - d0["sales"]["in_store"]["month"]["revenue_dzd"],
            6000,
        )
        # inventory valuation at cost dropped by 2 * 1000
        self.assertEqual(
            d0["inventory"]["valuation_cost_dzd"] - d1["inventory"]["valuation_cost_dzd"],
            2000,
        )
        # cash register shows open
        self.assertTrue(d1["cash_register"]["open"])
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 11000})

    def test_02_online_order_reflected(self):
        d0 = self._biz()
        order = self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"dash-ord-{self.suffix}"}, json={
            "full_name": "Client Dashboard", "phone": "0551234567", "wilaya_code": "09",
            "commune": "Ouled Yaïch", "delivery_address": "Rue Test", "delivery_method": "home",
            "items": [{"variant_id": self.variant["id"], "quantity": 1}],
        })
        self.assertEqual(order.status_code, 201, order.text)
        total = order.json()["total_dzd"]
        d1 = self._biz()
        self.assertEqual(
            d1["sales"]["online"]["month"]["revenue_dzd"] - d0["sales"]["online"]["month"]["revenue_dzd"],
            total,
        )

    def test_03_margin_distinct_from_revenue(self):
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 3}],
            "payments": [{"method": "cash", "amount_dzd": 9000}],
        })
        m = self._biz()["margin_month"]
        # revenue, gross margin and net profit are distinct, consistent numbers
        self.assertEqual(m["gross_margin_dzd"], m["revenue_dzd"] - m["cogs_dzd"])
        self.assertEqual(m["net_profit_dzd"], m["gross_margin_dzd"] - m["operating_expenses_dzd"])
        self.assertGreater(m["cogs_dzd"], 0)  # cost is real, so margin != revenue
        self.assertLess(m["gross_margin_dzd"], m["revenue_dzd"])
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

    def test_04_device_health_and_bestsellers(self):
        d0 = self._biz()
        self.client.post("/api/v1/admin/devices", headers=self.headers, json={
            "name": f"Printer {self.suffix}", "device_type": "receipt_printer", "connection_type": "windows",
        })
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 3000}],
        })
        d1 = self._biz()
        self.assertEqual(d1["devices"]["total"] - d0["devices"]["total"], 1)
        # The list is the top 8 of the whole (shared) database: the sold variant
        # is either listed, or outranked by 8 variants that sold at least as much.
        best = d1["best_sellers"]
        if not any(b["variant_id"] == self.variant["id"] for b in best):
            self.assertEqual(len(best), 8)
            self.assertTrue(all(b["qty_sold"] >= 1 for b in best))
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

    def test_05_unauthorized(self):
        self.assertEqual(self.client.get("/api/v1/admin/dashboard/business").status_code, 401)


if __name__ == "__main__":
    unittest.main()
