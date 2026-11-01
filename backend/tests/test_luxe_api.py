import io
import os
import tempfile
import unittest

# Configure isolated test SQLite database before importing app
TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix=".sqlite3")
os.close(TEST_DB_FD)
os.environ["LUXE_SQLITE_PATH"] = TEST_DB_PATH

from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits

class TestLuxeEcommercePlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()

    def get_admin_headers(self, email="admin@musluxury.dz", password="MusLuxury2026!"):
        resp = self.client.post("/api/v1/admin/auth/login", json={"email": email, "password": password})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # 1. Storefront & Security Headers
    def test_01_public_settings_and_security_headers(self):
        resp = self.client.get("/api/v1/store/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["primary_currency"], "DZD")
        self.assertEqual(data["colors"]["deep_emerald"], "#063D2E")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

    # 2. Public Product Listing strips private purchase_cost_dzd
    def test_02_public_products_hide_private_cost(self):
        resp = self.client.get("/api/v1/products")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        self.assertGreaterEqual(len(items), 4)
        for p in items:
            self.assertNotIn("purchase_cost_dzd", p)
            self.assertIn("selling_price_dzd", p)
            self.assertIn("variants", p)

    # 3. Unauthorized access to Admin API is strictly blocked
    def test_03_unauthorized_admin_access_blocked(self):
        resp = self.client.get("/api/v1/admin/dashboard")
        self.assertEqual(resp.status_code, 401)
        resp2 = self.client.post("/api/v1/admin/categories", json={"slug": "test", "name_fr": "T", "name_ar": "ت", "name_en": "T"})
        self.assertEqual(resp2.status_code, 401)

    # 4. RBAC Permissions enforced (catalog_editor cannot create categories or trigger backups)
    def test_04_rbac_permission_enforcement(self):
        editor_headers = self.get_admin_headers("editor@musluxury.dz", "EditorLuxury2026!")
        # Editor can read dashboard
        r_dash = self.client.get("/api/v1/admin/dashboard", headers=editor_headers)
        self.assertEqual(r_dash.status_code, 200)
        # Editor CANNOT create custom categories or trigger backups
        r_cat = self.client.post(
            "/api/v1/admin/categories",
            headers=editor_headers,
            json={"slug": "parfums", "name_fr": "Parfums", "name_ar": "عطور", "name_en": "Perfumes"}
        )
        self.assertEqual(r_cat.status_code, 403)
        r_bak = self.client.post("/api/v1/admin/backups", headers=editor_headers)
        self.assertEqual(r_bak.status_code, 403)

    # 5. Dynamic Category Builder + Attribute Configuration (Core Requirement)
    def test_05_dynamic_category_and_attribute_builder(self):
        headers = self.get_admin_headers()
        # Step 1: Create new custom category 'Parfums de Niche'
        r_cat = self.client.post(
            "/api/v1/admin/categories",
            headers=headers,
            json={
                "slug": "parfums-de-niche",
                "name_fr": "Parfums de Niche",
                "name_ar": "عطور نيش فاخرة",
                "name_en": "Niche Perfumes",
                "description_fr": "Fragrances rares et extraits de parfum",
                "display_order": 10,
                "is_active": True,
                "show_on_homepage": True,
            }
        )
        self.assertEqual(r_cat.status_code, 201, r_cat.text)
        cat_id = r_cat.json()["id"]

        # Step 2: Configure custom category attributes (concentration, volume_ml, olfactory_family)
        r_a1 = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=headers,
            json={
                "category_id": cat_id,
                "attr_key": "concentration",
                "label_fr": "Concentration",
                "label_ar": "التركيز",
                "label_en": "Concentration",
                "input_type": "single_select",
                "is_required": True,
                "is_filterable": True,
                "is_variant_axis": False,
                "options": [
                    {"value": "Extrait de Parfum", "label_fr": "Extrait de Parfum"},
                    {"value": "Eau de Parfum", "label_fr": "Eau de Parfum"}
                ]
            }
        )
        self.assertEqual(r_a1.status_code, 201, r_a1.text)

        r_a2 = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=headers,
            json={
                "category_id": cat_id,
                "attr_key": "bottle_size",
                "label_fr": "Contenance",
                "label_ar": "السعة",
                "label_en": "Bottle Size",
                "input_type": "size",
                "unit": "ml",
                "is_required": True,
                "is_filterable": True,
                "is_variant_axis": True,
                "options": [
                    {"value": "50ml", "label_fr": "50 ml"},
                    {"value": "100ml", "label_fr": "100 ml"}
                ]
            }
        )
        self.assertEqual(r_a2.status_code, 201, r_a2.text)

        # Verify dynamic product validation rejects published product missing required 'concentration'
        r_bad_prod = self.client.post(
            "/api/v1/admin/products",
            headers=headers,
            json={
                "category_id": cat_id,
                "slug": "oud-royal-alger",
                "sku": "LUX-PRF-001",
                "name_fr": "Oud Royal d'Alger",
                "selling_price_dzd": 14500,
                "status": "published",
                "dynamic_attributes": {} # missing required 'concentration'
            }
        )
        self.assertEqual(r_bad_prod.status_code, 422)

        # Saving as draft without required attributes is allowed
        r_draft = self.client.post(
            "/api/v1/admin/products",
            headers=headers,
            json={
                "category_id": cat_id,
                "slug": "oud-royal-draft",
                "sku": "LUX-PRF-DRAFT",
                "name_fr": "Oud Royal Draft",
                "selling_price_dzd": 14500,
                "status": "draft",
                "dynamic_attributes": {}
            }
        )
        self.assertEqual(r_draft.status_code, 201)

        # Creating published product with required dynamic attribute succeeds
        r_good_prod = self.client.post(
            "/api/v1/admin/products",
            headers=headers,
            json={
                "category_id": cat_id,
                "slug": "oud-royal-alger",
                "sku": "LUX-PRF-001",
                "name_fr": "Oud Royal d'Alger",
                "purchase_cost_dzd": 8000,
                "selling_price_dzd": 14500,
                "status": "published",
                "dynamic_attributes": {"concentration": "Extrait de Parfum"}
            }
        )
        self.assertEqual(r_good_prod.status_code, 201, r_good_prod.text)
        prod_id = r_good_prod.json()["id"]

        # Step 3: Variant Combination Generator & Duplicate Prevention
        r_gen = self.client.post(
            f"/api/v1/admin/products/{prod_id}/generate-variants",
            headers=headers,
            json={"axes": {"bottle_size": ["50ml", "100ml"]}, "default_stock": 5}
        )
        self.assertEqual(r_gen.status_code, 201, r_gen.text)
        self.assertEqual(len(r_gen.json()["created"]), 2)

        # Re-running variant generator skips duplicates cleanly
        r_gen_dup = self.client.post(
            f"/api/v1/admin/products/{prod_id}/generate-variants",
            headers=headers,
            json={"axes": {"bottle_size": ["50ml", "100ml"]}, "default_stock": 5}
        )
        self.assertEqual(r_gen_dup.status_code, 201)
        self.assertEqual(r_gen_dup.json()["skipped_duplicates"], 2)

        # Step 4: Prevent deleting an attribute actively used by existing products without warning/migration
        cat_data = self.client.get("/api/v1/categories/parfums-de-niche").json()
        conc_attr_id = [a["id"] for a in cat_data["attributes"] if a["attr_key"] == "concentration"][0]
        r_del_blocked = self.client.delete(f"/api/v1/admin/category-attributes/{conc_attr_id}", headers=headers)
        self.assertEqual(r_del_blocked.status_code, 409)

    # 6. Guest Checkout, Server-Side Price & Wilaya Calculation, Tamper Rejection & Stock Decrement
    def test_06_guest_checkout_server_price_and_inventory_protection(self):
        # Fetch product 'sac-a-main-chanel-style' (selling price 4500 DA)
        prod = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        variant = prod["variants"][0] # stock = 6, price = 4500 DA
        vid = variant["id"]
        initial_stock = variant["stock_qty"]

        # Attempt order with tampered browser price (1 DA) and tampered total (10 DA)
        # Delivery to Alger (16) Home Delivery = 400 DA
        order_payload = {
            "full_name": "Amina Benali",
            "phone": "0550123456",
            "wilaya_code": "16",
            "commune": "Hydra",
            "delivery_address": "14 Rue des Pins, Hydra, Alger",
            "delivery_method": "home",
            "items": [{"variant_id": vid, "quantity": 2, "client_tampered_price": 1}],
            "client_submitted_total_dzd": 10
        }
        r_ord = self.client.post("/api/v1/orders", json=order_payload)
        self.assertEqual(r_ord.status_code, 201, r_ord.text)
        odata = r_ord.json()

        # Verify server ignored tampered values and calculated 2 * 4500 + 400 = 9400 DA
        self.assertEqual(odata["subtotal_dzd"], 9000)
        self.assertEqual(odata["delivery_fee_dzd"], 400)
        self.assertEqual(odata["total_dzd"], 9400)

        # Verify duplicate order submission is blocked
        r_dup = self.client.post("/api/v1/orders", json=order_payload)
        self.assertEqual(r_dup.status_code, 409)

        # Verify stock was decremented by 2
        prod_after = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        v_after = [v for v in prod_after["variants"] if v["id"] == vid][0]
        self.assertEqual(v_after["stock_qty"], initial_stock - 2)

        # Verify overselling is prevented (requesting 25 units when only 4 remain)
        r_oversell = self.client.post("/api/v1/orders", json={
            "full_name": "Karim Mansouri",
            "phone": "0661987654",
            "wilaya_code": "31",
            "commune": "Oran Centre",
            "delivery_address": "Boulevard de la Soummam, Oran",
            "delivery_method": "stop_desk",
            "items": [{"variant_id": vid, "quantity": 25}]
        })
        self.assertEqual(r_oversell.status_code, 409)

        # Verify cancelling the order restores variant stock
        headers = self.get_admin_headers()
        r_cancel = self.client.patch(
            f"/api/v1/admin/orders/{odata['order_id']}",
            headers=headers,
            json={"status": "cancelled", "internal_notes": "Client requested cancellation by phone"}
        )
        self.assertEqual(r_cancel.status_code, 200)
        prod_restored = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        v_restored = [v for v in prod_restored["variants"] if v["id"] == vid][0]
        self.assertEqual(v_restored["stock_qty"], initial_stock)

    # 7. Security: File upload validation & Rate limiting
    def test_07_file_upload_security_and_rate_limiting(self):
        headers = self.get_admin_headers()
        # Reject executable/script disguised as image/jpeg
        bad_file = io.BytesIO(b"<?php system($_GET['cmd']); ?>")
        r_bad = self.client.post(
            "/api/v1/admin/upload",
            headers=headers,
            files={"file": ("exploit.jpg", bad_file, "image/jpeg")}
        )
        self.assertEqual(r_bad.status_code, 400)

        # Accept valid PNG binary header
        valid_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        r_good = self.client.post(
            "/api/v1/admin/upload",
            headers=headers,
            files={"file": ("product.png", valid_png, "image/png")}
        )
        self.assertEqual(r_good.status_code, 201)

        # Rate limit on login endpoint (max 5 requests per minute)
        reset_rate_limits()
        for _ in range(5):
            self.client.post("/api/v1/admin/auth/login", json={"email": "wrong@musluxury.dz", "password": "bad"})
        r_limited = self.client.post("/api/v1/admin/auth/login", json={"email": "wrong@musluxury.dz", "password": "bad"})
        self.assertEqual(r_limited.status_code, 429)

    # 8. Desktop CMS Full Website Control (Banners, Homepage Sections & Store Settings)
    def test_08_desktop_cms_controls_entire_website_layout(self):
        headers = self.get_admin_headers()
        # Update Hero Section & Store Tagline from the Desktop CMS API
        r_sec = self.client.put(
            "/api/v1/admin/homepage-sections/hero_banner",
            headers=headers,
            json={
                "title_fr": "Collection Automne-Hiver Algérie",
                "is_active": True,
                "display_order": 1,
                "config": {"title_line1_fr": "L'Élégance Impériale,", "title_line2_fr": "signée Mus Luxury"}
            }
        )
        self.assertEqual(r_sec.status_code, 200, r_sec.text)

        r_set = self.client.put(
            "/api/v1/admin/settings",
            headers=headers,
            json={"settings": {"tagline_fr": "Nouvelle Collection Exclusive 58 Wilayas"}}
        )
        self.assertEqual(r_set.status_code, 200)

        # Public website fetches /api/v1/store/layout and immediately reflects the Desktop CMS changes
        r_layout = self.client.get("/api/v1/store/layout")
        self.assertEqual(r_layout.status_code, 200)
        layout = r_layout.json()
        self.assertEqual(layout["settings"]["tagline_fr"], "Nouvelle Collection Exclusive 58 Wilayas")
        hero_sec = [s for s in layout["homepage_sections"] if s["section_key"] == "hero_banner"][0]
        self.assertEqual(hero_sec["config"]["title_line1_fr"], "L'Élégance Impériale,")

    # 9. WhatsApp Password Recovery: Explicit 503 when Cloud API unconfigured & Single-Use OTP verification
    def test_09_whatsapp_recovery_honesty_and_single_use_otp(self):
        # Ensure WhatsApp Cloud API env vars are unset: must return 503 Service Unavailable (never fake success!)
        os.environ.pop("WHATSAPP_CLOUD_API_TOKEN", None)
        os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)
        r_unavail = self.client.post(
            "/api/v1/admin/auth/recovery/request",
            json={"phone": "+213550000001", "channel": "whatsapp_cloud_api"}
        )
        self.assertEqual(r_unavail.status_code, 503, r_unavail.text)

        # Configure official WhatsApp Cloud API credentials in test environment and verify single-use OTP flow
        os.environ["WHATSAPP_CLOUD_API_TOKEN"] = "EAAG_test_official_cloud_api_token"
        os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "1092837465"
        os.environ["WHATSAPP_TEST_CAPTURE"] = "1"
        try:
            r_req = self.client.post(
                "/api/v1/admin/auth/recovery/request",
                json={"phone": "+213550000001", "channel": "whatsapp_cloud_api"}
            )
            self.assertEqual(r_req.status_code, 200, r_req.text)
            otp = r_req.json()["test_otp"]

            # Verify OTP and rotate password
            r_ver = self.client.post(
                "/api/v1/admin/auth/recovery/verify",
                json={
                    "phone": "+213550000001",
                    "verification_code": otp,
                    "new_password": "NewMusLuxuryPassword2026!"
                }
            )
            self.assertEqual(r_ver.status_code, 200, r_ver.text)

            # Re-using the same OTP must be rejected (Single-Use enforcement)
            r_reuse = self.client.post(
                "/api/v1/admin/auth/recovery/verify",
                json={
                    "phone": "+213550000001",
                    "verification_code": otp,
                    "new_password": "AnotherPassword2026!"
                }
            )
            self.assertEqual(r_reuse.status_code, 400)

            # Restore default owner password via seeded offline emergency code
            r_emerg = self.client.post(
                "/api/v1/admin/auth/recovery/verify",
                json={
                    "phone": "+213550000001",
                    "verification_code": "LUXE-EMERGENCY-2026-RECOVERY",
                    "new_password": "MusLuxury2026!"
                }
            )
            self.assertEqual(r_emerg.status_code, 200, r_emerg.text)
        finally:
            os.environ.pop("WHATSAPP_CLOUD_API_TOKEN", None)
            os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)
            os.environ.pop("WHATSAPP_TEST_CAPTURE", None)

    # 10. Server-Side Coupon Calculation & IDOR-Safe Guest Order Tracking
    def test_10_coupons_and_idor_safe_guest_order_tracking(self):
        prod = self.client.get("/api/v1/products/sac-a-main-elegant-emeraude").json()
        vid = prod["variants"][0]["id"] # 12,500 DA

        # Apply BIENVENUE10 (10% off, capped at 2500 DA -> 1250 DA discount) + Oran (31) stop_desk (400 DA)
        r_ord = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Nadia Boudiaf",
                "phone": "0770112233",
                "wilaya_code": "31",
                "commune": "Oran Centre",
                "delivery_address": "Rue Larbi Ben M'hidi, Oran",
                "delivery_method": "stop_desk",
                "coupon_code": "BIENVENUE10",
                "items": [{"variant_id": vid, "quantity": 1}]
            }
        )
        self.assertEqual(r_ord.status_code, 201, r_ord.text)
        data = r_ord.json()
        self.assertEqual(data["subtotal_dzd"], 12500)
        self.assertEqual(data["discount_dzd"], 1250)
        self.assertEqual(data["delivery_fee_dzd"], 400)
        self.assertEqual(data["total_dzd"], 11650)

        ref = data["order_reference"]
        # Guest order tracking with wrong phone number is blocked (IDOR protection)
        r_idor = self.client.get(f"/api/v1/orders/track?reference={ref}&phone=0550999999")
        self.assertEqual(r_idor.status_code, 404)

        # Guest order tracking with matching reference + phone succeeds
        r_track = self.client.get(f"/api/v1/orders/track?reference={ref}&phone=0770112233")
        self.assertEqual(r_track.status_code, 200)
        self.assertEqual(r_track.json()["total_dzd"], 11650)
        self.assertNotIn("internal_notes", r_track.json())

    # 11. Optimistic Concurrency Conflict Detection for Simultaneous CMS Edits
    def test_11_optimistic_concurrency_conflict_detection(self):
        headers = self.get_admin_headers()
        prod = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        pid = prod["id"]
        v_current = prod["version"]

        # First update with matching expected_version succeeds and increments version
        r_up1 = self.client.put(
            f"/api/v1/admin/products/{pid}",
            headers=headers,
            json={"name_fr": "Sac à main Chanel style", "selling_price_dzd": 4500, "expected_version": v_current}
        )
        self.assertEqual(r_up1.status_code, 200, r_up1.text)
        self.assertEqual(r_up1.json()["version"], v_current + 1)

        # Second update with stale expected_version is rejected with HTTP 409 Conflict
        r_conflict = self.client.put(
            f"/api/v1/admin/products/{pid}",
            headers=headers,
            json={"name_fr": "Stale Edit", "selling_price_dzd": 3000, "expected_version": v_current}
        )
        self.assertEqual(r_conflict.status_code, 409)

    # 12. All 58 Algerian Wilayas Seeded & Verified
    def test_12_all_58_algerian_wilayas_configured(self):
        r_zones = self.client.get("/api/v1/delivery-zones")
        self.assertEqual(r_zones.status_code, 200)
        zones = r_zones.json()["items"]
        self.assertEqual(len(zones), 58)
        codes = [z["wilaya_code"] for z in zones]
        self.assertIn("01", codes)
        self.assertIn("16", codes)
        self.assertIn("58", codes)

    # 13. Automatic Desktop CMS Reconnection & Delta Sync After Windows PC Turns Back On
    def test_13_automatic_cms_reconnection_delta_sync_after_pc_off(self):
        headers = self.get_admin_headers()
        # Step 1: Desktop CMS checks current sync state before PC is turned off
        r_sync_before = self.client.get("/api/v1/admin/sync/delta?since_order_id=0&since_movement_id=0", headers=headers)
        self.assertEqual(r_sync_before.status_code, 200)
        last_seen_order_id = r_sync_before.json()["latest_order_id"]
        last_seen_mov_id = r_sync_before.json()["latest_movement_id"]

        # Step 2: Owner's Windows PC is turned OFF. Meanwhile, a customer on the public website places an order!
        prod = self.client.get("/api/v1/products/baskets-elegantes-urbaines").json()
        vid = prod["variants"][0]["id"] # Size 38, stock 4
        r_guest_ord = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Yacine Brahimi",
                "phone": "0552334455",
                "wilaya_code": "25",
                "commune": "Constantine",
                "delivery_address": "Cité Bellevue, Constantine",
                "delivery_method": "home",
                "items": [{"variant_id": vid, "quantity": 1}]
            }
        )
        self.assertEqual(r_guest_ord.status_code, 201, r_guest_ord.text)

        # Step 3: Owner turns Windows PC back ON -> Desktop CMS automatically calls /api/v1/admin/sync/delta
        r_sync_after = self.client.get(
            f"/api/v1/admin/sync/delta?since_order_id={last_seen_order_id}&since_movement_id={last_seen_mov_id}",
            headers=headers
        )
        self.assertEqual(r_sync_after.status_code, 200)
        delta = r_sync_after.json()
        self.assertEqual(delta["missed_orders_count"], 1)
        self.assertEqual(delta["new_orders"][0]["customer_name"], "Yacine Brahimi")
        self.assertGreaterEqual(len(delta["new_movements"]), 1)

if __name__ == "__main__":
    unittest.main()



