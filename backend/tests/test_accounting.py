"""
Comptabilité (P&L) and per-product profitability count BOTH channels and the
same sales as the business dashboard:
  * online: orders neither cancelled nor returned (a returned COD parcel was never paid)
  * in store: sales minus refunds
  * cost of goods = units × purchase cost
Each test measures the change it causes, so it works on a shared database.
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

PRICE, COST = 10000, 4000


class TestAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        # Free delivery off so delivery fees are predictable.
        self.client.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"free_delivery_threshold_dzd": "0"}})

    def tearDown(self):
        self.client.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"free_delivery_threshold_dzd": "25000"}})

    def _product(self):
        sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"acc-{sfx}", "name_fr": "Compta", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        self.client.post("/api/v1/admin/category-attributes", headers=self.h, json={
            "category_id": cat["id"], "attr_key": "size", "label_fr": "Taille", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "M", "label_fr": "M"}]})
        p = self.client.post("/api/v1/admin/products", headers=self.h, json={
            "category_id": cat["id"], "slug": f"acc-p-{sfx}", "sku": f"ACC-{sfx.upper()}", "name_fr": "Article compta",
            "selling_price_dzd": PRICE, "purchase_cost_dzd": COST, "status": "published",
            "variants": [{"sku": f"ACC-{sfx.upper()}-M", "title": "M", "stock_qty": 50, "attributes": {"size": "M"}}]})
        self.assertEqual(p.status_code, 201, p.text)
        prod = self.client.get(f"/api/v1/products/acc-p-{sfx}").json()
        return prod["id"], prod["variants"][0]["id"]

    def _order(self, vid, qty, status=None):
        r = self.client.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Client Compta", "phone": "0661000000", "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "1 rue de la Compta, Alger", "delivery_method": "home",
            "items": [{"variant_id": vid, "quantity": qty}]})
        self.assertEqual(r.status_code, 201, r.text)
        o = r.json()
        if status:
            path = {"returned": ["confirmed", "shipped", "returned"], "cancelled": ["cancelled"]}[status]
            for st in path:
                u = self.client.patch(f"/api/v1/admin/orders/{o['order_id']}", headers=self.h, json={"status": st})
                self.assertEqual(u.status_code, 200, u.text)
        return o

    def _pnl(self):
        r = self.client.get("/api/v1/admin/accounting/pnl", headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_pnl_counts_both_channels_and_ignores_cancelled_and_returned(self):
        _, vid = self._product()
        before = self._pnl()
        biz_before = self.client.get("/api/v1/admin/dashboard/business", headers=self.h).json()

        kept = self._order(vid, 2)                      # counts
        self._order(vid, 1, status="cancelled")         # never counts
        self._order(vid, 1, status="returned")          # never paid: never counts
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": PRICE}]})
        self.assertEqual(sale.status_code, 201, sale.text)
        self.client.post("/api/v1/admin/expenses", headers=self.h, json={
            "description": "Compta test", "category": "rent", "amount_dzd": 3000,
            "expense_date": __import__("datetime").date.today().isoformat(),
            "payment_method": "cash", "payment_status": "paid"})

        after = self._pnl()
        d = lambda k: after[k] - before[k]  # noqa: E731
        self.assertEqual(d("gross_revenue_dzd"), 3 * PRICE, "2 online + 1 in store; cancelled/returned excluded")
        self.assertEqual(d("delivery_revenue_dzd"), kept["delivery_fee_dzd"])
        self.assertEqual(d("cogs_dzd"), 3 * COST)
        fee = kept["delivery_fee_dzd"]
        self.assertEqual(d("total_revenue_dzd"), 3 * PRICE + fee)
        self.assertEqual(d("gross_profit_dzd"), 3 * (PRICE - COST) + fee)
        self.assertEqual(d("operating_expenses_dzd"), 3000)
        self.assertEqual(d("net_operating_profit_dzd"), 3 * (PRICE - COST) + fee - 3000)
        self.assertEqual(d("units_sold"), 3)
        self.assertEqual(d("orders_count"), 1)
        self.assertEqual(d("in_store_sales_count"), 1)

        # Same sales as the business dashboard (this month).
        biz_after = self.client.get("/api/v1/admin/dashboard/business", headers=self.h).json()
        biz_delta = biz_after["margin_month"]["revenue_dzd"] - biz_before["margin_month"]["revenue_dzd"]
        self.assertEqual(biz_delta, d("total_revenue_dzd"))

    def test_product_profitability_both_channels(self):
        pid, vid = self._product()
        self._order(vid, 2)
        self._order(vid, 3, status="cancelled")
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
        self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": PRICE}]})
        items = self.client.get("/api/v1/admin/accounting/products-profitability", headers=self.h).json()["items"]
        row = next(i for i in items if i["id"] == pid)
        self.assertEqual(row["units_sold"], 3)
        self.assertEqual(row["total_revenue_dzd"], 3 * PRICE)
        self.assertEqual(row["total_cost_sold_dzd"], 3 * COST)
        self.assertEqual(row["total_profit_dzd"], 3 * (PRICE - COST))

    def test_pos_refund_gives_back_what_was_paid_with_discount(self):
        """2 units at 10 000 with a 2 000 ticket discount: paid 18 000.
        Refunding 1 unit gives 9 000 back (not the 10 000 list price), the
        last unit gives back exactly what is left, the till matches."""
        _, vid = self._product()
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
        reg0 = self.client.get("/api/v1/admin/pos/register/current", headers=self.h).json()
        sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 2}], "order_discount_dzd": 2000,
            "payments": [{"method": "cash", "amount_dzd": 18000}]})
        self.assertEqual(sale.status_code, 201, sale.text)
        sid = sale.json()["id"]
        self.assertEqual(sale.json()["total_dzd"], 18000)
        r1 = self.client.post(f"/api/v1/admin/pos/sales/{sid}/refund", headers=self.h,
                              json={"items": [{"variant_id": vid, "quantity": 1}], "refund_method": "cash"})
        self.assertEqual(r1.status_code, 201, r1.text)
        self.assertEqual(r1.json()["total_dzd"], 9000)
        r2 = self.client.post(f"/api/v1/admin/pos/sales/{sid}/refund", headers=self.h, json={"refund_method": "cash"})
        self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(r2.json()["total_dzd"], 9000)
        reg1 = self.client.get("/api/v1/admin/pos/register/current", headers=self.h).json()
        e0 = (reg0.get("session") or reg0).get("expected_cash_dzd", 0)
        e1 = (reg1.get("session") or reg1).get("expected_cash_dzd", 0)
        self.assertEqual(e1 - e0, 0, "sold 18 000 cash, refunded 18 000 cash: drawer unchanged")


if __name__ == "__main__":
    unittest.main()
