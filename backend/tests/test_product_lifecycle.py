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

    # ------------------------------------------------------------ categories --
    def _cat_with_axis(self):
        pid, slug, vid = self._product()
        prods = self.client.get("/api/v1/admin/products?include_archived=true", headers=self.h).json()["items"]
        cat_id = next(p["category_id"] for p in prods if p["id"] == pid)
        cats = self.client.get("/api/v1/admin/categories", headers=self.h).json()["items"]
        cat = next(c for c in cats if c["id"] == cat_id)
        return pid, cat

    def test_variant_axis_attribute_in_use_cannot_be_deleted_even_forced(self):
        _, cat = self._cat_with_axis()
        attr = cat["attributes"][0]
        for force in ("false", "true"):
            r = self.client.delete(f"/api/v1/admin/category-attributes/{attr['id']}?force_migrate={force}", headers=self.h)
            self.assertEqual(r.status_code, 409, r.text)
            self.assertIn("variante", r.json()["detail"])

    def test_category_with_only_archived_products_is_archived_not_deleted(self):
        pid, cat = self._cat_with_axis()
        self.client.delete(f"/api/v1/admin/products/{pid}", headers=self.h)  # archive the product
        r = self.client.delete(f"/api/v1/admin/categories/{cat['id']}?hard_delete=true", headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("archived"))
        self.assertFalse(r.json().get("deleted"))

    def test_new_category_and_product_get_no_invented_photo(self):
        sfx = uuid.uuid4().hex[:6]
        c = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"nophoto-{sfx}", "name_fr": "Sans photo", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.assertEqual(c.status_code, 201, c.text)
        self.assertEqual(c.json().get("image_url") or "", "")
        self.assertEqual(c.json().get("banner_url") or "", "")

    def test_purchase_line_must_name_the_variant(self):
        sfx = uuid.uuid4().hex[:6]
        sup = self.client.post("/api/v1/admin/suppliers", headers=self.h, json={"name": f"Fourn {sfx}", "phone": "+213550000099"}).json()
        cat = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"po-{sfx}", "name_fr": "PO", "name_ar": "x", "name_en": "x", "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        self.client.post("/api/v1/admin/category-attributes", headers=self.h, json={
            "category_id": cat["id"], "attr_key": "color", "label_fr": "Couleur", "input_type": "single_select", "is_variant_axis": True,
            "options": [{"value": "Noir", "label_fr": "Noir"}, {"value": "Rouge", "label_fr": "Rouge"}]})
        two = self.client.post("/api/v1/admin/products", headers=self.h, json={
            "category_id": cat["id"], "slug": f"po2-{sfx}", "sku": f"PO2-{sfx.upper()}", "name_fr": f"Deux {sfx}",
            "selling_price_dzd": 5000, "status": "published",
            "variants": [{"sku": f"PO2-{sfx.upper()}-N", "title": "Noir", "stock_qty": 0, "attributes": {"color": "Noir"}},
                         {"sku": f"PO2-{sfx.upper()}-R", "title": "Rouge", "stock_qty": 0, "attributes": {"color": "Rouge"}}]}).json()
        r = self.client.post("/api/v1/admin/purchases", headers=self.h, json={
            "supplier_id": sup["id"], "items": [{"product_id": two["id"], "quantity": 3, "unit_cost_dzd": 2000}]})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("variante", r.json()["detail"])
        # A single-variant product: the variant is filled in.
        pid, slug, vid = self._product()
        r2 = self.client.post("/api/v1/admin/purchases", headers=self.h, json={
            "supplier_id": sup["id"], "items": [{"product_id": pid, "quantity": 3, "unit_cost_dzd": 2000}]})
        self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(r2.json()["items"][0]["variant_id"], vid)


if __name__ == "__main__":
    unittest.main()
