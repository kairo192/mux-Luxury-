"""One business day through every module, checking that the screens agree.

Purchase -> stock, cost, supplier debt, journal, treasury. Online order ->
stock, dashboard, customer, delivery -> treasury. Till sale with discount and
refund -> stock, register, treasury, customer. Unpaid expense -> charges only.
Register close with a shortage -> treasury. Return after delivery -> stock,
revenue, treasury, customer. Then dashboards, reports and accounting must
all tell the same story.
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

from app.main import app, _shop_today
from app.seed import seed_initial_data
from app.security import reset_rate_limits

PRICE = 10_000


class TestBusinessFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.c = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.c.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.c.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"free_delivery_threshold_dzd": "0"}})
        # A register left open by another test would mix its cash into ours.
        if self.c.get("/api/v1/admin/pos/register/current", headers=self.h).json().get("session"):
            cur = self.c.get("/api/v1/admin/pos/register/current", headers=self.h).json()["session"]
            self.c.post("/api/v1/admin/pos/register/close", headers=self.h,
                        json={"counted_cash_dzd": max(int(cur.get("expected_cash_dzd") or 0), 0)})

    def tearDown(self):
        self.c.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"free_delivery_threshold_dzd": "25000"}})

    # ------------------------------------------------------------ helpers
    def ok(self, r, codes=(200, 201)):
        self.assertIn(r.status_code, codes, f"{r.request.method} {r.request.url}: {r.text[:300]}")
        return r.json()

    def get(self, path, **params):
        return self.ok(self.c.get("/api/v1" + path, headers=self.h, params=params))

    def post(self, path, body=None, **params):
        return self.ok(self.c.post("/api/v1" + path, headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json=body, params=params))

    def patch(self, path, body):
        return self.ok(self.c.patch("/api/v1" + path, headers=self.h, json=body))

    def stock(self):
        items = self.get("/admin/products", q=self.sku)
        items = items.get("items", items) if isinstance(items, dict) else items
        p = next(i for i in items if i["id"] == self.pid)
        return {v["id"]: v["stock_qty"] for v in p["variants"]}, int(p["purchase_cost_dzd"])

    def customer(self, phone):
        r = self.get("/admin/customers/search", q=phone)
        rows = r.get("items", r) if isinstance(r, dict) else r
        if not rows:
            return None
        row = rows[0]
        # The list, the search and the customer page must give the same total.
        detail = self.get(f"/admin/customers/{row['id']}")
        self.assertEqual(int(row["total_spent_dzd"]), detail["totals"]["combined_spent_dzd"])
        listed = next(i for i in self.get("/admin/customers")["items"] if i["id"] == row["id"])
        self.assertEqual(int(listed["total_spent_dzd"]), int(row["total_spent_dzd"]))
        return row

    def figures(self):
        t = self.get("/admin/treasury/summary")
        pnl = self.get("/admin/accounting/pnl")
        biz = self.get("/admin/dashboard/business")
        return {
            "cash": t["cash_balance_dzd"], "bank": t["bank_balance_dzd"],
            "revenue": pnl["total_revenue_dzd"], "cogs": pnl["cogs_dzd"], "opex": pnl["operating_expenses_dzd"],
            "net": pnl["net_operating_profit_dzd"], "stock_value": pnl["inventory_valuation_dzd"],
            "today": biz["sales"]["combined"]["today_revenue_dzd"],
        }

    # ------------------------------------------------------------ the day
    def test_a_business_day_keeps_every_screen_in_agreement(self):
        sfx = uuid.uuid4().hex[:5].upper()
        self.sku = f"FLX-{sfx}"
        cat = self.post("/admin/categories", {"slug": f"flx-{sfx.lower()}", "name_fr": "Flux", "name_ar": "x", "name_en": "x",
                                              "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.post("/admin/category-attributes", {"category_id": cat["id"], "attr_key": "color", "label_fr": "Couleur",
                                                 "input_type": "single_select", "is_variant_axis": True,
                                                 "options": [{"value": "noir", "label_fr": "Noir"}, {"value": "rouge", "label_fr": "Rouge"}]})
        prod = self.post("/admin/products", {
            "category_id": cat["id"], "slug": f"flx-{sfx.lower()}", "sku": self.sku, "name_fr": "Sac Flux",
            "selling_price_dzd": PRICE, "purchase_cost_dzd": 4000, "status": "published",
            "variants": [{"sku": f"{self.sku}-N", "title": "Noir", "stock_qty": 0, "attributes": {"color": "noir"}},
                         {"sku": f"{self.sku}-R", "title": "Rouge", "stock_qty": 0, "attributes": {"color": "rouge"}}]})
        self.pid = prod["id"]
        vN, vR = [v["id"] for v in self.c.get(f"/api/v1/products/flx-{sfx.lower()}").json()["variants"]]
        f0 = self.figures()

        # 1. Supplier purchase: 10 black + 2 red at 5 000, 1 000 shipping.
        sup = self.post("/admin/suppliers", {"name": f"Fournisseur {sfx}"})
        po = self.post("/admin/purchases", {"supplier_id": sup["id"], "shipping_dzd": 1000, "items": [
            {"product_id": self.pid, "variant_id": vN, "quantity": 10, "unit_cost_dzd": 5000},
            {"product_id": self.pid, "variant_id": vR, "quantity": 2, "unit_cost_dzd": 5000}]})
        self.assertEqual(po["total_cost_dzd"], 61000)
        self.post(f"/admin/purchases/{po['id']}/receive")
        stock, cost = self.stock()
        self.assertEqual(stock, {vN: 10, vR: 2})
        self.assertEqual(cost, 5083, "landed cost: 61 000 / 12 units (shipping included)")
        self.assertEqual(self.get(f"/admin/suppliers/{sup['id']}")["balance_dzd"], 61000, "we owe the supplier")
        self.assertEqual(self.figures()["stock_value"] - f0["stock_value"], 12 * 5083)
        self.post(f"/admin/purchases/{po['id']}/pay", payment_method="bank_transfer")
        self.assertEqual(self.get(f"/admin/suppliers/{sup['id']}")["balance_dzd"], 0)
        f1 = self.figures()
        self.assertEqual(f1["bank"] - f0["bank"], -61000, "paid by transfer: leaves the bank")
        self.assertEqual(f1["revenue"], f0["revenue"], "a purchase is not a sale")

        # 2. Online order: 2 black, home delivery.
        phone = "06" + str(uuid.uuid4().int)[:8]
        o = self.ok(self.c.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Amina Flux", "phone": phone, "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "1 rue du Flux, Alger", "delivery_method": "home",
            "items": [{"variant_id": vN, "quantity": 2}]}))
        order_total = o["total_dzd"]
        self.assertEqual(order_total, 2 * PRICE + o["delivery_fee_dzd"])
        self.assertEqual(self.stock()[0][vN], 8, "the order reserves its units")
        f2 = self.figures()
        self.assertEqual(f2["revenue"] - f1["revenue"], order_total)
        self.assertEqual(f2["cogs"] - f1["cogs"], 2 * 5083)
        self.assertEqual(f2["cash"], f1["cash"], "cash on delivery: no money yet")
        for st in ("confirmed", "preparing", "ready_for_shipment", "shipped", "delivered"):
            self.patch(f"/admin/orders/{o['order_id']}", {"status": st})
        f3 = self.figures()
        self.assertEqual(f3["cash"] - f2["cash"], order_total, "delivered: the money is collected")
        self.assertEqual(f3["revenue"], f2["revenue"], "delivery does not count the sale twice")
        cust = self.customer(phone)
        self.assertIsNotNone(cust, "the online order created the customer")
        self.assertEqual(cust["total_spent_dzd"], order_total)

        # 3. Till: 2 red with a 1 000 discount, paid 20 000 cash for 19 000.
        self.post("/admin/pos/register/open", {"register_name": "Caisse flux", "opening_float_dzd": 5000})
        sale = self.post("/admin/pos/sales", {"items": [{"variant_id": vR, "quantity": 2}], "order_discount_dzd": 1000,
                                              "customer_id": cust["id"],
                                              "payments": [{"method": "cash", "amount_dzd": 19000, "tendered_dzd": 20000}]})
        self.assertEqual(sale["total_dzd"], 19000)
        self.assertEqual(self.stock()[0][vR], 0)
        self.assertEqual(self.customer(phone)["total_spent_dzd"], order_total + 19000, "both channels on the customer")
        low = self.get("/admin/inventory/low-stock")
        low_items = low.get("items", low) if isinstance(low, dict) else low
        self.assertIn(f"{self.sku}-R", [i.get("sku") for i in low_items], "sold out: in the stock alerts")

        # Refund 1 red: gets back its share of what was paid (9 500), not 10 000.
        refund = self.post(f"/admin/pos/sales/{sale['id']}/refund", {"items": [{"variant_id": vR, "quantity": 1}], "refund_method": "cash"})
        self.assertEqual(refund["total_dzd"], 9500)
        self.assertEqual(self.stock()[0][vR], 1, "refunded unit back in stock")
        reg = self.get("/admin/pos/register/current")["session"]
        self.assertEqual(reg["expected_cash_dzd"], 5000 + 19000 - 9500)
        f4 = self.figures()
        self.assertEqual(f4["cash"] - f3["cash"], 19000 - 9500)
        self.assertEqual(f4["revenue"] - f3["revenue"], 9500)
        self.assertEqual(f4["today"] - f3["today"], 9500, "business dashboard = accounting")

        # 4. Unpaid expense: a charge, but no money moves yet.
        self.post("/admin/expenses", {"description": "Électricité flux", "category": "electricite_eau", "amount_dzd": 2500,
                                      "payment_method": "cash", "payment_status": "pending"})
        f5 = self.figures()
        self.assertEqual(f5["opex"] - f4["opex"], 2500)
        self.assertEqual(f5["net"] - f4["net"], -2500)
        self.assertEqual(f5["cash"], f4["cash"])

        # 5. Close the register 500 short: the treasury follows the drawer.
        closed = self.post("/admin/pos/register/close", {"counted_cash_dzd": 14000})
        self.assertEqual(closed["variance_dzd"], -500)
        f6 = self.figures()
        self.assertEqual(f6["cash"] - f5["cash"], -500, "shortage recorded as 'Écart de caisse'")

        # 6. The delivered order comes back.
        self.patch(f"/admin/orders/{o['order_id']}", {"status": "returned"})
        f7 = self.figures()
        self.assertEqual(self.stock()[0][vN], 10, "returned units back in stock")
        self.assertEqual(f7["revenue"] - f6["revenue"], -order_total, "a returned order is not a sale")
        self.assertEqual(f7["cash"] - f6["cash"], -order_total, "the customer is paid back")
        self.assertEqual(self.customer(phone)["total_spent_dzd"], 9500)

        # 7. Stock that leaves without a sale is a loss in the accounts.
        def net_both():
            pnl = self.get("/admin/accounting/pnl")
            biz = self.get("/admin/dashboard/business")["margin_month"]
            return pnl["net_operating_profit_dzd"], biz["net_profit_dzd"], pnl["inventory_valuation_dzd"]
        n0 = net_both()
        self.post("/admin/inventory/write-off", {"variant_id": vN, "quantity": 1, "reason": "damaged"})
        n1 = net_both()
        self.assertEqual((n1[0] - n0[0], n1[1] - n0[1], n1[2] - n0[2]), (-5083, -5083, -5083),
                         "damaged bag: loss at cost in Comptabilité and Analytique, stock value down")
        self.post("/admin/inventory/write-off", {"variant_id": vN, "quantity": 1, "reason": "return_to_supplier"})
        n2 = net_both()
        self.assertEqual((n2[0], n2[1]), (n1[0], n1[1]), "a return to the supplier is not a loss")
        count = self.post("/admin/inventory/counts", {"name": "Comptage flux"})
        self.ok(self.c.put(f"/api/v1/admin/inventory/counts/{count['id']}/lines", headers=self.h,
                           json={"variant_id": vN, "counted_qty": self.stock()[0][vN] + 1}))
        self.post(f"/admin/inventory/counts/{count['id']}/apply")
        n3 = net_both()
        self.assertEqual(n3[0] - n2[0], 5083, "a unit found at the count reduces the losses")
        self.assertEqual(self.stock()[0][vN], 9, "10 - damaged - returned + found")

        # 8. Today's reports tell the same story as the dashboards.
        today = _shop_today()
        rng = {"from": today, "to": today}
        sales = self.get("/admin/reports/sales", **rng)["totals"]
        self.assertGreaterEqual(sales["in_store_refunds_dzd"], 9500)
        biz = self.get("/admin/dashboard/business")["sales"]["combined"]["today_revenue_dzd"]
        self.assertEqual(biz - f0["today"], 9500, "the day's net: one red bag kept")
        mv = self.get("/admin/reports/inventory-movements", **rng, variant_id=vN)
        summary = mv.get("summary") or mv.get("totals")
        self.assertEqual(summary["net_change"], 9, "movements add up to the stock: +10 -2 +2 -1 -1 +1")
        self.assertEqual(self.get("/admin/accounting/ledger")["is_balanced"], True)


    def test_promo_code_is_kept_on_the_order_and_given_back_on_cancel(self):
        code = "FLX" + uuid.uuid4().hex[:6].upper()
        self.post("/admin/coupons", {"code": code, "discount_type": "fixed_dzd", "discount_value": 1000, "usage_limit": 1})
        sfx = uuid.uuid4().hex[:5]
        cat = self.post("/admin/categories", {"slug": f"cp-{sfx}", "name_fr": "Promo", "name_ar": "x", "name_en": "x",
                                              "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.post("/admin/category-attributes", {"category_id": cat["id"], "attr_key": "size", "label_fr": "Taille",
                                                 "input_type": "single_select", "is_variant_axis": True,
                                                 "options": [{"value": "u", "label_fr": "U"}]})
        self.post("/admin/products", {"category_id": cat["id"], "slug": f"cp-{sfx}", "sku": f"CP-{sfx.upper()}", "name_fr": "Promo",
                                      "selling_price_dzd": PRICE, "status": "published",
                                      "variants": [{"sku": f"CP-{sfx.upper()}-U", "title": "U", "stock_qty": 5, "attributes": {"size": "u"}}]})
        vid = self.c.get(f"/api/v1/products/cp-{sfx}").json()["variants"][0]["id"]

        def order():
            return self.c.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
                "full_name": "Client Promo", "phone": "0770" + str(uuid.uuid4().int)[:6], "wilaya_code": "16",
                "commune": "Alger Centre", "delivery_address": "2 rue Promo, Alger", "delivery_method": "home",
                "coupon_code": code.lower(), "items": [{"variant_id": vid, "quantity": 1}]})

        first = order()
        self.assertEqual(first.status_code, 201, first.text)
        listed = next(o for o in self.get("/admin/orders")["items"] if o["id"] == first.json()["order_id"])
        self.assertEqual((listed["coupon_code"], listed["discount_dzd"]), (code, 1000), "the order shows the code used")
        self.assertEqual(order().status_code, 400, "single-use code already used")
        cpn = next(c for c in self.get("/admin/coupons")["items"] if c["code"] == code)
        self.assertEqual((cpn["usage_count"], cpn["orders_count"], cpn["discount_given_dzd"]), (1, 1, 1000))
        self.patch(f"/admin/orders/{first.json()['order_id']}", {"status": "cancelled"})
        cpn = next(c for c in self.get("/admin/coupons")["items"] if c["code"] == code)
        self.assertEqual((cpn["usage_count"], cpn["orders_count"]), (0, 0), "cancelled: the use is given back")
        self.assertEqual(order().status_code, 201, "the code works again")

        # The invoice of that order carries the discount and the shop's contacts
        # from the settings (not fixed text).
        self.c.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"store_phone": "0550001122", "fiscal_phone": ""}})
        try:
            inv = self.get(f"/admin/orders/{first.json()['order_id']}/invoice")
            self.assertEqual(inv["discount_dzd"], 1000)
            self.assertEqual(inv["coupon_code"], code)
            self.assertEqual(inv["boutique_info"]["phone"], "0550001122")
        finally:
            self.c.put("/api/v1/admin/settings", headers=self.h, json={"settings": {"store_phone": "0655534154", "fiscal_phone": "0655534154"}})


    def test_shop_data_is_never_served_stale(self):
        """A sold-out item, a new price, an archived product or a new delivery
        price must reach the shop on the next load: the browser revalidates."""
        for path in ("/api/v1/products", "/api/v1/categories", "/api/v1/delivery-zones"):
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, path)
            cc = r.headers.get("cache-control", "")
            self.assertIn("no-cache", cc, path)
            self.assertNotIn("max-age=3600", cc)
            etag = r.headers.get("etag")
            if etag:
                self.assertEqual(self.c.get(path, headers={"If-None-Match": etag}).status_code, 304, path)

        # Shared server cache (1 vCPU): repeated loads are answered from it, and
        # a change made in the CMS empties it at once.
        from app import main as m
        m.public_cache_clear()
        self.c.get("/api/v1/products", params={"page_size": 50})
        self.assertTrue(any(k.startswith("/api/v1/products?") for k in m._PUBLIC_CACHE), "answer kept for other visitors")
        items = self.c.get("/api/v1/products", params={"page_size": 50}).json()["items"]
        if items:
            prod = items[0]
            full = next(p for p in self.get("/admin/products")["items"] if p["id"] == prod["id"])
            new_price = int(full["selling_price_dzd"]) + 100
            self.ok(self.c.put(f"/api/v1/admin/products/{prod['id']}", headers=self.h,
                               json={**full, "selling_price_dzd": new_price, "expected_version": full["version"]}))
            again = self.c.get("/api/v1/products", params={"page_size": 50}).json()["items"]
            self.assertEqual(next(p for p in again if p["id"] == prod["id"])["selling_price_dzd"], new_price,
                             "a CMS change is visible on the very next shop request")


    def test_order_tracking_shows_only_public_fields(self):
        pr = self.c.get("/api/v1/products", params={"page_size": 50}).json()["items"]
        vid = next(v["id"] for p in pr for v in p["variants"] if (v.get("stock_qty") or v.get("stock") or 0) > 0)
        phone = "0662" + str(uuid.uuid4().int)[:6]
        o = self.ok(self.c.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Suivi Public", "phone": phone, "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "4 rue du Suivi, Alger", "delivery_method": "home", "items": [{"variant_id": vid, "quantity": 1}]}))
        t = self.c.get("/api/v1/orders/track", params={"reference": o["order_reference"], "phone": phone}).json()
        self.assertEqual(t["status"], "new")
        for private in ("id", "customer_id", "customer_phone", "idempotency_hash", "internal_notes", "stock_deducted"):
            self.assertNotIn(private, t)


if __name__ == "__main__":
    unittest.main()
