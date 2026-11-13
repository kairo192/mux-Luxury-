"""
Search engines & link previews: /produit/<slug>, /categorie/<slug>, /sitemap.xml
(served by the API behind nginx, see backend/app/seo.py).
"""
import json
import os
import re
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

from app import seo
from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="UTF-8" />
<title>Mus Luxury — Boutique</title>
<!-- SEO:START --><meta name="description" content="home" /><!-- SEO:END -->
</head><body><div id="shop"></div><script>/* shop */</script></body></html>"""


class TestSeoPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        cls._orig_template = seo.get_template
        seo.get_template = lambda: TEMPLATE
        os.environ["PUBLIC_STORE_URL"] = "https://mus-luxury.com"

    @classmethod
    def tearDownClass(cls):
        seo.get_template = cls._orig_template
        os.environ.pop("PUBLIC_STORE_URL", None)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"seo-cat-{sfx}", "name_fr": "Robes & Ensembles", "name_ar": "x", "name_en": "Dresses",
            "description_fr": "Robes de soirée.", "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.assertEqual(cat.status_code, 201, cat.text)
        self.cat = cat.json()
        a = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": self.cat["id"], "attr_key": "size", "label_fr": "Taille", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "M", "label_fr": "M"}]})
        self.assertEqual(a.status_code, 201, a.text)
        self.slug = f"robe-seo-{sfx}"
        p = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.cat["id"], "slug": self.slug, "sku": f"SEO-{sfx.upper()}",
            "name_fr": 'Robe "Étoile" </script><script>alert(1)</script>', "selling_price_dzd": 12500,
            "status": "published", "description_fr": "Une robe longue en satin.",
            "variants": [{"sku": f"SEO-{sfx.upper()}-M", "title": "M", "stock_qty": 4, "attributes": {"size": "M"}}]})
        self.assertEqual(p.status_code, 201, p.text)
        self.product_id = p.json()["id"]

    def _json_ld(self, html_text):
        return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.S)]

    def test_product_page_has_preview_tags_and_schema(self):
        r = self.client.get(f"/api/v1/seo/render/produit/{self.slug}")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.text
        self.assertIn('<div id="shop"></div>', body, "the shop itself must still be served")
        self.assertIn(f'<link rel="canonical" href="https://mus-luxury.com/produit/{self.slug}" />', body)
        self.assertIn('<meta property="og:type" content="product" />', body)
        self.assertIn('<meta property="product:price:amount" content="12500" />', body)
        self.assertNotIn('content="home"', body, "the default home block must be replaced")
        # Product name with HTML/script must never break out of the head.
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;/script&gt;", body)
        ld = self._json_ld(body)
        product = next(x for x in ld if x.get("@type") == "Product")
        self.assertEqual(product["offers"]["price"], "12500")
        self.assertEqual(product["offers"]["priceCurrency"], "DZD")
        self.assertTrue(product["offers"]["availability"].endswith("InStock"))
        self.assertNotIn("aggregateRating", product, "never invent ratings")
        self.assertTrue(any(x.get("@type") == "BreadcrumbList" for x in ld))
        # nginx applies the storefront CSP; the API must not add its strict one here.
        self.assertNotIn("content-security-policy", {k.lower() for k in r.headers.keys()})

    def test_category_page_lists_products(self):
        r = self.client.get(f"/api/v1/seo/render/categorie/{self.cat['slug']}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("<title>Robes &amp; Ensembles — Mus Luxury</title>", r.text)
        lst = next(x for x in self._json_ld(r.text) if x.get("@type") == "ItemList")
        self.assertIn(f"https://mus-luxury.com/produit/{self.slug}", [i["url"] for i in lst["itemListElement"]])

    def test_unknown_or_hidden_pages_are_404_noindex(self):
        r = self.client.get("/api/v1/seo/render/produit/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertIn("noindex", r.text)
        archived = self.client.delete(f"/api/v1/admin/products/{self.product_id}", headers=self.headers)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(self.client.get(f"/api/v1/seo/render/produit/{self.slug}").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/seo/render/admin/x").status_code, 404)

    def test_sitemap_lists_public_pages(self):
        r = self.client.get("/api/v1/seo/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/xml", r.headers["content-type"])
        self.assertIn("<loc>https://mus-luxury.com/</loc>", r.text)
        self.assertIn(f"<loc>https://mus-luxury.com/produit/{self.slug}</loc>", r.text)
        self.assertIn(f"<loc>https://mus-luxury.com/categorie/{self.cat['slug']}</loc>", r.text)

    def test_fallback_when_shop_unreachable(self):
        seo.get_template = lambda: None
        try:
            r = self.client.get(f"/api/v1/seo/render/produit/{self.slug}")
        finally:
            seo.get_template = lambda: TEMPLATE
        self.assertEqual(r.status_code, 200)
        self.assertIn('og:title', r.text)
        self.assertIn(f'url=/#/produit/{self.slug}', r.text)


if __name__ == "__main__":
    unittest.main()
