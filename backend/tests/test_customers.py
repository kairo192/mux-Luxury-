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


class TestCustomers(unittest.TestCase):
    """Customer management: walk-in creation, search, cross-channel history."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        ed = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"})
        cls.editor_headers = {"Authorization": f"Bearer {ed.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        # unique Algerian-format phone per test
        self.phone = "055" + "".join(c for c in self.suffix if c.isdigit()).ljust(7, "0")[:7]
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]

    def _create_category(self) -> int:
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"cust-{self.suffix}", "name_fr": f"Cust {self.suffix}", "name_ar": "x", "name_en": "Cust",
            "display_order": 99, "is_active": True, "show_on_homepage": False})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        a = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        assert a.status_code == 201, a.text
        return cid

    def _create_product(self) -> dict:
        sku = f"CU-{self.suffix.upper()}"
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"cust-product-{self.suffix}", "sku": sku,
            "name_fr": f"Cust {self.suffix}", "selling_price_dzd": 3000, "status": "published",
            "variants": [{"sku": f"{sku}-A", "title": "A", "stock_qty": 10, "attributes": {"slot": "A"}}]})
        assert r.status_code == 201, r.text
        return r.json()

    # ------------------------------------------------------------------ tests
    def test_01_create_walkin_minimal(self):
        r = self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": "Client Passage", "phone": self.phone})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["phone"], self.phone)
        self.assertEqual(r.json()["wilaya_code"], "")  # walk-in: no delivery details required

    def test_02_duplicate_phone_conflict(self):
        self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": "Client Un", "phone": self.phone})
        dup = self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": "Client Deux", "phone": self.phone})
        self.assertEqual(dup.status_code, 409, dup.text)

    def test_03_search_by_name_and_phone(self):
        name = f"Rechercheable {self.suffix}"
        self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": name, "phone": self.phone})
        by_name = self.client.get("/api/v1/admin/customers/search", headers=self.headers, params={"q": "Rechercheable"})
        self.assertTrue(any(c["phone"] == self.phone for c in by_name.json()["items"]))
        by_phone = self.client.get("/api/v1/admin/customers/search", headers=self.headers, params={"q": self.phone[-5:]})
        self.assertTrue(any(c["phone"] == self.phone for c in by_phone.json()["items"]))

    def test_04_combined_history(self):
        cid = self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": "Fidèle", "phone": self.phone}).json()["id"]
        # online order with same phone links to this customer
        order = self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"cust-ord-{self.suffix}"}, json={
            "full_name": "Fidèle", "phone": self.phone, "wilaya_code": "09", "commune": "Ouled Yaïch",
            "delivery_address": "Rue X", "delivery_method": "home", "items": [{"variant_id": self.variant["id"], "quantity": 1}]})
        self.assertEqual(order.status_code, 201, order.text)
        # in-store sale attached to the customer
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant["id"], "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 6000}], "customer_id": cid})
        self.assertEqual(sale.status_code, 201, sale.text)
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

        detail = self.client.get(f"/api/v1/admin/customers/{cid}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        t = detail.json()["totals"]
        self.assertEqual(t["online_orders"], 1)
        self.assertEqual(t["in_store_sales"], 1)
        self.assertEqual(t["in_store_spent_dzd"], 6000)
        self.assertEqual(t["combined_spent_dzd"], t["online_spent_dzd"] + 6000)
        channels = {h["channel"] for h in detail.json()["history"]}
        self.assertEqual(channels, {"online", "in_store"})

    def test_05_update_notes(self):
        cid = self.client.post("/api/v1/admin/customers", headers=self.headers, json={"full_name": "Notable", "phone": self.phone}).json()["id"]
        up = self.client.put(f"/api/v1/admin/customers/{cid}", headers=self.headers, json={"notes": "Cliente VIP", "email": "vip@example.com"})
        self.assertEqual(up.status_code, 200, up.text)
        self.assertEqual(up.json()["notes"], "Cliente VIP")
        self.assertEqual(up.json()["email"], "vip@example.com")

    def test_06_permissions(self):
        # product_manager has neither orders:write nor pos:sell
        self.assertEqual(self.client.get("/api/v1/admin/customers/search", headers=self.editor_headers, params={"q": "x"}).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/admin/customers/search", params={"q": "x"}).status_code, 401)

    def test_list_is_paged_best_customers_first(self):
        """The list comes in pages (a shop with 20 000 customers sent 5 MB and
        took minutes); total tells the CMS how many there are."""
        r = self.client.get("/api/v1/admin/customers?limit=2", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertLessEqual(len(d["items"]), 2)
        self.assertGreaterEqual(d["total"], len(d["items"]))
        spent = [c["total_spent_dzd"] for c in d["items"]]
        self.assertEqual(spent, sorted(spent, reverse=True))
        nxt = self.client.get("/api/v1/admin/customers?limit=2&offset=2", headers=self.headers).json()
        self.assertFalse({c["id"] for c in d["items"]} & {c["id"] for c in nxt["items"]}, "pages do not overlap")
        self.assertEqual(self.client.get("/api/v1/admin/customers?limit=0", headers=self.headers).status_code, 422)

    def test_orders_search_finds_old_orders(self):
        """Commandes shows the newest 100; the search finds any order by number,
        phone (spaces ignored) or name (any case), also with a status filter."""
        from app.database import db_session
        ref = "LUX-SRCH-" + self.phone[-6:]
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM customers ORDER BY id LIMIT 1")
            cid = cur.fetchone()["id"]
            cur.execute(
                """INSERT INTO orders (order_reference, customer_id, customer_name, customer_phone, wilaya_code, wilaya_name,
                       commune, delivery_address, delivery_method, payment_method, subtotal_dzd, delivery_fee_dzd, total_dzd, status)
                   VALUES (?, ?, 'Yasmine Benali', ?, '16', 'Alger', 'Hydra', '1 rue', 'home', 'cod', 5000, 400, 5400, 'delivered')""",
                (ref, cid, self.phone),
            )
        def found(**params):
            r = self.client.get("/api/v1/admin/orders", headers=self.headers, params=params)
            self.assertEqual(r.status_code, 200, r.text)
            return [o["order_reference"] for o in r.json()["items"]]
        self.assertIn(ref, found(q=ref.lower()))
        spaced = " ".join([self.phone[:4], self.phone[4:6], self.phone[6:8], self.phone[8:]])
        self.assertIn(ref, found(q=spaced))
        self.assertIn(ref, found(q="yasmine BENALI"))
        self.assertIn(ref, found(q="Benali", status="delivered"))
        self.assertNotIn(ref, found(q="Benali", status="new"))
        self.assertEqual(found(q="zzz-nothing-zzz"), [])


if __name__ == "__main__":
    unittest.main()
