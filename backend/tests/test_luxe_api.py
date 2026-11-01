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

    # 12. All 69 Official Algerian Wilayas (01 to 69) Seeded & Verified
    def test_12_all_69_algerian_wilayas_configured(self):
        r_zones = self.client.get("/api/v1/delivery-zones")
        self.assertEqual(r_zones.status_code, 200)
        zones = r_zones.json()["items"]
        self.assertEqual(len(zones), 69)
        codes = [z["wilaya_code"] for z in zones]
        for expected_code in ["01", "16", "31", "58", "59", "60", "64", "68", "69"]:
            self.assertIn(expected_code, codes)

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

    # 14. Setup Status Check & Multi-PC Workflow
    def test_14_setup_status_check_and_multi_pc_detection(self):
        # When DB is seeded with an owner, setup-status returns is_initialized=True
        r = self.client.get("/api/v1/admin/auth/setup-status")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["is_initialized"])
        self.assertFalse(r.json()["requires_owner_setup"])

    # 15. One-Time Owner Provisioning & Permanent Lockout (HTTP 403 on subsequent calls)
    def test_15_one_time_owner_initialization_lockout(self):
        # Attempting to call initialize-owner when already initialized must return HTTP 403 Forbidden
        payload = {
            "full_name": "Mustapha Harbit",
            "email": "owner_second_attempt@musluxury.dz",
            "password": "SecurePassword2026!",
            "whatsapp_phone": "0550112233",
            "emergency_phone": "0661223344"
        }
        r_locked = self.client.post("/api/v1/admin/auth/initialize-owner", json=payload)
        self.assertEqual(r_locked.status_code, 403)
        self.assertIn("already been initialized", r_locked.json()["detail"])

    # 16. Cryptographic Request Signing & Replay Attack Prevention
    def test_16_cryptographic_signing_and_replay_attack_prevention(self):
        from app.security import sign_api_request
        headers = self.get_admin_headers()
        path = "/api/v1/admin/secure-action"
        payload_bytes = b'{"action": "rotate_encryption_keys"}'

        # Step 1: Client signs request with HMAC-SHA256, current timestamp, and unique nonce
        sig, ts, nonce = sign_api_request("POST", path, payload_bytes)
        req_headers = {
            **headers,
            "X-Luxe-Signature": sig,
            "X-Luxe-Timestamp": ts,
            "X-Luxe-Nonce": nonce,
            "Content-Type": "application/json"
        }
        r_good = self.client.post(path, data=payload_bytes, headers=req_headers)
        self.assertEqual(r_good.status_code, 200, r_good.text)
        self.assertEqual(r_good.json()["status"], "verified_and_executed")

        # Step 2: Attacker intercepts and attempts a REPLAY ATTACK with the exact same nonce & signature
        r_replay = self.client.post(path, data=payload_bytes, headers=req_headers)
        self.assertEqual(r_replay.status_code, 401)
        self.assertIn("Replay Attack Detected", r_replay.json()["detail"])

        # Step 3: Attacker sends an expired timestamp (> 300 seconds skew)
        old_sig, old_ts, new_nonce = sign_api_request("POST", path, payload_bytes)
        bad_ts_headers = {
            **headers,
            "X-Luxe-Signature": old_sig,
            "X-Luxe-Timestamp": str(int(ts) - 600), # 10 minutes in the past
            "X-Luxe-Nonce": new_nonce,
            "Content-Type": "application/json"
        }
        r_expired = self.client.post(path, data=payload_bytes, headers=bad_ts_headers)
        self.assertEqual(r_expired.status_code, 401)
        self.assertIn("expired", r_expired.json()["detail"])

    # 17. Cryptographic Tamper Detection (Payload / Header Invalidation)
    def test_17_cryptographic_tamper_detection(self):
        from app.security import sign_api_request
        headers = self.get_admin_headers()
        path = "/api/v1/admin/secure-action"
        original_bytes = b'{"action": "update_store_settings"}'
        sig, ts, nonce = sign_api_request("POST", path, original_bytes)

        # Attacker tampers with one byte of the payload in transit:
        tampered_bytes = b'{"action": "update_store_ATTACKED"}'
        tampered_headers = {
            **headers,
            "X-Luxe-Signature": sig,
            "X-Luxe-Timestamp": ts,
            "X-Luxe-Nonce": nonce,
            "Content-Type": "application/json"
        }
        r_tampered = self.client.post(path, data=tampered_bytes, headers=tampered_headers)
        self.assertEqual(r_tampered.status_code, 401)
        self.assertIn("tampered with in transit", r_tampered.json()["detail"])

    # 18. Path Traversal & Embedded Malicious Script Protection in File Uploads
    def test_18_path_traversal_and_malicious_script_upload_blocking(self):
        headers = self.get_admin_headers()
        # Attempt path traversal: ../../../etc/cron.d/exploit.jpg
        traversal_file = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        r_trav = self.client.post(
            "/api/v1/admin/upload",
            headers=headers,
            files={"file": ("../../../etc/exploit.jpg", traversal_file, "image/jpeg")}
        )
        self.assertEqual(r_trav.status_code, 400)
        self.assertIn("Path traversal", r_trav.json()["detail"])

        # Attempt polyglot webshell embedding PHP eval code inside a PNG file
        malicious_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00<?php eval($_POST['cmd']); ?>")
        r_shell = self.client.post(
            "/api/v1/admin/upload",
            headers=headers,
            files={"file": ("shell.png", malicious_png, "image/png")}
        )
        self.assertEqual(r_shell.status_code, 400)
        self.assertIn("Malicious script signature detected", r_shell.json()["detail"])

    # 19. SQL Injection Resilience Across Filter, Search & Auth Endpoints
    def test_19_sql_injection_resilience(self):
        # Attempt SQL injection in product search
        r_sqli = self.client.get("/api/v1/products?q=' OR '1'='1; DROP TABLE products;--")
        self.assertEqual(r_sqli.status_code, 200) # Safe parameterization returns 0 matches or empty

        # Attempt SQL injection in category slug
        r_cat_sqli = self.client.get("/api/v1/categories/sacs' UNION SELECT * FROM admin_users;--")
        self.assertEqual(r_cat_sqli.status_code, 404)

        # Attempt SQL injection in admin login
        r_login_sqli = self.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "' OR 1=1;--", "password": "password"}
        )
        self.assertEqual(r_login_sqli.status_code, 401)

    # 20. Dynamic PDP Schema (Category Attributes + Multi-Axis Variants) & Attribute Filtering
    def test_20_dynamic_pdp_schema_and_attribute_filtering(self):
        # Product detail response includes full category attribute definitions (variant axes + custom fields)
        r_pdp = self.client.get("/api/v1/products/sac-a-main-chanel-style")
        self.assertEqual(r_pdp.status_code, 200)
        pdp = r_pdp.json()
        cat_attrs = pdp["category"]["attributes"]
        axis_keys = [a["attr_key"] for a in cat_attrs if a["is_variant_axis"]]
        self.assertIn("color", axis_keys)
        self.assertIn("size", axis_keys)
        self.assertEqual(pdp["attributes"]["bag_type"], "Sac à main")

        # Filter products dynamically by custom attribute or variant option (?attr_color=Bordeaux)
        r_filt = self.client.get("/api/v1/products?category=sacs&attr_color=Bordeaux")
        self.assertEqual(r_filt.status_code, 200)
        self.assertGreaterEqual(r_filt.json()["total"], 1)

        # Public coupon validation endpoint
        r_cpn = self.client.post("/api/v1/coupons/validate", json={"code": "BIENVENUE10", "subtotal_dzd": 10000})
        self.assertEqual(r_cpn.status_code, 200)
        self.assertEqual(r_cpn.json()["discount_dzd"], 1000)

    # 21. Admin 69-Wilaya Rate Update, Variant Stock Adjustment & Reports Endpoints
    def test_21_wilaya_rate_update_stock_adjustment_and_reports(self):
        headers = self.get_admin_headers()
        # Update Wilaya 59 (Aflou) delivery rates
        r_wil = self.client.put(
            "/api/v1/admin/delivery-zones/59",
            headers=headers,
            json={"home_fee_dzd": 700, "stop_desk_fee_dzd": 450, "estimated_days": "24h - 48h"}
        )
        self.assertEqual(r_wil.status_code, 200)
        self.assertEqual(r_wil.json()["home_fee_dzd"], 700)

        # Adjust variant stock and verify movement logging
        prod = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        vid = prod["variants"][0]["id"]
        prev_stk = prod["variants"][0]["stock_qty"]
        r_adj = self.client.post(
            f"/api/v1/admin/variants/{vid}/adjust-stock",
            headers=headers,
            json={"change_qty": 5, "reason": "restock_arrival"}
        )
        self.assertEqual(r_adj.status_code, 200)
        self.assertEqual(r_adj.json()["new_qty"], prev_stk + 5)

        # Verify customers & reports endpoints
        r_cust = self.client.get("/api/v1/admin/customers", headers=headers)
        self.assertEqual(r_cust.status_code, 200)
        r_rep = self.client.get("/api/v1/admin/reports", headers=headers)
        self.assertEqual(r_rep.status_code, 200)
        self.assertIn("product_performance", r_rep.json())

    # 22. End-to-End CMS Wilaya Home vs Stop-Desk Pricing -> Storefront Live Display & Automatic Order Total Calculation
    def test_22_cms_wilaya_home_and_stop_desk_pricing_auto_calculates_order_total(self):
        headers = self.get_admin_headers()
        # Step 1: Admin configures Wilaya 16 (Alger) Home = 450 DA and Stop-Desk = 250 DA in the CMS
        r_upd = self.client.put(
            "/api/v1/admin/delivery-zones/16",
            headers=headers,
            json={
                "home_fee_dzd": 450,
                "stop_desk_fee_dzd": 250,
                "home_supported": True,
                "stop_desk_supported": True,
                "estimated_days": "24h"
            }
        )
        self.assertEqual(r_upd.status_code, 200, r_upd.text)

        # Step 2: Customer on Storefront selects Wilaya 16 (subtotal = 4500 DA) and toggles between Home and Stop-Desk
        r_calc_home = self.client.get("/api/v1/delivery-zones/calculate?wilaya_code=16&delivery_method=home&subtotal_dzd=4500")
        self.assertEqual(r_calc_home.status_code, 200)
        self.assertEqual(r_calc_home.json()["delivery_fee_dzd"], 450)
        self.assertEqual(r_calc_home.json()["total_dzd"], 4950)
        self.assertEqual(r_calc_home.json()["home_rate"]["fee_dzd"], 450)
        self.assertEqual(r_calc_home.json()["stop_desk_rate"]["fee_dzd"], 250)

        r_calc_desk = self.client.get("/api/v1/delivery-zones/calculate?wilaya_code=16&delivery_method=stop_desk&subtotal_dzd=4500")
        self.assertEqual(r_calc_desk.status_code, 200)
        self.assertEqual(r_calc_desk.json()["delivery_fee_dzd"], 250)
        self.assertEqual(r_calc_desk.json()["total_dzd"], 4750)

        # Step 3: Customer places Guest Order with Stop-Desk in Wilaya 16 -> Server automatically calculates 4500 + 250 = 4750 DA
        prod = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        vid = prod["variants"][2]["id"] # Bordeaux / L (4500 DA)
        r_ord = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Meriem Touati",
                "phone": "0559887766",
                "wilaya_code": "16",
                "commune": "Bab Ezzouar",
                "delivery_address": "Agence Stop-Desk Bab Ezzouar",
                "delivery_method": "stop_desk",
                "items": [{"variant_id": vid, "quantity": 1}]
            }
        )
        self.assertEqual(r_ord.status_code, 201, r_ord.text)
        self.assertEqual(r_ord.json()["subtotal_dzd"], 4500)
        self.assertEqual(r_ord.json()["delivery_fee_dzd"], 250)
        self.assertEqual(r_ord.json()["total_dzd"], 4750)

    # 23. Comprehensive Dashboard Metrics & Real-Time Backup / Sync Status (Section 3.1)
    def test_23_dashboard_comprehensive_metrics_and_backup_status(self):
        headers = self.get_admin_headers()
        r_dash = self.client.get("/api/v1/admin/dashboard", headers=headers)
        self.assertEqual(r_dash.status_code, 200)
        d = r_dash.json()
        self.assertIn("total_active_products", d)
        self.assertIn("total_categories", d)
        self.assertIn("low_stock_variants", d)
        self.assertIn("out_of_stock_variants", d)
        self.assertIn("orders_by_status", d)
        self.assertIn("recent_orders", d)
        self.assertIn("recent_activity", d)
        self.assertIn("backend_sync_status", d)
        self.assertTrue(d["backend_sync_status"]["connected"])
        self.assertGreaterEqual(d["total_categories"], 9)

    # 24. Product Archival Preserves Historical Order Records & Historical Price Immutability (Sections 3.2 & 3.5)
    def test_24_product_archival_preserves_historical_orders_and_price_immutability(self):
        headers = self.get_admin_headers()
        prod = self.client.get("/api/v1/products/sac-a-main-chanel-style").json()
        prod_id = prod["id"]
        vid = prod["variants"][0]["id"]
        original_unit_price = prod["variants"][0]["effective_price_dzd"]

        # Place a guest order at the original price
        r_ord = self.client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": "idem-hist-price-001"},
            json={
                "full_name": "Nadia Benali",
                "phone": "0655534154",
                "wilaya_code": "09",
                "commune": "Ouled Yaïch",
                "delivery_address": "FVX6+GCJ Mus luxury, Ouled Yaïch",
                "delivery_method": "home",
                "items": [{"variant_id": vid, "quantity": 1}]
            }
        )
        self.assertEqual(r_ord.status_code, 201, r_ord.text)
        order_id = r_ord.json()["order_id"]

        # Admin edits the product's current selling price from 4500 DA to 9900 DA
        r_admin_prods = self.client.get("/api/v1/admin/products", headers=headers)
        self.assertEqual(r_admin_prods.status_code, 200)
        current_ver = next(p["version"] for p in r_admin_prods.json()["items"] if p["id"] == prod_id)

        r_upd = self.client.put(
            f"/api/v1/admin/products/{prod_id}",
            headers=headers,
            json={
                "name_fr": prod["name_fr"],
                "selling_price_dzd": 9900,
                "expected_version": current_ver
            }
        )
        self.assertEqual(r_upd.status_code, 200)

        # Verify historical order invoice STILL records the original unit price (price immutability)
        r_inv = self.client.get(f"/api/v1/admin/orders/{order_id}/invoice", headers=headers)
        self.assertEqual(r_inv.status_code, 200)
        self.assertEqual(r_inv.json()["items"][0]["unit_price_dzd"], original_unit_price)
        self.assertIn("Ouled Yaïch", r_inv.json()["boutique_info"]["address"])
        self.assertEqual(r_inv.json()["boutique_info"]["phone"], "0655534154")

        # Now safely archive/delete the product and verify historical order is still intact
        r_del = self.client.delete(f"/api/v1/admin/products/{prod_id}", headers=headers)
        self.assertEqual(r_del.status_code, 200)
        self.assertTrue(r_del.json()["archived"])
        self.assertGreaterEqual(r_del.json()["historical_order_items_preserved"], 1)

        # Public product page returns 404 after archival, but historical order invoice remains 200 OK
        r_pub_after = self.client.get("/api/v1/products/sac-a-main-chanel-style")
        self.assertEqual(r_pub_after.status_code, 404)
        r_inv_after = self.client.get(f"/api/v1/admin/orders/{order_id}/invoice", headers=headers)
        self.assertEqual(r_inv_after.status_code, 200)
        self.assertEqual(len(r_inv_after.json()["items"]), 1)

    # 25. Explicit Idempotency-Key Header, Order Status Transition State Machine & CSV Export (Section 3.5)
    def test_25_order_idempotency_key_and_status_transition_state_machine(self):
        headers = self.get_admin_headers()
        prod = self.client.get("/api/v1/products").json()["items"][0]
        vid = prod["variants"][0]["id"]

        order_payload = {
            "full_name": "Karim Mansouri",
            "phone": "0655534154",
            "wilaya_code": "09",
            "commune": "Ouled Yaïch",
            "delivery_address": "Rue Principale, Ouled Yaïch",
            "delivery_method": "stop_desk",
            "items": [{"variant_id": vid, "quantity": 1}]
        }
        r1 = self.client.post("/api/v1/orders", headers={"Idempotency-Key": "retry-key-999"}, json=order_payload)
        self.assertEqual(r1.status_code, 201)
        oid = r1.json()["order_id"]

        # Retrying with the same Idempotency-Key must be rejected with 409 Conflict
        r2 = self.client.post("/api/v1/orders", headers={"Idempotency-Key": "retry-key-999"}, json=order_payload)
        self.assertEqual(r2.status_code, 409)

        # Transition order -> confirmed -> delivered
        r_conf = self.client.patch(f"/api/v1/admin/orders/{oid}", headers=headers, json={"status": "confirmed"})
        self.assertEqual(r_conf.status_code, 200)
        r_deliv = self.client.patch(f"/api/v1/admin/orders/{oid}", headers=headers, json={"status": "delivered"})
        self.assertEqual(r_deliv.status_code, 200)

        # Invalid transition from terminal 'delivered' back to 'preparing' must fail with 400
        r_invalid = self.client.patch(f"/api/v1/admin/orders/{oid}", headers=headers, json={"status": "preparing"})
        self.assertEqual(r_invalid.status_code, 400)

        # Verify CSV export
        r_csv = self.client.get("/api/v1/admin/orders/export.csv", headers=headers)
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("order_reference", r_csv.text)

    # 26. Real Compressed Backup Archive Creation & Isolated Non-Destructive Restoration Test (Section 7)
    def test_26_isolated_backup_creation_and_non_destructive_restore_verification(self):
        headers = self.get_admin_headers()
        r_bkp = self.client.post("/api/v1/admin/backups", headers=headers)
        self.assertEqual(r_bkp.status_code, 201)
        bkp_id = r_bkp.json()["id"]
        self.assertGreater(r_bkp.json()["size_bytes"], 1000)

        # Trigger isolated restoration verification into temporary database
        r_ver = self.client.post(f"/api/v1/admin/backups/{bkp_id}/verify-restore", headers=headers)
        self.assertEqual(r_ver.status_code, 200, r_ver.text)
        ver_data = r_ver.json()
        self.assertTrue(ver_data["sha256_verified"])
        self.assertTrue(ver_data["isolated_restore_success"])
        self.assertEqual(ver_data["restored_counts"]["delivery_zones"], 69)
        self.assertGreaterEqual(ver_data["restored_counts"]["categories"], 9)

    # 27. Complete 14-Step End-to-End Integration Journey (Section 10)
    def test_27_complete_14_step_end_to_end_journey(self):
        # Step 1: Log in as an authorized administrator
        headers = self.get_admin_headers()

        # Step 2: Create a category with custom attributes
        r_cat = self.client.post(
            "/api/v1/admin/categories",
            headers=headers,
            json={
                "slug": "maroquinerie-voyage",
                "name_fr": "Maroquinerie de Voyage",
                "name_ar": "حقائب سفر",
                "name_en": "Travel Leather Goods",
                "display_order": 12,
                "is_active": True,
                "show_on_homepage": True
            }
        )
        self.assertEqual(r_cat.status_code, 201)
        cat_id = r_cat.json()["id"]

        r_attr1 = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=headers,
            json={
                "category_id": cat_id,
                "attr_key": "color",
                "label_fr": "Couleur",
                "input_type": "color",
                "is_required": True,
                "is_filterable": True,
                "is_variant_axis": True,
                "options": [
                    {"value": "Émeraude", "label_fr": "Émeraude", "color_hex": "#063D2E"},
                    {"value": "Noir", "label_fr": "Noir", "color_hex": "#181818"}
                ]
            }
        )
        self.assertEqual(r_attr1.status_code, 201)

        r_attr2 = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=headers,
            json={
                "category_id": cat_id,
                "attr_key": "cabin_approved",
                "label_fr": "Format Cabine",
                "input_type": "short_text",
                "is_required": True,
                "is_filterable": True,
                "is_variant_axis": False
            }
        )
        self.assertEqual(r_attr2.status_code, 201)

        # Step 3 & 4: Add a brand, upload a product image, and create a draft product in that category
        r_brand = self.client.post(
            "/api/v1/admin/brands",
            headers=headers,
            json={"name": "Mus Voyage 09", "slug": "mus-voyage-09", "logo_url": "/assets/mus_luxury_logo.png"}
        )
        self.assertEqual(r_brand.status_code, 201)
        brand_id = r_brand.json()["id"]

        valid_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r_up = self.client.post(
            "/api/v1/admin/upload",
            headers=headers,
            files={"file": ("bagage_luxe.png", valid_png, "image/png")}
        )
        self.assertEqual(r_up.status_code, 201)
        uploaded_url = r_up.json()["url"]

        r_prod = self.client.post(
            "/api/v1/admin/products",
            headers=headers,
            json={
                "category_id": cat_id,
                "brand_id": brand_id,
                "slug": "sac-cabine-ouled-yaich",
                "sku": "LUX-TRV-009",
                "name_fr": "Sac Cabine Émeraude",
                "purchase_cost_dzd": 7500,
                "selling_price_dzd": 12500,
                "main_image_url": uploaded_url,
                "status": "draft",
                "dynamic_attributes": {"cabin_approved": "Oui (55x35x25 cm)"},
                "variants": []
            }
        )
        self.assertEqual(r_prod.status_code, 201)
        prod_id = r_prod.json()["id"]

        # Step 5: Configure variants, prices, and stock via matrix generator
        r_gen = self.client.post(
            f"/api/v1/admin/products/{prod_id}/generate-variants",
            headers=headers,
            json={"axes": {"color": ["Émeraude", "Noir"]}, "default_stock": 6, "price_override_dzd": 12500}
        )
        self.assertEqual(r_gen.status_code, 201)
        var_id = r_gen.json()["created"][0]["id"]

        # Step 6: Publish the product
        r_pub = self.client.put(
            f"/api/v1/admin/products/{prod_id}",
            headers=headers,
            json={
                "name_fr": "Sac Cabine Émeraude",
                "selling_price_dzd": 12500,
                "status": "published",
                "expected_version": 1
            }
        )
        self.assertEqual(r_pub.status_code, 200)
        self.assertEqual(r_pub.json()["status"], "published")

        # Step 7: Open the public website API and verify actual product data
        r_web = self.client.get("/api/v1/products/sac-cabine-ouled-yaich")
        self.assertEqual(r_web.status_code, 200)
        web_prod = r_web.json()
        self.assertNotIn("purchase_cost_dzd", web_prod)
        self.assertEqual(web_prod["attributes"]["cabin_approved"], "Oui (55x35x25 cm)")
        self.assertEqual(web_prod["total_stock"], 12)

        # Step 8: Submit a guest order (2 units in Wilaya 09 - Blida, Ouled Yaïch)
        r_order = self.client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": "e2e-14step-order-key"},
            json={
                "full_name": "Sofiane Boudiaf",
                "phone": "0655534154",
                "wilaya_code": "09",
                "commune": "Ouled Yaïch",
                "delivery_address": "FVX6+GCJ Mus luxury, Ouled Yaïch",
                "delivery_method": "home",
                "items": [{"variant_id": var_id, "quantity": 2}]
            }
        )
        self.assertEqual(r_order.status_code, 201)
        order_id = r_order.json()["order_id"]

        # Step 9: Confirm the order appears in the CMS
        r_cms_orders = self.client.get("/api/v1/admin/orders", headers=headers)
        self.assertEqual(r_cms_orders.status_code, 200)
        self.assertTrue(any(o["id"] == order_id for o in r_cms_orders.json()["items"]))

        # Step 10: Confirm inventory changes accurately (6 -> 4) and movement is logged
        r_web_after = self.client.get("/api/v1/products/sac-cabine-ouled-yaich").json()
        v_after = next(v for v in r_web_after["variants"] if v["id"] == var_id)
        self.assertEqual(v_after["stock_qty"], 4)

        r_mov = self.client.get(f"/api/v1/admin/inventory/movements?variant_id={var_id}", headers=headers)
        self.assertEqual(r_mov.status_code, 200)
        self.assertGreaterEqual(len(r_mov.json()["items"]), 1)

        # Step 11 & 12: Update the order status (confirmed -> cancelled) and verify stock restoration (4 -> 6)
        r_st1 = self.client.patch(f"/api/v1/admin/orders/{order_id}", headers=headers, json={"status": "confirmed"})
        self.assertEqual(r_st1.status_code, 200)
        r_st2 = self.client.patch(f"/api/v1/admin/orders/{order_id}", headers=headers, json={"status": "cancelled"})
        self.assertEqual(r_st2.status_code, 200)

        r_web_restored = self.client.get("/api/v1/products/sac-cabine-ouled-yaich").json()
        v_restored = next(v for v in r_web_restored["variants"] if v["id"] == var_id)
        self.assertEqual(v_restored["stock_qty"], 6)

        # Step 13: Re-query delta synchronization endpoint as after CMS relaunch and confirm persistent state
        r_sync = self.client.get("/api/v1/admin/sync/delta?since_order_id=0&since_movement_id=0", headers=headers)
        self.assertEqual(r_sync.status_code, 200)
        self.assertGreaterEqual(r_sync.json()["latest_order_id"], order_id)

        # Step 14: Test an unauthorized request and verify it is rejected (401)
        r_unauth = self.client.post("/api/v1/admin/products", json={})
        self.assertEqual(r_unauth.status_code, 401)


    # 28. Healthcheck & Static Content Pages CRUD + Publication Toggle (Sections 3.7 & 9)
    def test_28_healthcheck_and_static_pages_crud(self):
        r_health = self.client.get("/api/v1/health")
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json()["status"], "ok")
        self.assertEqual(r_health.json()["active_wilayas"], 69)

        headers = self.get_admin_headers()
        r_put = self.client.put(
            "/api/v1/admin/pages/la-maison",
            headers=headers,
            json={
                "title_fr": "La Maison Mus Luxury — Ouled Yaïch",
                "content_fr": "Boutique officielle située à FVX6+GCJ Mus luxury, Ouled Yaïch (Blida 09). Tél/WhatsApp: 0655534154.",
                "is_published": True
            }
        )
        self.assertEqual(r_put.status_code, 200)

        r_pub = self.client.get("/api/v1/pages/la-maison")
        self.assertEqual(r_pub.status_code, 200)
        self.assertIn("0655534154", r_pub.json()["content_fr"])

        # Unpublish page and confirm it is hidden from public route
        self.client.put(
            "/api/v1/admin/pages/la-maison",
            headers=headers,
            json={
                "title_fr": "La Maison Mus Luxury — Ouled Yaïch",
                "content_fr": "Brouillon privé",
                "is_published": False
            }
        )
        r_unpub = self.client.get("/api/v1/pages/la-maison")
        self.assertEqual(r_unpub.status_code, 404)

    # 29. Product Image Gallery Upload, Primary Selection, Reorder & Delete (Section 3.2)
    def test_29_product_image_gallery_upload_reorder_and_delete(self):
        headers = self.get_admin_headers()
        prod = self.client.get("/api/v1/products").json()["items"][0]
        pid = prod["id"]
        slug = prod["slug"]

        r_img1 = self.client.post(
            f"/api/v1/admin/products/{pid}/images",
            headers=headers,
            json={"image_url": "/uploads/gallery_1.jpg", "alt_text": "Vue avant", "display_order": 1, "set_as_primary": False}
        )
        self.assertEqual(r_img1.status_code, 201)
        img1_id = r_img1.json()["id"]

        r_img2 = self.client.post(
            f"/api/v1/admin/products/{pid}/images",
            headers=headers,
            json={"image_url": "/uploads/gallery_2.jpg", "alt_text": "Vue côté", "display_order": 2, "set_as_primary": True}
        )
        self.assertEqual(r_img2.status_code, 201)
        img2_id = r_img2.json()["id"]

        # Reorder so img2 is order 1 and img1 is order 2
        r_reord = self.client.put(
            f"/api/v1/admin/products/{pid}/images/reorder",
            headers=headers,
            json={
                "orders": [
                    {"image_id": img2_id, "display_order": 1},
                    {"image_id": img1_id, "display_order": 2}
                ],
                "primary_image_url": "/uploads/gallery_2.jpg"
            }
        )
        self.assertEqual(r_reord.status_code, 200)
        self.assertEqual(r_reord.json()["items"][0]["id"], img2_id)

        # Verify public PDP reflects new primary image and ordered gallery_images
        r_pdp = self.client.get(f"/api/v1/products/{slug}").json()
        self.assertEqual(r_pdp["main_image_url"], "/uploads/gallery_2.jpg")
        self.assertEqual(r_pdp["gallery_images"][0]["id"], img2_id)

        # Delete first image
        r_del = self.client.delete(f"/api/v1/admin/product-images/{img1_id}", headers=headers)
        self.assertEqual(r_del.status_code, 200)
        self.assertTrue(r_del.json()["deleted"])

    # 30. Concurrent Stock Reservation Protection Against Overselling (Section 3.4 & 10)
    def test_30_concurrent_order_submissions_prevent_overselling(self):
        import concurrent.futures
        headers = self.get_admin_headers()
        prod = self.client.get("/api/v1/products").json()["items"][0]
        vid = prod["variants"][0]["id"]
        cur_stk = prod["variants"][0]["stock_qty"]

        # Set exact stock of this variant to 2 units
        delta = 2 - cur_stk
        if delta != 0:
            r_set = self.client.post(
                f"/api/v1/admin/variants/{vid}/adjust-stock",
                headers=headers,
                json={"change_qty": delta, "reason": "prepare_concurrency_test"}
            )
            self.assertEqual(r_set.status_code, 200)

        def submit_buyer_order(idx: int):
            from fastapi.testclient import TestClient
            from app.main import app as fastapi_app
            local_client = TestClient(fastapi_app)
            return local_client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": f"concurrent-buyer-{idx}"},
                json={
                    "full_name": f"Client Concurrent {idx}",
                    "phone": f"065553415{idx}",
                    "wilaya_code": "09",
                    "commune": "Ouled Yaïch",
                    "delivery_address": "Ouled Yaïch Centre",
                    "delivery_method": "home",
                    "items": [{"variant_id": vid, "quantity": 1}]
                }
            ).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(submit_buyer_order, range(1, 7)))

        # Exactly 2 orders must succeed (201) and 4 must fail with 409 Insufficient Stock
        self.assertEqual(statuses.count(201), 2, f"Expected exactly 2 successful orders, got {statuses}")
        self.assertEqual(statuses.count(409), 4, f"Expected 4 stock conflicts, got {statuses}")

        # Verify stock is exactly 0 and never negative
        prod_after = self.client.get(f"/api/v1/products/{prod['slug']}").json()
        v_after = next(v for v in prod_after["variants"] if v["id"] == vid)
        self.assertEqual(v_after["stock_qty"], 0)

    # 31. Database Migration Parity (SQLite vs PostgreSQL 16) & Schema Validation (Section 9 & 10)
    def test_31_database_migration_schema_parity_sqlite_and_postgres(self):
        import re as _re
        base_dir = os.path.dirname(os.path.dirname(__file__))
        sqlite_path = os.path.join(base_dir, "migrations", "001_initial_schema.sql")
        pg_path = os.path.join(base_dir, "migrations", "001_initial_schema_postgres.sql")
        self.assertTrue(os.path.isfile(sqlite_path))
        self.assertTrue(os.path.isfile(pg_path))

        with open(sqlite_path, "r", encoding="utf-8") as f1, open(pg_path, "r", encoding="utf-8") as f2:
            s_sql = f1.read()
            p_sql = f2.read()

        sqlite_tables = set(_re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", s_sql))
        pg_tables = set(_re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", p_sql))
        self.assertEqual(sqlite_tables, pg_tables)
        self.assertGreaterEqual(len(pg_tables), 20)
        self.assertNotIn("AUTOINCREMENT", p_sql)
        self.assertIn("SERIAL PRIMARY KEY", p_sql)
        self.assertIn("idx_orders_idempotency", p_sql)

    # 32. Frontend & Desktop CMS API Contract, No-Secret Audit & Shell Script Validation (Sections 8, 10 & 11)
    def test_32_desktop_cms_and_storefront_tsx_ast_and_contract_verification(self):
        import re as _re
        import subprocess
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 1. Verify all registered FastAPI routes cover every endpoint in DesktopCmsApi & Storefront client
        registered_paths = {getattr(r, "path", "") for r in app.routes}
        required_contracts = [
            "/api/v1/health",
            "/api/v1/store/layout",
            "/api/v1/categories",
            "/api/v1/products",
            "/api/v1/delivery-zones",
            "/api/v1/delivery-zones/calculate",
            "/api/v1/orders",
            "/api/v1/orders/track",
            "/api/v1/admin/auth/setup-status",
            "/api/v1/admin/auth/initialize-owner",
            "/api/v1/admin/auth/login",
            "/api/v1/admin/auth/logout",
            "/api/v1/admin/dashboard",
            "/api/v1/admin/sync/delta",
            "/api/v1/admin/products",
            "/api/v1/admin/products/{product_id}",
            "/api/v1/admin/products/{product_id}/images",
            "/api/v1/admin/products/{product_id}/images/reorder",
            "/api/v1/admin/product-images/{image_id}",
            "/api/v1/admin/categories",
            "/api/v1/admin/categories/{category_id}",
            "/api/v1/admin/category-attributes",
            "/api/v1/admin/variants/{variant_id}/adjust-stock",
            "/api/v1/admin/inventory/movements",
            "/api/v1/admin/orders",
            "/api/v1/admin/orders/{order_id}",
            "/api/v1/admin/orders/{order_id}/invoice",
            "/api/v1/admin/orders/export.csv",
            "/api/v1/admin/delivery-zones/{wilaya_code}",
            "/api/v1/admin/delivery-zones-bulk",
            "/api/v1/admin/pages/{slug}",
            "/api/v1/admin/backups",
            "/api/v1/admin/backups/{backup_id}/verify-restore",
        ]
        for req_path in required_contracts:
            self.assertIn(req_path, registered_paths, f"Missing route contract: {req_path}")

        # 2. Verify Desktop CMS & Storefront TSX files have real Mus Luxury Ouled Yaïch & 0655534154 details and no mock 550 numbers
        storefront_html = os.path.join(repo_root, "apps", "storefront", "index.html")
        with open(storefront_html, "r", encoding="utf-8") as sf:
            shtml = sf.read()
        self.assertIn("FVX6+GCJ Mus luxury, Ouled Yaïch", shtml)
        self.assertIn("https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux", shtml)
        self.assertIn("https://www.tiktok.com/@musluxury.092?_r=1&_t=ZS-9B2mO0gpA7V", shtml)
        self.assertIn("0655 53 41 54", shtml)
        self.assertNotIn("+213 (0) 550 00 00 00", shtml)

        # 3. Validate bash syntax of all deployment and backup scripts
        scripts = [
            os.path.join(repo_root, "infrastructure", "backups", "backup_postgres_and_media.sh"),
            os.path.join(repo_root, "infrastructure", "backups", "restore_backup.sh"),
            os.path.join(repo_root, "infrastructure", "scripts", "deploy_algeria_vps.sh"),
        ]
        for sc in scripts:
            res = subprocess.run(["bash", "-n", sc], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Syntax error in {sc}: {res.stderr}")


    # 33. Environment Configuration (.env / .env.example) & .gitignore Protection (User Verification)
    def test_33_environment_configuration_and_gitignore_protection(self):
        import subprocess
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_example_path = os.path.join(repo_root, ".env.example")
        gitignore_path = os.path.join(repo_root, ".gitignore")
        self.assertTrue(os.path.isfile(env_example_path), ".env.example must exist at repo root")
        self.assertTrue(os.path.isfile(gitignore_path), ".gitignore must exist at repo root")

        with open(env_example_path, "r", encoding="utf-8") as f:
            env_text = f.read()

        required_env_keys = [
            "SECRET_KEY=",
            "CMS_HMAC_SIGNING_SECRET=",
            "POSTGRES_HOST=",
            "POSTGRES_PORT=",
            "POSTGRES_DB=",
            "POSTGRES_USER=",
            "POSTGRES_PASSWORD=",
            "DATABASE_URL=",
            "LUXE_SQLITE_PATH=",
            "ADMIN_INITIAL_EMAIL=",
            "ADMIN_INITIAL_PASSWORD=",
            "ADMIN_INITIAL_WHATSAPP_PHONE=",
            "ADMIN_EMERGENCY_RECOVERY_CODE=",
            "WHATSAPP_CLOUD_API_TOKEN=",
            "WHATSAPP_PHONE_NUMBER_ID=",
            "WHATSAPP_BUSINESS_ACCOUNT_ID=",
            "WHATSAPP_APP_ID=",
            "WHATSAPP_APP_SECRET=",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN=",
            "WHATSAPP_API_VERSION=",
            "WHATSAPP_TEMPLATE_NAME=",
            "WHATSAPP_SANDBOX_MODE=",
            "YALIDINE_API_ID=",
            "YALIDINE_API_TOKEN=",
            "ZR_EXPRESS_API_KEY=",
            "ZR_EXPRESS_TOKEN=",
            "MAYSTRO_API_TOKEN=",
            "CHARGILY_PUBLIC_KEY=",
            "CHARGILY_SECRET_KEY=",
            "S3_ACCESS_KEY_ID=",
            "S3_SECRET_ACCESS_KEY=",
            "VITE_API_BASE_URL=",
            "VITE_CMS_API_URL=",
        ]
        for key in required_env_keys:
            self.assertIn(key, env_text, f"Missing required environment variable {key} in .env.example")

        # Verify .gitignore blocks .env, *.sqlite3, *.db, and backups from being committed
        res_ignore = subprocess.run(
            ["git", "check-ignore", ".env", "backend/luxe_store.sqlite3"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_ignore.returncode, 0, f".gitignore did not ignore .env: {res_ignore.stderr}")
        self.assertIn(".env", res_ignore.stdout)

    # 34. Algerian Phone Normalization, Boutique Number (0655534154) WhatsApp Recovery & Emergency Code Rotation
    def test_34_whatsapp_recovery_algerian_phone_normalization_and_boutique_number(self):
        from app.whatsapp import normalize_algerian_phone

        for raw in ["0655 53 41 54", "0655-53-41-54", "+213 655 53 41 54", "00213655534154", "213655534154"]:
            e164, local_num, meta_id = normalize_algerian_phone(raw)
            self.assertEqual(e164, "+213655534154")
            self.assertEqual(local_num, "0655534154")
            self.assertEqual(meta_id, "213655534154")

        # Check recovery status endpoint
        os.environ["WHATSAPP_CLOUD_API_TOKEN"] = "EAATest_Sandbox_Token_2026"
        os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "109283746519283"
        os.environ["WHATSAPP_SANDBOX_MODE"] = "true"
        try:
            r_stat = self.client.get("/api/v1/admin/auth/recovery/status")
            self.assertEqual(r_stat.status_code, 200)
            sdata = r_stat.json()
            self.assertTrue(sdata["whatsapp_cloud_api_configured"])
            self.assertEqual(sdata["boutique_whatsapp_local"], "0655534154")

            # Request OTP using local Algerian format 0655534154 (matches owner emergency_phone +213655534154)
            reset_rate_limits()
            r_req = self.client.post(
                "/api/v1/admin/auth/recovery/request",
                json={"phone": "0655 53 41 54", "channel": "whatsapp_cloud_api"}
            )
            self.assertEqual(r_req.status_code, 200, r_req.text)
            req_json = r_req.json()
            self.assertEqual(req_json["status"], "recovery_initiated")
            self.assertIn("test_otp", req_json)
            otp_code = req_json["test_otp"]

            # Verify OTP using international format +213655534154 and set a new password
            r_ver = self.client.post(
                "/api/v1/admin/auth/recovery/verify",
                json={
                    "phone": "+213655534154",
                    "verification_code": otp_code,
                    "new_password": "RecoveredVia0655534154!"
                }
            )
            self.assertEqual(r_ver.status_code, 200, r_ver.text)

            # Log in with the newly recovered password and rotate the offline emergency code
            reset_rate_limits()
            r_login = self.client.post(
                "/api/v1/admin/auth/login",
                json={"email": "admin@musluxury.dz", "password": "RecoveredVia0655534154!"}
            )
            self.assertEqual(r_login.status_code, 200, r_login.text)
            new_token = r_login.json()["access_token"]

            r_rot = self.client.post(
                "/api/v1/admin/auth/recovery/rotate-emergency-code",
                headers={"Authorization": f"Bearer {new_token}"}
            )
            self.assertEqual(r_rot.status_code, 200, r_rot.text)
            fresh_emerg_code = r_rot.json()["emergency_code"]
            self.assertTrue(fresh_emerg_code.startswith("LUXE-EMERG-"))

            # Use the rotated offline emergency code with local phone 0655534154 to restore default password
            r_restore = self.client.post(
                "/api/v1/admin/auth/recovery/verify",
                json={
                    "phone": "0655534154",
                    "verification_code": fresh_emerg_code,
                    "new_password": "MusLuxury2026!"
                }
            )
            self.assertEqual(r_restore.status_code, 200, r_restore.text)
            self.assertIn("replacement_emergency_code", r_restore.json())
        finally:
            reset_rate_limits()

    # 35. Meta WhatsApp Webhook Verification, HMAC Signature Check & CLI Emergency Reset Utility
    def test_35_whatsapp_webhook_verification_and_cli_emergency_reset(self):
        import hashlib as _hashlib
        import hmac as _hmac
        import json
        from scripts.emergency_reset_owner import reset_owner_credentials

        os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = "mus_luxury_wa_webhook_verify_2026_secret"
        os.environ["WHATSAPP_APP_SECRET"] = "meta_app_secret_test_key_2026"

        # 1. GET Webhook Verification Challenge
        r_ok = self.client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "mus_luxury_wa_webhook_verify_2026_secret",
                "hub.challenge": "9988776655",
            },
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.text, "9988776655")

        r_bad = self.client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "9988776655",
            },
        )
        self.assertEqual(r_bad.status_code, 403)

        # 2. POST Webhook Delivery Status Receipt with X-Hub-Signature-256
        webhook_payload = json.dumps({
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "987654321",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "statuses": [{
                            "id": "wamid.TEST_DELIVERED_01",
                            "status": "delivered",
                            "recipient_id": "213655534154"
                        }]
                    }
                }]
            }]
        }).encode("utf-8")
        valid_sig = "sha256=" + _hmac.new(b"meta_app_secret_test_key_2026", webhook_payload, _hashlib.sha256).hexdigest()

        r_post_ok = self.client.post(
            "/api/v1/webhooks/whatsapp",
            content=webhook_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig},
        )
        self.assertEqual(r_post_ok.status_code, 200, r_post_ok.text)
        self.assertEqual(r_post_ok.json()["statuses_logged"], 1)

        r_post_tampered = self.client.post(
            "/api/v1/webhooks/whatsapp",
            content=webhook_payload,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=0000bad"},
        )
        self.assertEqual(r_post_tampered.status_code, 401)

        # 3. Verify CLI Emergency Reset Utility
        info = reset_owner_credentials("admin@musluxury.dz", "MusLuxury2026!")
        self.assertEqual(info["email"], "admin@musluxury.dz")
        self.assertTrue(info["new_emergency_code"].startswith("LUXE-EMERG-"))

    # 36. Tauri 2 Desktop CMS Build Scaffolding & GitHub Actions Workflow Verification
    def test_36_tauri_desktop_cms_build_scaffolding_and_workflow_integrity(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        required_files = [
            os.path.join(repo_root, "apps", "desktop-cms", "package.json"),
            os.path.join(repo_root, "apps", "desktop-cms", "tsconfig.json"),
            os.path.join(repo_root, "apps", "desktop-cms", "vite.config.ts"),
            os.path.join(repo_root, "apps", "desktop-cms", "tailwind.config.js"),
            os.path.join(repo_root, "apps", "desktop-cms", "postcss.config.js"),
            os.path.join(repo_root, "apps", "desktop-cms", "index.html"),
            os.path.join(repo_root, "apps", "desktop-cms", "src", "main.tsx"),
            os.path.join(repo_root, "apps", "desktop-cms", "src", "App.tsx"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "Cargo.toml"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "build.rs"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "tauri.conf.json"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "capabilities", "default.json"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "icons", "icon.ico"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "icons", "32x32.png"),
            os.path.join(repo_root, "apps", "desktop-cms", "src-tauri", "icons", "128x128.png"),
            os.path.join(repo_root, ".github", "workflows", "build-desktop-cms.yml"),
        ]
        for rf in required_files:
            self.assertTrue(os.path.isfile(rf), f"Missing Tauri 2 / Desktop CMS build file: {rf}")


    # 37. Babel TypeScript/React Compilation of Windows Desktop CMS & Strict No-Web-CMS Separation
    def test_37_babel_typescript_react_compilation_and_strict_no_web_cms_separation(self):
        import subprocess
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 1. Compile all Windows Desktop CMS & Public Storefront .ts/.tsx files via Babel TypeScript + React presets
        js_check = """
const fs = require("fs");
const path = require("path");
const babel = require("@babel/core");
const files = [
  "apps/desktop-cms/src/api/adminClient.ts",
  "apps/desktop-cms/src/pages/CategoryBuilderPage.tsx",
  "apps/desktop-cms/src/pages/DeliveryWilayasPage.tsx",
  "apps/desktop-cms/src/App.tsx",
  "apps/desktop-cms/src/main.tsx",
  "apps/storefront/src/api/client.ts",
  "apps/storefront/src/App.tsx",
  "apps/storefront/src/main.tsx",
];
for (const f of files) {
  const full = path.resolve(process.cwd(), f);
  const src = fs.readFileSync(full, "utf8");
  const out = babel.transformSync(src, {
    filename: full,
    presets: [
      ["/usr/share/nodejs/@babel/preset-env", { targets: { esmodules: true } }],
      ["/usr/share/nodejs/@babel/preset-react", { runtime: "automatic" }],
      ["/usr/share/nodejs/@babel/preset-typescript", { isTSX: f.endsWith(".tsx"), allExtensions: true }],
    ],
  });
  if (!out || !out.code || out.code.length < 50) {
    throw new Error("Compilation produced empty output for " + f);
  }
}
console.log("ALL_TSX_COMPILED_OK");
"""
        env = os.environ.copy()
        env["NODE_PATH"] = "/usr/share/nodejs"
        res = subprocess.run(["node", "-e", js_check], cwd=repo_root, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"TypeScript/React compilation failed: {res.stderr}")
        self.assertIn("ALL_TSX_COMPILED_OK", res.stdout)

        # 2. Enforce Strict Architecture Separation: Public Website must NEVER contain Web CMS or Admin Login
        for pub_file in [
            os.path.join(repo_root, "apps", "storefront", "index.html"),
            os.path.join(repo_root, "apps", "storefront", "src", "App.tsx"),
            os.path.join(repo_root, "apps", "storefront", "src", "api", "client.ts"),
        ]:
            with open(pub_file, "r", encoding="utf-8") as pf:
                content = pf.read()
            self.assertNotIn("/admin/auth/login", content, f"Public website file {pub_file} must not contain admin login")
            self.assertNotIn("DesktopCmsApi", content, f"Public website file {pub_file} must not import DesktopCmsApi")


if __name__ == "__main__":
    unittest.main()









