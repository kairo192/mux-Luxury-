"""Shop items (boutique articles): quick add with colours / sizes, quantities and
barcodes; a boutique-only article is sold at the till but never online; stock
arrivals; missing barcodes; everything stays the same product / variant /
stock data the rest of the CMS uses."""
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

from app.main import app, ean_check_digit
from app.security import reset_rate_limits
from app.seed import seed_initial_data


class TestStoreItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        reset_rate_limits()
        r = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        cls.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        sfx = uuid.uuid4().hex[:6]
        cat = cls.client.post("/api/v1/admin/categories", headers=cls.h, json={
            "slug": f"boutique-{sfx}", "name_fr": "Boutique", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        cls.cat = cat["id"]
        for key, label, opts in (("couleur", "Couleur", ["Noir", "Rouge"]), ("taille", "Taille", ["S", "M"])):
            r = cls.client.post("/api/v1/admin/category-attributes", headers=cls.h, json={
                "category_id": cls.cat, "attr_key": key, "label_fr": label, "input_type": "single_select",
                "is_variant_axis": True, "options": [{"value": o, "label_fr": o} for o in opts]})
            assert r.status_code == 201, r.text
        # A required characteristic the online shop needs (not the boutique).
        r = cls.client.post("/api/v1/admin/category-attributes", headers=cls.h, json={
            "category_id": cls.cat, "attr_key": "matiere", "label_fr": "Matière", "input_type": "short_text", "is_required": True})
        assert r.status_code == 201, r.text
        cls.free_cat = cls.client.post("/api/v1/admin/categories", headers=cls.h, json={
            "slug": f"libre-{sfx}", "name_fr": "Libre", "name_ar": "x", "name_en": "x",
            "display_order": 2, "is_active": True, "show_on_homepage": False}).json()["id"]

    def setUp(self):
        reset_rate_limits()

    def _add(self, **over):
        body = {"name": f"Sac {uuid.uuid4().hex[:4]}", "category_id": self.cat, "price_dzd": 9000, "cost_dzd": 4000,
                "variants": [
                    {"attributes": {"couleur": "Noir", "taille": "S"}, "quantity": 3},
                    {"attributes": {"couleur": "Noir", "taille": "M"}, "quantity": 2},
                    {"attributes": {"couleur": "Bleu", "taille": "M"}, "quantity": 1, "price_dzd": 9500},
                ]}
        body.update(over)
        return self.client.post("/api/v1/admin/store/items", headers=self.h, json=body)

    def _variant(self, item, title):
        return next(v for v in item["variants"] if v["title"] == title)

    def test_quick_add_with_colours_sizes_and_barcodes(self):
        r = self._add(variants=[
            {"attributes": {"couleur": "Noir", "taille": "S"}, "quantity": 3},
            {"attributes": {"couleur": "Noir", "taille": "M"}, "quantity": 2, "barcode": "4006381333932"},
            {"attributes": {"couleur": "Bleu", "taille": "M"}, "quantity": 1, "price_dzd": 9500},
        ])
        # the scanned code above has a wrong check digit: refused, nothing created
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("invalide", r.json()["detail"])

        scanned = "4006381333931"  # a real manufacturer EAN-13
        r = self._add(variants=[
            {"attributes": {"couleur": "Noir", "taille": "S"}, "quantity": 3},
            {"attributes": {"couleur": "Noir", "taille": "M"}, "quantity": 2, "barcode": scanned},
            {"attributes": {"couleur": "Bleu", "taille": "M"}, "quantity": 1, "price_dzd": 9500},
        ])
        self.assertEqual(r.status_code, 201, r.text)
        item = r.json()
        self.assertEqual((item["sales_channel"], item["status"], item["sold_online"]), ("store", "published", False))
        self.assertTrue(item["sku"].startswith("MAG-"))
        self.assertEqual(item["total_stock"], 6)
        self.assertEqual(item["missing_barcodes"], 0)
        self.assertEqual(self._variant(item, "Noir / M")["barcode"], scanned)
        for title in ("Noir / S", "Bleu / M"):
            code = self._variant(item, title)["barcode"]
            self.assertEqual(len(code), 13)
            self.assertTrue(code.startswith("20"), "shop codes use the in-store range 20…")
            self.assertEqual(ean_check_digit(code[:12]), int(code[12]))
        self.assertEqual(self._variant(item, "Bleu / M")["price_dzd"], 9500)
        self.assertEqual(self._variant(item, "Noir / S")["price_dzd"], 9000)
        # "Bleu" was new: it is now an option of the category (same as the Products screen)
        attrs = self.client.get("/api/v1/admin/categories", headers=self.h).json()
        cat = next(c for c in (attrs.get("items") if isinstance(attrs, dict) else attrs) if c["id"] == self.cat)
        couleur = next(a for a in cat["attributes"] if a["attr_key"] == "couleur")
        self.assertIn("Bleu", [o["value"] for o in couleur["options"]])
        # the same barcode cannot go on a second article
        again = self._add(variants=[{"attributes": {"couleur": "Rouge"}, "quantity": 1, "barcode": scanned}])
        self.assertEqual(again.status_code, 409, again.text)
        # stock history: the pieces were recorded as arrivals of new variants
        mv = self.client.get("/api/v1/admin/inventory/movements", headers=self.h,
                             params={"variant_id": self._variant(item, "Noir / S")["id"]}).json()
        rows = mv.get("items", mv) if isinstance(mv, dict) else mv
        self.assertTrue(any(m["reason"] == "variant_created" and m["change_qty"] == 3 for m in rows), rows)

    def test_boutique_only_is_sold_at_the_till_never_online(self):
        item = self._add().json()
        code = self._variant(item, "Noir / S")["barcode"]
        vid = self._variant(item, "Noir / S")["id"]
        # not in the online shop
        listing = self.client.get("/api/v1/products", params={"q": item["name_fr"], "page_size": 50}).json()
        names = [p["name_fr"] for p in listing.get("items", listing.get("products", []))]
        self.assertNotIn(item["name_fr"], names)
        cur = self.client.get("/api/v1/admin/products", headers=self.h).json()
        slug = next(p["slug"] for p in cur.get("items", cur) if p["id"] == item["id"])
        self.assertEqual(self.client.get(f"/api/v1/products/{slug}").status_code, 404)
        self.assertNotIn(slug, self.client.get("/api/v1/seo/sitemap.xml").text)
        order = self.client.post("/api/v1/orders", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "full_name": "Client Boutique", "phone": "0661000000", "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "1 rue de la Boutique, Alger", "delivery_method": "home",
            "items": [{"variant_id": vid, "quantity": 1}]})
        self.assertIn(order.status_code, (404, 409, 422), order.text)
        # the till finds it by scanning, and by name
        found = self.client.get("/api/v1/admin/pos/lookup", headers=self.h, params={"code": code}).json()
        self.assertEqual((found["match_type"], found["variant"]["variant_id"]), ("variant", vid))
        by_name = self.client.get("/api/v1/admin/pos/lookup", headers=self.h, params={"code": item["name_fr"]}).json()
        self.assertEqual(by_name["results"][0]["id"], item["id"])
        snap = self.client.get("/api/v1/admin/pos/catalog/snapshot", headers=self.h).json()
        self.assertIn(item["id"], [p["id"] for p in snap["products"]])
        # and sells it
        self.client.post("/api/v1/admin/pos/register/open", headers=self.h, json={"opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers={**self.h, "Idempotency-Key": uuid.uuid4().hex},
                                json={"items": [{"variant_id": vid, "quantity": 1}], "payments": [{"method": "cash", "amount_dzd": 9000}]})
        self.assertEqual(sale.status_code, 201, sale.text)
        after = self.client.get("/api/v1/admin/store/items", headers=self.h, params={"q": code}).json()["items"][0]
        self.assertEqual(self._variant(after, "Noir / S")["stock_qty"], 2)

    def test_online_needs_what_the_online_shop_needs(self):
        r = self._add(sold_online=True)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("Matière", r.json()["detail"])
        ok = self._add(category_id=self.free_cat, sold_online=True,
                       variants=[{"title": "Modèle A", "quantity": 2}, {"title": "Modèle B", "quantity": 1}])
        self.assertEqual(ok.status_code, 201, ok.text)
        item = ok.json()
        self.assertEqual(sorted(v["title"] for v in item["variants"]), ["Modèle A", "Modèle B"])
        listing = self.client.get("/api/v1/products", params={"q": item["name_fr"], "page_size": 50}).json()
        self.assertIn(item["name_fr"], [p["name_fr"] for p in listing.get("items", listing.get("products", []))])
        # back to boutique only: gone from the online shop
        off = self.client.put(f"/api/v1/admin/store/items/{item['id']}", headers=self.h, json={"sold_online": False}).json()
        self.assertEqual(off["sales_channel"], "store")
        listing = self.client.get("/api/v1/products", params={"q": item["name_fr"], "page_size": 50}).json()
        self.assertNotIn(item["name_fr"], [p["name_fr"] for p in listing.get("items", listing.get("products", []))])

    def test_single_article_and_product_editor_still_works(self):
        r = self._add(category_id=self.cat, variants=[])
        self.assertEqual(r.status_code, 201, r.text)
        item = r.json()
        self.assertEqual([v["title"] for v in item["variants"]], ["Unique"])
        self.assertEqual(item["total_stock"], 0)
        # the Products screen edits it (boutique-only: the missing "Matière" does not block)
        full = next(p for p in self.client.get("/api/v1/admin/products", headers=self.h).json().get("items", [])
                    if p["id"] == item["id"])
        upd = self.client.put(f"/api/v1/admin/products/{item['id']}", headers=self.h, json={
            "expected_version": full["version"], "name_fr": item["name_fr"] + " (cuir)", "selling_price_dzd": 9900})
        self.assertEqual(upd.status_code, 200, upd.text)
        self.assertEqual(upd.json()["sales_channel"], "store")
        # …but selling it online asks for the missing characteristic
        upd = self.client.put(f"/api/v1/admin/products/{item['id']}", headers=self.h, json={
            "expected_version": upd.json()["version"], "name_fr": item["name_fr"], "selling_price_dzd": 9900, "sales_channel": "all"})
        self.assertEqual(upd.status_code, 422, upd.text)

    def test_receive_stock_new_colours_and_missing_barcodes(self):
        item = self._add().json()
        vid = self._variant(item, "Noir / S")["id"]
        r = self.client.post(f"/api/v1/admin/store/variants/{vid}/receive", headers=self.h, json={"quantity": 5})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["previous_qty"], r.json()["new_qty"]), (3, 8))
        self.assertEqual(self.client.post(f"/api/v1/admin/store/variants/{vid}/receive", headers=self.h,
                                          json={"quantity": 0}).status_code, 422)
        mv = self.client.get("/api/v1/admin/inventory/movements", headers=self.h, params={"variant_id": vid}).json()
        rows = mv.get("items", mv) if isinstance(mv, dict) else mv
        self.assertTrue(any(m["reason"] == "store_receipt" and m["change_qty"] == 5 for m in rows), rows)

        more = self.client.post(f"/api/v1/admin/store/items/{item['id']}/variants", headers=self.h, json={
            "variants": [{"attributes": {"couleur": "Rouge", "taille": "S"}, "quantity": 4}]})
        self.assertEqual(more.status_code, 201, more.text)
        self.assertEqual(more.json()["total_stock"], 6 + 5 + 4)
        dup = self.client.post(f"/api/v1/admin/store/items/{item['id']}/variants", headers=self.h, json={
            "variants": [{"attributes": {"couleur": "Rouge", "taille": "S"}, "quantity": 1}]})
        self.assertEqual(dup.status_code, 409, dup.text)

        # a variant made elsewhere without a barcode gets one here
        rouge = self._variant(more.json(), "Rouge / S")
        self.client.delete(f"/api/v1/admin/variants/{rouge['id']}/barcode", headers=self.h)
        listed = self.client.get("/api/v1/admin/store/items", headers=self.h, params={"show": "no_barcode"}).json()
        self.assertIn(item["id"], [i["id"] for i in listed["items"]])
        self.assertGreaterEqual(listed["missing_barcodes"], 1)
        gen = self.client.post(f"/api/v1/admin/store/items/{item['id']}/barcodes", headers=self.h).json()
        self.assertEqual(gen["generated"], 1)
        self.assertEqual(gen["item"]["missing_barcodes"], 0)
        self.assertTrue(self._variant(gen["item"], "Rouge / S")["barcode"].startswith("20"))

    def test_search_filters_and_rights(self):
        item = self._add().json()
        code = self._variant(item, "Bleu / M")["barcode"]
        for q in (code, item["sku"], item["name_fr"][:6]):
            got = self.client.get("/api/v1/admin/store/items", headers=self.h, params={"q": q}).json()
            self.assertIn(item["id"], [i["id"] for i in got["items"]], q)
        store_only = self.client.get("/api/v1/admin/store/items", headers=self.h, params={"show": "store"}).json()
        self.assertTrue(all(i["sales_channel"] == "store" for i in store_only["items"]))
        self.assertTrue(store_only["store_name"])
        self.assertEqual(self.client.get("/api/v1/admin/store/items").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/admin/store/items", json={}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
