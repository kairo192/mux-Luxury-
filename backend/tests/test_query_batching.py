"""
No N+1 queries in the lists: the number of SQL queries a list makes must not
grow with the number of rows it returns (child rows are loaded for all parents
at once, with a JOIN or one `IN (...)` query, not one query per row).

Queries are counted on SQLite (it reports every statement run); the results
themselves are checked on both engines, including the 30-day sales of the
low-stock report.
"""
import os
import tempfile
import unittest
import uuid
from unittest import mock

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits


TRACED = os.environ.get("LUXE_DB_ENGINE") != "postgres"


class TestQueryBatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ---------------------------------------------------------------- helpers
    def _queries(self, path, table):
        """Runs GET path and returns how many statements read `table` (0 when the
        engine cannot report its statements; the counts then compare equal)."""
        statements = []
        real = database.get_connection

        def traced():
            conn = real()
            if TRACED:
                conn.set_trace_callback(statements.append)
            return conn

        # Every route opens its connection through app.database.get_connection.
        with mock.patch.object(database, "get_connection", traced):
            r = self.client.get(path, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        return sum(1 for s in statements if f" {table} " in f" {s} ".replace("\n", " ")), r.json()

    def _category(self, n_attrs=2):
        sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"qb-{sfx}", "name_fr": f"QB {sfx}", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        for i in range(n_attrs):
            r = self.client.post("/api/v1/admin/category-attributes", headers=self.h, json={
                "category_id": cat["id"], "attr_key": f"k{i}", "label_fr": f"K{i}", "input_type": "single_select",
                "is_variant_axis": i == 0, "options": [{"value": "A", "label_fr": "A"}, {"value": "B", "label_fr": "B"}]})
            self.assertEqual(r.status_code, 201, r.text)
        return cat

    def _product(self, stock=50):
        cat = self._category(n_attrs=1)
        sfx = uuid.uuid4().hex[:6]
        p = self.client.post("/api/v1/admin/products", headers=self.h, json={
            "category_id": cat["id"], "slug": f"qb-p-{sfx}", "sku": f"QB-{sfx.upper()}", "name_fr": "Article QB",
            "selling_price_dzd": 10000, "purchase_cost_dzd": 4000, "status": "published",
            "variants": [{"sku": f"QB-{sfx.upper()}-A", "title": "A", "stock_qty": stock, "attributes": {"k0": "A"}}]})
        self.assertEqual(p.status_code, 201, p.text)
        return p.json()["id"], p.json()["variants"][0]["id"], p.json()["variants"][0]["sku"]

    def _order(self, vid, qty=1):
        r = self.client.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Client QB", "phone": "0661000000", "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "1 rue des Requêtes, Alger", "delivery_method": "home",
            "items": [{"variant_id": vid, "quantity": qty}]})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    # ---------------------------------------------------------------- tests
    def test_categories_with_attributes_and_options(self):
        self._category()
        before, _ = self._queries("/api/v1/admin/categories", "category_attribute_options")
        for _ in range(3):
            self._category()
        after, body = self._queries("/api/v1/admin/categories", "category_attribute_options")
        self.assertEqual(before, after)
        if TRACED:
            self.assertLessEqual(after, 1)
        mine = [c for c in body["items"] if c["slug"].startswith("qb-")]
        self.assertTrue(all(len(c["attributes"]) == 2 for c in mine))
        self.assertTrue(all([o["value"] for o in a["options"]] == ["A", "B"] for c in mine for a in c["attributes"]))
        self.assertTrue(all("attribute_id" not in o for c in mine for a in c["attributes"] for o in a["options"]))
        for path in ("/api/v1/categories",):       # the shop's own list too
            n, _ = self._queries(path, "category_attribute_options")
            if TRACED:
                self.assertLessEqual(n, 1)

    def test_orders_with_their_items(self):
        _, vid, _ = self._product()
        self._order(vid)
        d1, _ = self._queries("/api/v1/admin/dashboard", "order_items")
        s1, _ = self._queries("/api/v1/admin/sync/delta?since_order_id=0&since_movement_id=0", "order_items")
        for _ in range(3):
            self._order(vid, 2)
        d2, dash = self._queries("/api/v1/admin/dashboard", "order_items")
        s2, sync = self._queries("/api/v1/admin/sync/delta?since_order_id=0&since_movement_id=0", "order_items")
        self.assertEqual((d1, s1), (d2, s2))
        newest = sync["new_orders"][0]
        self.assertEqual([(i["variant_id"], i["quantity"]) for i in newest["items"]], [(vid, 2)])
        self.assertTrue(all(o["items"] for o in dash["recent_orders"]))

    def test_purchase_orders_with_their_lines(self):
        pid, vid, _ = self._product()
        sup = self.client.post("/api/v1/admin/suppliers", headers=self.h, json={"name": f"Sup {uuid.uuid4().hex[:4]}"}).json()

        def po():
            r = self.client.post("/api/v1/admin/purchases", headers=self.h, json={
                "supplier_id": sup["id"], "shipping_dzd": 0, "tax_dzd": 0,
                "items": [{"product_id": pid, "variant_id": vid, "quantity": 4, "unit_cost_dzd": 2000}]})
            self.assertEqual(r.status_code, 201, r.text)
            return r.json()["id"]

        po()
        before, _ = self._queries("/api/v1/admin/purchases", "purchase_order_items")
        last = [po() for _ in range(3)][-1]
        after, body = self._queries("/api/v1/admin/purchases", "purchase_order_items")
        self.assertEqual(before, after)
        mine = next(p for p in body["items"] if p["id"] == last)
        self.assertEqual([(i["variant_id"], i["quantity_ordered"]) for i in mine["items"]], [(vid, 4)])

    def test_roles_with_their_permissions_in_one_query(self):
        n, body = self._queries("/api/v1/admin/roles", "role_permissions")
        if TRACED:
            self.assertEqual(n, 2)                 # login check + the list itself (one JOIN)
        owner = next(r for r in body["items"] if r["name"] == "super_admin")
        self.assertIn("settings:write", owner["permissions"])
        self.assertEqual(owner["permissions"], sorted(owner["permissions"]))

    def test_low_stock_sales_are_counted_once_for_all_variants(self):
        _, vid, sku = self._product(stock=5)
        self._order(vid, 2)                                    # web order: counts
        cancelled = self._order(vid, 1)                        # cancelled: never counts
        self.client.patch(f"/api/v1/admin/orders/{cancelled['order_id']}", headers=self.h, json={"status": "cancelled"})
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "QB", "opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 2}], "payments": [{"method": "cash", "amount_dzd": 20000}]})
        self.assertEqual(sale.status_code, 201, sale.text)    # till sale: +2
        ref = self.client.post(f"/api/v1/admin/pos/sales/{sale.json()['id']}/refund", headers=self.h,
                               json={"items": [{"variant_id": vid, "quantity": 1}], "refund_method": "cash"})
        self.assertEqual(ref.status_code, 201, ref.text)      # till refund: -1

        path = "/api/v1/admin/inventory/low-stock?limit=500"
        before, body = self._queries(path, "pos_sale_items")
        row = next(i for i in body["items"] if i["sku"] == sku)
        self.assertEqual(row["velocity_30d"], 2 + 2 - 1)
        for _ in range(3):
            self._product(stock=1)
        after, _ = self._queries(path, "pos_sale_items")
        self.assertEqual(before, after)
        if TRACED:
            self.assertLessEqual(after, 1)


if __name__ == "__main__":
    unittest.main()
