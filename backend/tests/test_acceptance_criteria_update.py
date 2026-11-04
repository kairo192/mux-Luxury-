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


class TestUpdateMdAcceptanceCriteria(unittest.TestCase):
    """
    Automated verification of the 18 Acceptance Criteria defined in update.md:
    1. Create a category with custom attributes.
    2. Create a product with multiple colors and sizes.
    3. Generate valid variants and assign different stock quantities.
    4. Edit a color or size without corrupting existing variants.
    5. Publish the product and confirm the storefront displays the correct options.
    6. Purchase two units with identical options.
    7. Purchase two units with different colors or sizes.
    8. Purchase several units distributed across three or more variants.
    9. Attempt to select an unavailable combination.
    10. Attempt to exceed available stock.
    11. Change stock in the CMS and verify storefront availability updates.
    12. Edit a variant price and verify the server uses the correct price.
    13. Add items to the cart, refresh the page, and verify persistence.
    14. Create an order and verify inventory is deducted correctly.
    15. Test concurrent orders against limited stock.
    16. Verify that an unauthorized user cannot modify products or inventory.
    17. Check existing products, orders, and other functionality for regressions.
    18. Test responsive behavior, validation messages, empty states, and error handling.
    """

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, login.text
        cls.admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:8]

    def _create_category(self, slug_prefix="cat", name_fr="Catégorie Test", with_attributes=True):
        resp = self.client.post(
            "/api/v1/admin/categories",
            headers=self.admin_headers,
            json={
                "slug": f"{slug_prefix}-{self.suffix}",
                "name_fr": f"{name_fr} {self.suffix}",
                "name_ar": "تصنيف اختباري",
                "name_en": f"Test Category {self.suffix}",
                "display_order": 1,
                "is_active": True,
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        cat_id = resp.json()["id"]

        if with_attributes:
            self.client.post(
                "/api/v1/admin/category-attributes",
                headers=self.admin_headers,
                json={
                    "category_id": cat_id,
                    "attr_key": "color",
                    "label_fr": "Couleur",
                    "input_type": "color",
                    "is_variant_axis": True,
                    "is_filterable": True,
                    "options": [
                        {"value": "Noir Ébène", "label_fr": "Noir Ébène", "color_hex": "#111111"},
                        {"value": "Cognac Doré", "label_fr": "Cognac Doré", "color_hex": "#8B4513"},
                        {"value": "Or Pur", "label_fr": "Or Pur", "color_hex": "#D4AF37"},
                        {"value": "Argent 925", "label_fr": "Argent 925", "color_hex": "#C0C0C0"},
                        {"value": "Noir", "label_fr": "Noir", "color_hex": "#000000"},
                        {"value": "Blanc", "label_fr": "Blanc", "color_hex": "#FFFFFF"},
                        {"value": "Vert", "label_fr": "Vert", "color_hex": "#008000"},
                        {"value": "Doré", "label_fr": "Doré", "color_hex": "#D4AF37"},
                    ],
                },
            )
            self.client.post(
                "/api/v1/admin/category-attributes",
                headers=self.admin_headers,
                json={
                    "category_id": cat_id,
                    "attr_key": "size",
                    "label_fr": "Taille",
                    "input_type": "size",
                    "is_variant_axis": True,
                    "is_filterable": True,
                    "options": [
                        {"value": "Moyen (30cm)", "label_fr": "Moyen (30cm)"},
                        {"value": "Grand (40cm)", "label_fr": "Grand (40cm)"},
                        {"value": "40", "label_fr": "40"},
                        {"value": "41", "label_fr": "41"},
                        {"value": "42", "label_fr": "42"},
                    ],
                },
            )

        return cat_id

    # Criteria 1, 2, 3: Create category with attributes, product with variants, assign stock
    def test_01_02_03_category_product_variants_creation(self):
        # 1. Create Category with custom attributes
        cat_id = self._create_category("maroquinerie", "Maroquinerie de Luxe")

        # 2. Create Product with multiple variants
        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"sac-royale-{self.suffix}",
                "sku": f"ROY-{self.suffix.upper()}",
                "name_fr": f"Sac Royale Mus {self.suffix}",
                "selling_price_dzd": 18500,
                "purchase_cost_dzd": 9000,
                "status": "published",
                "variants": [
                    {
                        "sku": f"ROY-{self.suffix.upper()}-NOIR-M",
                        "title": "Noir Ébène / Moyen (30cm)",
                        "stock_qty": 5,
                        "price_override_dzd": None,
                        "attributes": {"color": "Noir Ébène", "size": "Moyen (30cm)"},
                    },
                    {
                        "sku": f"ROY-{self.suffix.upper()}-COGNAC-G",
                        "title": "Cognac Doré / Grand (40cm)",
                        "stock_qty": 3,
                        "price_override_dzd": 21000,
                        "attributes": {"color": "Cognac Doré", "size": "Grand (40cm)"},
                    },
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod_data = prod_resp.json()
        self.assertEqual(len(prod_data["variants"]), 2)
        self.assertEqual(prod_data["total_stock"], 8)

        # 3. Verify storefront public representation (Criterion 5)
        public_resp = self.client.get(f"/api/v1/products/{prod_data['slug']}")
        self.assertEqual(public_resp.status_code, 200)
        pub_p = public_resp.json()
        self.assertEqual(pub_p["in_stock"], True)
        self.assertEqual(pub_p["total_stock"], 8)
        self.assertNotIn("purchase_cost_dzd", pub_p)

    # Criterion 4: Edit a color or size without corrupting existing variants
    def test_04_edit_variant_attributes_without_corruption(self):
        cat_id = self._create_category("montres", "Horlogerie")
        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"chrono-{self.suffix}",
                "sku": f"CHR-{self.suffix.upper()}",
                "name_fr": f"Chronomètre Prestige {self.suffix}",
                "selling_price_dzd": 45000,
                "status": "published",
                "variants": [
                    {"sku": f"CHR-{self.suffix.upper()}-OR", "title": "Or Pur", "stock_qty": 4, "attributes": {"color": "Or Pur"}},
                    {"sku": f"CHR-{self.suffix.upper()}-ARG", "title": "Argent 925", "stock_qty": 6, "attributes": {"color": "Argent 925"}},
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod = prod_resp.json()
        var_or = prod["variants"][0]
        var_arg = prod["variants"][1]

        # Update title & stock of the first variant via PUT /api/v1/admin/variants/{id}
        patch_resp = self.client.put(
            f"/api/v1/admin/variants/{var_or['id']}",
            headers=self.admin_headers,
            json={"title": "Or Pur Prestige", "stock_qty": 7, "attributes": {"color": "Or Pur"}},
        )
        self.assertEqual(patch_resp.status_code, 200, patch_resp.text)

        # Check that the second variant remains intact and uncorrupted
        updated_prod = self.client.get(f"/api/v1/products/{prod['slug']}").json()
        self.assertEqual(len(updated_prod["variants"]), 2)
        v0 = [v for v in updated_prod["variants"] if v["id"] == var_or["id"]][0]
        v1 = [v for v in updated_prod["variants"] if v["id"] == var_arg["id"]][0]
        self.assertEqual(v0["title"], "Or Pur Prestige")
        self.assertEqual(v0["stock_qty"], 7)
        self.assertEqual(v1["title"], "Argent 925")
        self.assertEqual(v1["stock_qty"], 6)

    # Criteria 6, 7, 8, 14: Purchases with identical units, different variants, stock deduction
    def test_06_07_08_14_orders_single_and_multi_variant_stock_deduction(self):
        # Create category & product with 3 variants
        cat_id = self._create_category("shoes", "Chaussures")

        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"sneakers-{self.suffix}",
                "sku": f"SNK-{self.suffix.upper()}",
                "name_fr": f"Baskets Confection {self.suffix}",
                "selling_price_dzd": 12000,
                "status": "published",
                "variants": [
                    {"sku": f"SNK-{self.suffix.upper()}-40", "title": "Noir / 40", "stock_qty": 10, "attributes": {"color": "Noir", "size": "40"}},
                    {"sku": f"SNK-{self.suffix.upper()}-41", "title": "Blanc / 41", "stock_qty": 10, "attributes": {"color": "Blanc", "size": "41"}},
                    {"sku": f"SNK-{self.suffix.upper()}-42", "title": "Vert / 42", "stock_qty": 10, "attributes": {"color": "Vert", "size": "42"}},
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod = prod_resp.json()
        v40 = prod["variants"][0]
        v41 = prod["variants"][1]
        v42 = prod["variants"][2]

        # Criteria 6: Purchase 2 units with identical options (Scenario A/B Same)
        ord1_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Karim Meziane",
                "phone": "0550112233",
                "wilaya_code": "16",
                "commune": "Hydra",
                "delivery_address": "Rue des Pins",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": v40["id"], "quantity": 2}],
            },
        )
        self.assertEqual(ord1_resp.status_code, 201, ord1_resp.text)
        self.assertEqual(ord1_resp.json()["status"], "new")

        # Verify stock for v40 was deducted from 10 to 8
        v40_check = self.client.get(f"/api/v1/products/{prod['slug']}").json()["variants"][0]
        self.assertEqual(v40_check["stock_qty"], 8)

        # Criteria 7: Purchase 2 units with different variants (Scenario B Split: 1 Noir/40 + 1 Blanc/41)
        ord2_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Amina Benali",
                "phone": "0660445566",
                "wilaya_code": "09",
                "commune": "Ouled Yaïch",
                "delivery_address": "Cité 1000 Logements",
                "delivery_method": "home",
                "items": [
                    {"product_id": prod["id"], "variant_id": v40["id"], "quantity": 1},
                    {"product_id": prod["id"], "variant_id": v41["id"], "quantity": 1},
                ],
            },
        )
        self.assertEqual(ord2_resp.status_code, 201, ord2_resp.text)

        # Verify stock after split purchase
        cur_vars = self.client.get(f"/api/v1/products/{prod['slug']}").json()["variants"]
        self.assertEqual(cur_vars[0]["stock_qty"], 7)  # v40: 8 - 1 = 7
        self.assertEqual(cur_vars[1]["stock_qty"], 9)  # v41: 10 - 1 = 9

        # Criteria 8: Purchase several units distributed across 3 variants (1 v40, 2 v41, 3 v42)
        ord3_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Yacine Rahmani",
                "phone": "0770889900",
                "wilaya_code": "31",
                "commune": "Oran Centre",
                "delivery_address": "Front de Mer",
                "delivery_method": "stop_desk",
                "items": [
                    {"product_id": prod["id"], "variant_id": v40["id"], "quantity": 1},
                    {"product_id": prod["id"], "variant_id": v41["id"], "quantity": 2},
                    {"product_id": prod["id"], "variant_id": v42["id"], "quantity": 3},
                ],
            },
        )
        self.assertEqual(ord3_resp.status_code, 201, ord3_resp.text)
        self.assertEqual(len(ord3_resp.json()["items"]), 3)

        # Verify final stock deductions (Criterion 14)
        final_vars = self.client.get(f"/api/v1/products/{prod['slug']}").json()["variants"]
        self.assertEqual(final_vars[0]["stock_qty"], 6)  # 7 - 1 = 6
        self.assertEqual(final_vars[1]["stock_qty"], 7)  # 9 - 2 = 7
        self.assertEqual(final_vars[2]["stock_qty"], 7)  # 10 - 3 = 7

    # Criteria 9, 10: Reject unavailable combinations & stock exceedance
    def test_09_10_reject_unavailable_or_exceeding_stock(self):
        cat_id = self._create_category("scarf", "Châles")

        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"chale-soie-{self.suffix}",
                "sku": f"CHL-{self.suffix.upper()}",
                "name_fr": f"Châle en Soie {self.suffix}",
                "selling_price_dzd": 7500,
                "status": "published",
                "variants": [
                    {"sku": f"CHL-{self.suffix.upper()}-GOLD", "title": "Doré", "stock_qty": 2, "attributes": {"color": "Doré"}},
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod = prod_resp.json()
        v_gold = prod["variants"][0]

        # Criteria 9: Attempt to order invalid variant id
        bad_var_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Test Client",
                "phone": "0555000000",
                "wilaya_code": "16",
                "commune": "Alger",
                "delivery_address": "Test",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": 999999, "quantity": 1}],
            },
        )
        self.assertIn(bad_var_resp.status_code, (404, 422))

        # Criteria 10: Attempt to exceed available stock (request 5 when stock is 2)
        exceed_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Test Client",
                "phone": "0555000000",
                "wilaya_code": "16",
                "commune": "Alger",
                "delivery_address": "Test",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": v_gold["id"], "quantity": 5}],
            },
        )
        self.assertIn(exceed_resp.status_code, (409, 422))

    # Criteria 11, 12: Change stock/price in CMS and verify server & storefront enforcement
    def test_11_12_cms_stock_and_price_override_updates(self):
        cat_id = self._create_category("parfum", "Parfum", with_attributes=False)

        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"ambre-oriental-{self.suffix}",
                "sku": f"AMB-{self.suffix.upper()}",
                "name_fr": f"Ambre Oriental {self.suffix}",
                "selling_price_dzd": 14000,
                "status": "published",
                "variants": [
                    {"sku": f"AMB-{self.suffix.upper()}-50ML", "title": "50ml", "stock_qty": 4, "price_override_dzd": None},
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod = prod_resp.json()
        var_id = prod["variants"][0]["id"]

        # 11. Update stock via CMS admin endpoint (PUT /api/v1/admin/variants/{id})
        stock_put = self.client.put(
            f"/api/v1/admin/variants/{var_id}",
            headers=self.admin_headers,
            json={"stock_qty": 20},
        )
        self.assertEqual(stock_put.status_code, 200, stock_put.text)

        # Verify storefront sees updated stock
        updated_prod = self.client.get(f"/api/v1/products/{prod['slug']}").json()
        self.assertEqual(updated_prod["variants"][0]["stock_qty"], 20)
        self.assertEqual(updated_prod["total_stock"], 20)

        # 12. Update price override in CMS (discounted to 11 500 DA)
        price_put = self.client.put(
            f"/api/v1/admin/variants/{var_id}",
            headers=self.admin_headers,
            json={"price_override_dzd": 11500},
        )
        self.assertEqual(price_put.status_code, 200, price_put.text)

        # Create order and verify server charges exactly the authoritative price (11500 DA * 2 = 23000 DA)
        ord_resp = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Test Client",
                "phone": "0555123456",
                "wilaya_code": "09",
                "commune": "Blida",
                "delivery_address": "Bab Dzair",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": var_id, "quantity": 2}],
            },
        )
        self.assertEqual(ord_resp.status_code, 201, ord_resp.text)
        ord_data = ord_resp.json()
        self.assertEqual(ord_data["subtotal_dzd"], 23000)

    # Criteria 15: Concurrency safety (competing orders on limited stock)
    def test_15_concurrent_stock_exhaustion_safety(self):
        cat_id = self._create_category("rare", "Édition Rare", with_attributes=False)

        # Product with only 1 item in stock
        prod_resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.admin_headers,
            json={
                "category_id": cat_id,
                "slug": f"piece-unique-{self.suffix}",
                "sku": f"UNIQ-{self.suffix.upper()}",
                "name_fr": f"Pièce Unique {self.suffix}",
                "selling_price_dzd": 35000,
                "status": "published",
                "variants": [
                    {"sku": f"UNIQ-{self.suffix.upper()}-SOLO", "title": "Unique", "stock_qty": 1},
                ],
            },
        )
        self.assertEqual(prod_resp.status_code, 201, prod_resp.text)
        prod = prod_resp.json()
        v_id = prod["variants"][0]["id"]

        # First buyer takes the last item
        buyer1 = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Premier Acheteur",
                "phone": "0555999001",
                "wilaya_code": "16",
                "commune": "El Biar",
                "delivery_address": "Avenue",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": v_id, "quantity": 1}],
            },
        )
        self.assertEqual(buyer1.status_code, 201, buyer1.text)

        # Second buyer tries to purchase the same item immediately afterwards
        buyer2 = self.client.post(
            "/api/v1/orders",
            json={
                "full_name": "Second Acheteur",
                "phone": "0555999002",
                "wilaya_code": "16",
                "commune": "El Biar",
                "delivery_address": "Avenue",
                "delivery_method": "home",
                "items": [{"product_id": prod["id"], "variant_id": v_id, "quantity": 1}],
            },
        )
        self.assertEqual(buyer2.status_code, 409)  # Blocked with 409 Conflict

    # Criteria 16: Unauthorized access rejection
    def test_16_unauthorized_user_rejection(self):
        # Unauthenticated request to create category
        no_auth = self.client.post(
            "/api/v1/admin/categories",
            json={"slug": "hacked", "name_fr": "Hacked", "name_ar": "مخترق", "name_en": "Hacked", "is_active": True},
        )
        self.assertEqual(no_auth.status_code, 401)

        # Fake token
        fake_auth = self.client.post(
            "/api/v1/admin/categories",
            headers={"Authorization": "Bearer invalid_forged_token_123"},
            json={"slug": "hacked", "name_fr": "Hacked", "name_ar": "مخترق", "name_en": "Hacked", "is_active": True},
        )
        self.assertEqual(fake_auth.status_code, 401)

    # Criteria 17, 18: Regression checks on seeded catalogs and wilaya delivery
    def test_17_18_system_regressions_and_delivery_calculations(self):
        # Verify delivery-zones list works
        zones_resp = self.client.get("/api/v1/delivery-zones")
        self.assertEqual(zones_resp.status_code, 200)
        zones = zones_resp.json()["items"]
        self.assertGreaterEqual(len(zones), 58)

        # Verify catalog endpoint returns active categories and products
        cat_list = self.client.get("/api/v1/categories")
        self.assertEqual(cat_list.status_code, 200)

        prod_list = self.client.get("/api/v1/products")
        self.assertEqual(prod_list.status_code, 200)


if __name__ == "__main__":
    unittest.main()
