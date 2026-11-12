"""
Everything the shop shows on its home page and at checkout comes from the CMS
and the server — nothing fixed in the page:

  * free delivery threshold (CMS → Contenu) is applied by the SERVER, on the
    preview and on the stored order, and 0 switches it off;
  * banners (hero + promo cards) can be created, edited, hidden and are the
    only ones the shop receives;
  * home blocks can be switched on/off, including ones never saved before;
  * the dashboard chart gets real per-day revenue, and stock figures count
    only products still in the catalogue.
"""
import json
import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone

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


class TestStorefrontContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.assertEqual(r.status_code, 200, r.text)
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def tearDown(self):
        # Leave the seeded threshold as it was for other test files.
        self._set_threshold("25000")

    # ------------------------------------------------------------ helpers --
    def _set_threshold(self, value):
        r = self.client.put("/api/v1/admin/settings", headers=self.headers,
                            json={"settings": {"free_delivery_threshold_dzd": value}})
        self.assertEqual(r.status_code, 200, r.text)

    def _product(self, price, stock=10):
        sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"sc-cat-{sfx}", "name_fr": "Cat test", "name_ar": "x", "name_en": "x",
            "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.assertEqual(cat.status_code, 201, cat.text)
        cat_id = cat.json()["id"]
        a = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cat_id, "attr_key": "size", "label_fr": "Taille", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "M", "label_fr": "M"}]})
        self.assertEqual(a.status_code, 201, a.text)
        p = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cat_id, "slug": f"sc-prod-{sfx}", "sku": f"SC-{sfx.upper()}",
            "name_fr": "Article test", "selling_price_dzd": price, "status": "published",
            "variants": [{"sku": f"SC-{sfx.upper()}-M", "title": "M", "stock_qty": stock, "attributes": {"size": "M"}}]})
        self.assertEqual(p.status_code, 201, p.text)
        prod = self.client.get(f"/api/v1/products/sc-prod-{sfx}").json()
        return prod, prod["variants"][0]["id"]

    def _order(self, variant_id, qty=1):
        r = self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"sc-{uuid.uuid4().hex}"}, json={
            "full_name": "Client Test", "phone": "0655000000", "wilaya_code": "16", "commune": "Alger Centre",
            "delivery_address": "12 rue des Tests, Alger", "delivery_method": "home",
            "items": [{"variant_id": variant_id, "quantity": qty}]})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    # ------------------------------------------------------ free delivery --
    def test_free_delivery_threshold_is_applied_by_the_server(self):
        self._set_threshold("20000")
        _, vid_big = self._product(30000)
        _, vid_small = self._product(5000)

        prev = self.client.get("/api/v1/delivery-zones/calculate",
                               params={"wilaya_code": "16", "delivery_method": "home", "subtotal_dzd": 30000}).json()
        self.assertTrue(prev["free_delivery_applied"])
        self.assertEqual(prev["delivery_fee_dzd"], 0)
        self.assertEqual(prev["total_dzd"], 30000)

        big = self._order(vid_big)
        self.assertEqual(big["delivery_fee_dzd"], 0, "order above the threshold must be stored with free delivery")
        self.assertEqual(big["total_dzd"], 30000)

        small = self._order(vid_small)
        self.assertGreater(small["delivery_fee_dzd"], 0)
        self.assertEqual(small["total_dzd"], 5000 + small["delivery_fee_dzd"])

    def test_threshold_zero_switches_free_delivery_off(self):
        self._set_threshold("0")
        _, vid = self._product(40000)
        prev = self.client.get("/api/v1/delivery-zones/calculate",
                               params={"wilaya_code": "16", "delivery_method": "home", "subtotal_dzd": 40000}).json()
        self.assertFalse(prev["free_delivery_applied"])
        self.assertEqual(prev["free_delivery_threshold_dzd"], 0)
        order = self._order(vid)
        self.assertGreater(order["delivery_fee_dzd"], 0)

    # ------------------------------------------------------------ banners --
    def test_banner_create_edit_hide_and_public_layout(self):
        r = self.client.post("/api/v1/admin/banners", headers=self.headers, json={
            "position": "hero", "title_fr": "Nouvelle collection", "title_ar": "مجموعة جديدة",
            "subtitle_fr": "Sacs de soirée", "cta_text_fr": "Voir", "cta_link": "#/boutique"})
        self.assertEqual(r.status_code, 201, r.text)
        bid = r.json()["id"]
        try:
            layout = self.client.get("/api/v1/store/layout").json()
            mine = next(b for b in layout["banners"] if b["id"] == bid)
            self.assertEqual(mine["position"], "hero")
            self.assertEqual(mine["title_ar"], "مجموعة جديدة")
            # No invented defaults: empty fields stay empty.
            self.assertEqual(mine["image_url"] or "", "")

            upd = self.client.put(f"/api/v1/admin/banners/{bid}", headers=self.headers, json={
                "position": "promo_grid", "title_fr": "-20 % sur les sacs", "subtitle_fr": "Cette semaine",
                "cta_link": "/categorie/sacs", "is_active": True, "display_order": 2})
            self.assertEqual(upd.status_code, 200, upd.text)
            layout = self.client.get("/api/v1/store/layout").json()
            mine = next(b for b in layout["banners"] if b["id"] == bid)
            self.assertEqual(mine["position"], "promo_grid")
            self.assertEqual(mine["title_fr"], "-20 % sur les sacs")
            self.assertEqual(mine["cta_link"], "/categorie/sacs")

            hide = self.client.put(f"/api/v1/admin/banners/{bid}", headers=self.headers, json={
                "position": "promo_grid", "title_fr": "-20 % sur les sacs", "is_active": False})
            self.assertEqual(hide.status_code, 200, hide.text)
            layout = self.client.get("/api/v1/store/layout").json()
            self.assertFalse(any(b["id"] == bid for b in layout["banners"]), "hidden banner must not reach the shop")

            bad = self.client.put(f"/api/v1/admin/banners/{bid}", headers=self.headers, json={
                "position": "promo_grid", "title_fr": "x", "cta_link": "javascript:alert(1)"})
            self.assertEqual(bad.status_code, 422)
            self.assertEqual(self.client.put("/api/v1/admin/banners/99999999", headers=self.headers,
                                             json={"title_fr": "x"}).status_code, 404)
        finally:
            self.client.delete(f"/api/v1/admin/banners/{bid}", headers=self.headers)

    def test_banner_editing_requires_login(self):
        self.assertIn(self.client.put("/api/v1/admin/banners/1", json={"title_fr": "x"}).status_code, (401, 403))

    # ------------------------------------------------------- home blocks --
    def test_home_blocks_listed_and_switchable(self):
        r = self.client.get("/api/v1/admin/homepage-sections", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        keys = [s["section_key"] for s in r.json()["items"]]
        for k in ("hero_banner", "trust_bar", "categories_grid", "featured_products", "promo_banners"):
            self.assertIn(k, keys)

        off = self.client.put("/api/v1/admin/homepage-sections/trust_bar", headers=self.headers,
                              json={"is_active": False, "display_order": 2, "config": {}})
        self.assertEqual(off.status_code, 200, off.text)
        try:
            secs = {s["section_key"]: s for s in self.client.get("/api/v1/store/layout").json()["homepage_sections"]}
            self.assertIn("trust_bar", secs, "switched-off blocks are sent so the shop can hide them")
            self.assertFalse(secs["trust_bar"]["is_active"])
        finally:
            self.client.put("/api/v1/admin/homepage-sections/trust_bar", headers=self.headers,
                            json={"is_active": True, "display_order": 2, "config": {}})
        self.assertEqual(self.client.put("/api/v1/admin/homepage-sections/not_a_block", headers=self.headers,
                                         json={"is_active": True}).status_code, 404)

    # ---------------------------------------------------------- dashboard --
    def test_starter_pages_arabic_is_arabic_owner_text_kept(self):
        """Older shops had the French starter text copied into the Arabic and
        English fields: it is translated at start, but never over the owner's own text."""
        from app.database import db_session
        from app.seed import _INITIAL_STATIC_PAGES, translate_untouched_starter_pages
        faq_fr = next(p for p in _INITIAL_STATIC_PAGES if p[0] == "faq")[4]
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            # as an older version left them: faq untouched, returns edited by the owner
            cur.execute("UPDATE static_pages SET content_ar = content_fr, content_en = content_fr WHERE slug IN ('faq', 'returns')")
            cur.execute("UPDATE static_pages SET content_ar = ? WHERE slug = 'returns'", ("نص كتبه المالك",))
            translate_untouched_starter_pages(cur)
            self.assertEqual(translate_untouched_starter_pages(cur), 0, "runs once, then nothing to do")
        faq = self.client.get("/api/v1/pages/faq").json()
        self.assertNotEqual(faq["content_ar"], faq_fr)
        self.assertIn("اطلبوا مباشرة", faq["content_ar"])
        self.assertIn("Order directly", faq["content_en"])
        self.assertEqual(self.client.get("/api/v1/pages/returns").json()["content_ar"], "نص كتبه المالك")

    def test_compression_large_answers_only(self):
        """Lists are gzip-compressed, tiny answers are not; both stay readable."""
        big = self.client.get("/api/v1/delivery-zones", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(big.status_code, 200)
        self.assertEqual(big.headers.get("content-encoding"), "gzip")
        self.assertGreater(len(big.json()["items"]), 40)
        small = self.client.get("/api/v1/health", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(small.status_code, 200)
        self.assertNotIn("content-encoding", small.headers)

    def test_dashboard_chart_uses_real_daily_revenue(self):
        before = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        self.assertEqual(len(before["revenue_by_day"]), 30)
        today = __import__("app.main", fromlist=["_shop_today"])._shop_today()  # shop day (Algeria)
        self.assertEqual(before["revenue_by_day"][-1]["date"], today)

        self._set_threshold("0")
        _, vid = self._product(7000)
        order = self._order(vid)
        after = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        delta = after["revenue_by_day"][-1]["revenue_dzd"] - before["revenue_by_day"][-1]["revenue_dzd"]
        self.assertEqual(delta, order["total_dzd"])
        self.assertEqual(after["revenue_by_day"][-1]["orders"] - before["revenue_by_day"][-1]["orders"], 1)

        # Cancelled orders leave the chart and the revenue card.
        c = self.client.patch(f"/api/v1/admin/orders/{order['order_id']}", headers=self.headers,
                              json={"status": "cancelled"})
        self.assertEqual(c.status_code, 200, c.text)
        final = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        self.assertEqual(final["revenue_by_day"][-1]["revenue_dzd"], before["revenue_by_day"][-1]["revenue_dzd"])

    def test_dashboard_stock_ignores_archived_products(self):
        before = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        prod, _ = self._product(3000, stock=0)
        mid = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        self.assertEqual(mid["out_of_stock_variants"], before["out_of_stock_variants"] + 1)
        self.assertEqual(mid["active_variants"], before["active_variants"] + 1)
        self.client.delete(f"/api/v1/admin/products/{prod['id']}", headers=self.headers)
        after = self.client.get("/api/v1/admin/dashboard", headers=self.headers).json()
        self.assertEqual(after["out_of_stock_variants"], before["out_of_stock_variants"])
        self.assertEqual(after["active_variants"], before["active_variants"])
        # low_stock_only never includes the out-of-stock ones
        self.assertLessEqual(after["low_stock_only_variants"], after["low_stock_variants"])

    # ------------------------------------------- old example content --
    def test_legacy_demo_cleanup_runs_once_is_audited_and_keeps_owner_content(self):
        from unittest import mock
        from app.database import db_session
        from app.seed import LEGACY_CLEANUP_MARKER, remove_legacy_demo_content

        ins = ("INSERT INTO banners (position, title_fr, cta_link, image_url, is_active, display_order) "
               "VALUES (?, ?, ?, ?, 1, 9)")
        legacy = ("promo_grid", "CHAUSSURES — Jusqu'à -20%", "/categories/chaussures", "/assets/prod_baskets_elegantes.jpg")
        prod_env = {"APP_ENV": "production", "LUXE_SEED_DEMO_PRODUCTS": "0"}
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM store_settings WHERE setting_key = ?", (LEGACY_CLEANUP_MARKER,))
            cur.execute(ins, legacy)
            demo_id = cur.lastrowid
            # Same title but the owner changed the photo: kept.
            cur.execute(ins, legacy[:3] + ("/uploads/mine.jpg",))
            owner_id = cur.lastrowid
            cur.execute("DELETE FROM coupons WHERE code IN ('BIENVENUE10', 'ALGERIE500')")
            cur.execute("INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, is_active, usage_count) "
                        "VALUES ('BIENVENUE10', 'percentage', 10, 4000, 1, 0)")
            cur.execute("INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, is_active, usage_count) "
                        "VALUES ('ALGERIE500', 'fixed_dzd', 500, 5000, 1, 3)")
        ids = []
        try:
            # 1. Test / demo databases are never cleaned and get no marker.
            with db_session(commit=True) as conn:
                self.assertEqual(remove_legacy_demo_content(conn.cursor())["banners"], [])
            with db_session() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) AS cnt FROM banners WHERE id = ?", (demo_id,))
                self.assertEqual(cur.fetchone()["cnt"], 1)

            # 2. Production: example rows go, owner rows stay, change is audited.
            with mock.patch.dict(os.environ, prod_env):
                with db_session(commit=True) as conn:
                    found = remove_legacy_demo_content(conn.cursor())
            removed = [b["id"] for b in found["banners"]]
            self.assertIn(demo_id, removed)
            self.assertNotIn(owner_id, removed)
            self.assertEqual([c["code"] for c in found["coupons"]], ["BIENVENUE10"])
            with db_session() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM banners WHERE id IN (?, ?)", (demo_id, owner_id))
                self.assertEqual([r["id"] for r in cur.fetchall()], [owner_id])
                cur.execute("SELECT code, is_active FROM coupons WHERE code IN ('BIENVENUE10', 'ALGERIE500')")
                codes = {r["code"]: r["is_active"] for r in cur.fetchall()}
                self.assertEqual(codes["BIENVENUE10"], 0, "unused example code must be switched off")
                self.assertEqual(codes["ALGERIE500"], 1, "a code customers already used is kept")
                cur.execute("SELECT details_json FROM audit_logs WHERE action = 'remove_legacy_demo_content' ORDER BY id DESC LIMIT 1")
                details = json.loads(cur.fetchone()["details_json"])
                self.assertEqual(details["deactivated_promo_codes"], ["BIENVENUE10"])
                cur.execute("SELECT 1 AS x FROM store_settings WHERE setting_key = ?", (LEGACY_CLEANUP_MARKER,))
                self.assertIsNotNone(cur.fetchone(), "marker must be stored")

            # 3. Runs only once: an identical banner the owner adds later stays.
            with db_session(commit=True) as conn:
                cur = conn.cursor()
                cur.execute(ins, legacy)
                ids.append(cur.lastrowid)
            with mock.patch.dict(os.environ, prod_env):
                with db_session(commit=True) as conn:
                    self.assertEqual(remove_legacy_demo_content(conn.cursor())["banners"], [])
            with db_session() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) AS cnt FROM banners WHERE id = ?", (ids[0],))
                self.assertEqual(cur.fetchone()["cnt"], 1)

            # 4. The marker is internal: never sent to the shop.
            self.assertNotIn(LEGACY_CLEANUP_MARKER, self.client.get("/api/v1/store/layout").json()["settings"])
        finally:
            with db_session(commit=True) as conn:
                cur = conn.cursor()
                for bid in [demo_id, owner_id] + ids:
                    cur.execute("DELETE FROM banners WHERE id = ?", (bid,))
                cur.execute("DELETE FROM store_settings WHERE setting_key = ?", (LEGACY_CLEANUP_MARKER,))

if __name__ == "__main__":
    unittest.main()
