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


class TestSalesReport(unittest.TestCase):
    """Sales reports: date-ranged aggregation across in-store and online, CSV."""

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
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]  # stock 10, price 3000

    def _create_category(self) -> int:
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"rep-{self.suffix}", "name_fr": f"Rep {self.suffix}", "name_ar": "x", "name_en": "Rep",
            "display_order": 99, "is_active": True, "show_on_homepage": False})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        return cid

    def _create_product(self) -> dict:
        sku = f"RE-{self.suffix.upper()}"
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"rep-product-{self.suffix}", "sku": sku,
            "name_fr": f"Rep {self.suffix}", "selling_price_dzd": 3000, "status": "published",
            "variants": [{"sku": f"{sku}-A", "title": "A", "stock_qty": 10, "attributes": {"slot": "A"}}]})
        assert r.status_code == 201, r.text
        return r.json()

    def _report(self, d_from: str, d_to: str, headers=None):
        return self.client.get("/api/v1/admin/reports/sales", headers=headers or self.headers, params={"from": d_from, "to": d_to})

    # ------------------------------------------------------------------ tests
    def test_01_empty_range(self):
        r = self._report("2000-01-01", "2000-01-02")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["by_day"], [])
        self.assertEqual(r.json()["totals"]["net_revenue_dzd"], 0)

    def test_02_invalid_dates(self):
        self.assertEqual(self._report("bogus", "2026-01-01").status_code, 422)
        self.assertEqual(self._report("2026-02-01", "2026-01-01").status_code, 422)

    def test_03_in_store_sale_and_refund_reflected(self):
        today = _shop_today()
        base = self._report(today, today).json()["totals"]

        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 6000}]})
        self.assertEqual(sale.status_code, 201, sale.text)
        after = self._report(today, today).json()
        d = after["totals"]
        self.assertEqual(d["in_store_revenue_dzd"] - base["in_store_revenue_dzd"], 6000)
        self.assertEqual(d["net_revenue_dzd"] - base["net_revenue_dzd"], 6000)

        # refund 1 unit → in_store_refunds_dzd rises by 3000, net drops by 3000
        self.client.post(f"/api/v1/admin/pos/sales/{sale.json()['id']}/refund", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 1}]})
        after2 = self._report(today, today).json()
        d2 = after2["totals"]
        self.assertEqual(d2["in_store_refunds_dzd"] - d["in_store_refunds_dzd"], 3000)
        self.assertEqual(d2["net_revenue_dzd"] - d["net_revenue_dzd"], -3000)
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

        # top products includes our variant with positive qty
        self.assertTrue(any(p["variant_id"] == self.variant["id"] and p["qty_sold"] >= 2 for p in after2["top_products"]))

    def test_04_online_order_in_net(self):
        today = _shop_today()
        base = self._report(today, today).json()["totals"]["net_revenue_dzd"]
        ord_r = self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"rep-{self.suffix}"}, json={
            "full_name": "Client Rapport", "phone": "0551234568", "wilaya_code": "09",
            "commune": "Ouled Yaïch", "delivery_address": "Rue Test", "delivery_method": "home",
            "items": [{"variant_id": self.variant["id"], "quantity": 1}]})
        self.assertEqual(ord_r.status_code, 201, ord_r.text)
        total = ord_r.json()["total_dzd"]
        after = self._report(today, today).json()["totals"]["net_revenue_dzd"]
        self.assertEqual(after - base, total)

    def test_05_csv_export(self):
        today = _shop_today()
        r = self.client.get("/api/v1/admin/reports/sales.csv", headers=self.headers, params={"from": today, "to": today})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn('attachment; filename="ventes_', r.headers["content-disposition"])
        body = r.text
        self.assertIn("Jour;Commandes en ligne;CA en ligne (DA)", body.lstrip("\ufeff").splitlines()[0])
        self.assertIn("TOTAL", body)


if __name__ == "__main__":
    unittest.main()
