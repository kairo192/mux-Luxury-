"""
Archive / reactivate / delete a product (CMS → Produits):
  * a product with ANY history (online order, in-store sale, supplier
    purchase) is archived, never deleted — even with force=true — and no
    customer order is ever removed;
  * "Réactiver" (bulk status published) really brings it back: visible on
    the shop and sellable at the till again;
  * a product never sold nor bought is deleted for good.
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


class TestProductLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _product(self):
        sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"life-{sfx}", "name_fr": "Cycle", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        self.client.post("/api/v1/admin/category-attributes", headers=self.h, json={
            "category_id": cat["id"], "attr_key": "size", "label_fr": "Taille", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "M", "label_fr": "M"}]})
        slug = f"life-p-{sfx}"
        p = self.client.post("/api/v1/admin/products", headers=self.h, json={
            "category_id": cat["id"], "slug": slug, "sku": f"LIFE-{sfx.upper()}", "name_fr": f"Cycle {sfx}",
            "selling_price_dzd": 5000, "status": "published",
            "variants": [{"sku": f"LIFE-{sfx.upper()}-M", "title": "M", "stock_qty": 10, "attributes": {"size": "M"}}]})
        self.assertEqual(p.status_code, 201, p.text)
        pub = self.client.get(f"/api/v1/products/{slug}").json()
        return p.json()["id"], slug, pub["variants"][0]["id"]

    def _on_shop(self, slug):
        return self.client.get(f"/api/v1/products/{slug}").status_code == 200

    def test_product_with_online_order_is_archived_never_deleted_even_forced(self):
        pid, slug, vid = self._product()
        o = self.client.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Client Cycle", "phone": "0662000000", "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "1 rue du Cycle, Alger", "delivery_method": "home",
            "items": [{"variant_id": vid, "quantity": 1}]})
        self.assertEqual(o.status_code, 201, o.text)
        r = self.client.delete(f"/api/v1/admin/products/{pid}?hard_delete=true&force=true", headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["archived"]) ; self.assertFalse(r.json()["deleted"])
        orders = self.client.get("/api/v1/admin/orders", headers=self.h).json()["items"]
        kept = next(x for x in orders if x["id"] == o.json()["order_id"])
        self.assertEqual(len(kept["items"]), 1, "the customer order and its line must survive")
        self.assertFalse(self._on_shop(slug))

    def test_product_sold_in_store_only_is_archived(self):
        pid, slug, vid = self._product()
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"register_name": "Cycle", "opening_float_dzd": 0})
        s = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex}, json={
            "items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": 5000}]})
        self.assertEqual(s.status_code, 201, s.text)
        r = self.client.delete(f"/api/v1/admin/products/{pid}?hard_delete=true", headers=self.h)
        self.assertTrue(r.json()["archived"], r.text)
        self.assertEqual(r.json()["history"]["in_store_sale_lines"], 1)

    def test_reactivate_really_brings_the_product_back(self):
        pid, slug, vid = self._product()
        self.assertEqual(self.client.delete(f"/api/v1/admin/products/{pid}", headers=self.h).status_code, 200)
        self.assertFalse(self._on_shop(slug))
        r = self.client.post("/api/v1/admin/products/bulk-status", headers=self.h, json={"product_ids": [pid], "status": "published"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(self._on_shop(slug), "reactivated product must be on the shop again")
        v = self.client.get(f"/api/v1/products/{slug}").json()["variants"]
        self.assertTrue(v and v[0]["id"] == vid, "its variant must be sellable again")

    def test_never_sold_product_is_deleted(self):
        pid, slug, _ = self._product()
        r = self.client.delete(f"/api/v1/admin/products/{pid}?hard_delete=true", headers=self.h)
        self.assertTrue(r.json()["deleted"], r.text)
        prods = self.client.get("/api/v1/admin/products?include_archived=true", headers=self.h).json()["items"]
        self.assertFalse(any(p["id"] == pid for p in prods))


if __name__ == "__main__":
    unittest.main()
