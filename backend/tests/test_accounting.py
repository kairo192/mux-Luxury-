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

    def _treasury(self):
        t = self.client.get("/api/v1/admin/treasury/summary", headers=self.h).json()
        return t["cash_balance_dzd"], t["bank_balance_dzd"]

    def test_treasury_receives_sales_refunds_and_delivered_orders(self):
        _, vid = self._product()
        cash0, bank0 = self._treasury()
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
        cash_sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": PRICE}]})
        self.assertEqual(cash_sale.status_code, 201, cash_sale.text)
        card_sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "card", "amount_dzd": PRICE}]})
        self.assertEqual(card_sale.status_code, 201, card_sale.text)
        cash1, bank1 = self._treasury()
        self.assertEqual((cash1 - cash0, bank1 - bank0), (PRICE, PRICE), "cash → cash box, card → bank")

        r = self.client.post(f"/api/v1/admin/pos/sales/{cash_sale.json()['id']}/refund", headers=self.h, json={"refund_method": "cash"})
        self.assertEqual(r.status_code, 201, r.text)
        cash2, _ = self._treasury()
        self.assertEqual(cash2 - cash1, -PRICE, "refund leaves the cash box")

        o = self._order(vid, 1)
        for st in ("confirmed", "shipped", "delivered"):
            self.client.patch(f"/api/v1/admin/orders/{o['order_id']}", headers=self.h, json={"status": st})
        cash3, _ = self._treasury()
        self.assertEqual(cash3 - cash2, o["total_dzd"], "delivered COD order = money collected")
        self.client.patch(f"/api/v1/admin/orders/{o['order_id']}", headers=self.h, json={"status": "returned"})
        cash4, _ = self._treasury()
        self.assertEqual(cash4 - cash3, -o["total_dzd"], "return after delivery gives it back")

    def test_treasury_backfill_adds_missing_history_once(self):
        from app.database import db_session
        from app.seed import TREASURY_BACKFILL_MARKER, backfill_treasury_from_sales
        _, vid = self._product()
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": PRICE}]}).json()
        ref = sale["sale_reference"]
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            # Pretend the sale was made before the treasury followed sales.
            cur.execute("DELETE FROM cash_movements WHERE source_reference = ?", (ref,))
            cur.execute("DELETE FROM store_settings WHERE setting_key = ?", (TREASURY_BACKFILL_MARKER,))
        with db_session(commit=True) as conn:
            first = backfill_treasury_from_sales(conn.cursor())
        with db_session(commit=True) as conn:
            second = backfill_treasury_from_sales(conn.cursor())
        self.assertGreaterEqual(first["added"], 1)
        self.assertEqual(second["added"], 0, "runs once")
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(amount_dzd), 0) AS s FROM cash_movements WHERE source_reference = ?", (ref,))
            row = cur.fetchone()
        self.assertEqual((int(row["c"]), int(row["s"])), (1, PRICE), "added exactly once")

    def test_expenses_move_the_treasury_correctly(self):
        import datetime as _d
        cash0, bank0 = self._treasury()
        def exp(method, status, amount):
            r = self.client.post("/api/v1/admin/expenses", headers=self.h, json={
                "description": f"Test {method} {status}", "category": "loyer", "amount_dzd": amount,
                "expense_date": _d.date.today().isoformat(), "payment_method": method, "payment_status": status})
            self.assertEqual(r.status_code, 201, r.text)
            return r.json()
        exp("bank_transfer", "paid", 7000)
        cash1, bank1 = self._treasury()
        self.assertEqual((cash1 - cash0, bank1 - bank0), (0, -7000), "a bank transfer leaves the bank")
        pending = exp("cash", "pending", 3000)
        self.assertEqual(self._treasury(), (cash1, bank1), "unpaid: nothing moves yet")
        r = self.client.post(f"/api/v1/admin/expenses/{pending['id']}/pay?payment_method=cash", headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["payment_status"], "paid")
        cash2, _ = self._treasury()
        self.assertEqual(cash2 - cash1, -3000)
        self.assertEqual(self.client.post(f"/api/v1/admin/expenses/{pending['id']}/pay", headers=self.h).status_code, 400)
        d = self.client.delete(f"/api/v1/admin/expenses/{pending['id']}", headers=self.h)
        self.assertEqual(d.status_code, 200, d.text)
        cash3, _ = self._treasury()
        self.assertEqual(cash3, cash1, "deleting a paid expense puts the money back")

    def test_manual_treasury_entries_and_transfers(self):
        cash0, bank0 = self._treasury()
        r = self.client.post("/api/v1/admin/treasury/movements", headers=self.h, json={
            "movement_type": "outflow", "category": "bank_deposit", "amount_dzd": 5000, "notes": "Dépôt du soir"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(len(r.json()["movement_ids"]), 2, "a transfer is recorded on both accounts")
        cash1, bank1 = self._treasury()
        self.assertEqual((cash1 - cash0, bank1 - bank0), (-5000, 5000))
        r = self.client.post("/api/v1/admin/treasury/movements", headers=self.h, json={
            "movement_type": "inflow", "category": "capital_contribution", "account_type": "bank_account", "amount_dzd": 2000})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self._treasury(), (cash1, bank1 + 2000))
        bad = self.client.post("/api/v1/admin/treasury/movements", headers=self.h, json={"category": "nimporte", "amount_dzd": 10})
        self.assertEqual(bad.status_code, 422)

    def test_receipt_prefix_setting_is_used(self):
        _, vid = self._product()
        r = self.client.put("/api/v1/admin/fiscal/settings", headers=self.h, json={"settings": {"receipt_prefix_pos": "mus"}})
        self.assertEqual(r.status_code, 200, r.text)
        try:
            self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Compta", "opening_float_dzd": 0})
            sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
                "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": PRICE}]})
            self.assertEqual(sale.status_code, 201, sale.text)
            self.assertTrue(sale.json()["sale_reference"].startswith("MUS-"), sale.json()["sale_reference"])
        finally:
            self.client.put("/api/v1/admin/fiscal/settings", headers=self.h, json={"settings": {"receipt_prefix_pos": "POS"}})


if __name__ == "__main__":
    unittest.main()
