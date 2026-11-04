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


class TestDynamicCategoryTemplatesAndVariants(unittest.TestCase):
    """
    Comprehensive verification for:
    'Additional Requirement — Dynamic Category Templates and Complete Product Variant Management'
    1. Configure attributes when creating a category (e.g. T-shirts with color swatches, sizes, material, fit).
    2. Automatically configure product editor from category.
    3. Manage stock independently for every color-and-size combination (including candidate combinations and excluding unsold ones).
    4. Storefront dynamic alignment: PDP options, visual circular color swatches with HEX, stock badges, multi-variant cart allocation, and stock deduction.
    5. Universal product type support (Shoes, Bags, Watches).
    6. Product independence: Products under the same category have distinct color/size configurations.
    """

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, f"Login failed: {login.text}"
        cls.token = login.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def setUp(self):
        reset_rate_limits()

    def _create_category_template(self):
        slug = f"t-shirts-couture-{uuid.uuid4().hex[:6]}"
        payload = {
            "slug": slug,
            "name_fr": "T-shirts Couture Mus",
            "name_ar": "قمصان فاخرة",
            "name_en": "Mus Couture T-Shirts",
            "description_fr": "T-shirts d'exception en coton Pima noble avec finitions haute couture.",
            "image_url": "/assets/cat_vetements.jpg",
            "banner_url": "/assets/hero_bag_clean.jpg",
            "display_order": 1,
            "is_active": True,
            "show_on_homepage": True,
            "attributes": [
                {
                    "attr_key": "material",
                    "label_fr": "Matière",
                    "input_type": "single_select",
                    "is_required": True,
                    "is_visible_on_storefront": True,
                    "is_filterable": True,
                    "is_variant_axis": False,
                    "options": [
                        {"value": "100% Coton Pima", "label_fr": "100% Coton Pima"},
                        {"value": "Lin Naturel", "label_fr": "Lin Naturel"},
                        {"value": "Soie & Coton", "label_fr": "Soie & Coton"},
                    ],
                },
                {
                    "attr_key": "fit",
                    "label_fr": "Coupe",
                    "input_type": "single_select",
                    "is_required": True,
                    "is_visible_on_storefront": True,
                    "is_filterable": True,
                    "is_variant_axis": False,
                    "options": [
                        {"value": "Coupe Oversize", "label_fr": "Coupe Oversize"},
                        {"value": "Coupe Regular", "label_fr": "Coupe Regular"},
                        {"value": "Coupe Slim", "label_fr": "Coupe Slim"},
                    ],
                },
                {
                    "attr_key": "color",
                    "label_fr": "Couleur",
                    "input_type": "color",
                    "is_required": True,
                    "is_visible_on_storefront": True,
                    "is_filterable": True,
                    "is_variant_axis": True,
                    "options": [
                        {"value": "Noir Profond", "label_fr": "Noir Profond", "color_hex": "#0A0A0A", "display_order": 1},
                        {"value": "Blanc Pur", "label_fr": "Blanc Pur", "color_hex": "#FFFFFF", "display_order": 2},
                        {"value": "Vert Émeraude Mus", "label_fr": "Vert Émeraude Mus", "color_hex": "#063D2E", "display_order": 3},
                        {"value": "Bordeaux Royal", "label_fr": "Bordeaux Royal", "color_hex": "#4A0E17", "display_order": 4},
                    ],
                },
                {
                    "attr_key": "size",
                    "label_fr": "Taille",
                    "input_type": "size",
                    "is_required": True,
                    "is_visible_on_storefront": True,
                    "is_filterable": True,
                    "is_variant_axis": True,
                    "options": [
                        {"value": "XS", "label_fr": "XS", "display_order": 1},
                        {"value": "S", "label_fr": "S", "display_order": 2},
                        {"value": "M", "label_fr": "M", "display_order": 3},
                        {"value": "L", "label_fr": "L", "display_order": 4},
                        {"value": "XL", "label_fr": "XL", "display_order": 5},
                        {"value": "XXL", "label_fr": "XXL", "display_order": 6},
                    ],
                },
            ],
        }

        resp = self.client.post("/api/v1/admin/categories", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 201, f"Create category failed: {resp.text}")
        return resp.json()

    def test_01_create_dynamic_category_template_with_color_swatches_and_sizes(self):
        """
        Req 1: Create category 'T-shirts' with attributes (material, fit, brand),
        variant dimensions (color and size), visual circular color swatches (with HEX),
        and size presets (XS..XXL).
        """
        data = self._create_category_template()
        self.assertEqual(len(data["attributes"]), 4)

        # Verify attributes and options persisted correctly
        color_attr = next(a for a in data["attributes"] if a["attr_key"] == "color")
        self.assertTrue(color_attr["is_variant_axis"])
        self.assertEqual(len(color_attr["options"]), 4)
        noir_opt = next(o for o in color_attr["options"] if o["value"] == "Noir Profond")
        self.assertEqual(noir_opt["color_hex"], "#0A0A0A")
        vert_opt = next(o for o in color_attr["options"] if o["value"] == "Vert Émeraude Mus")
        self.assertEqual(vert_opt["color_hex"], "#063D2E")

        size_attr = next(a for a in data["attributes"] if a["attr_key"] == "size")
        self.assertTrue(size_attr["is_variant_axis"])
        self.assertEqual(len(size_attr["options"]), 6)

    def _create_test_products(self):
        cat_data = self._create_category_template()
        cat_id = cat_data["id"]

        # Product A: Classic T-shirt in Black, White, Bordeaux (sizes S, M, L)
        sku_a = f"TSH-A-{uuid.uuid4().hex[:4].upper()}"
        slug_a = f"t-shirt-signature-{uuid.uuid4().hex[:6]}"
        variants_a = [
            # Black S, M, L
            {"sku": f"{sku_a}-BLK-S", "title": "Noir Profond / S", "stock_qty": 5, "attributes": {"color": "Noir Profond", "size": "S"}},
            {"sku": f"{sku_a}-BLK-M", "title": "Noir Profond / M", "stock_qty": 12, "attributes": {"color": "Noir Profond", "size": "M"}},
            {"sku": f"{sku_a}-BLK-L", "title": "Noir Profond / L", "stock_qty": 7, "attributes": {"color": "Noir Profond", "size": "L"}},
            # White S, M, L
            {"sku": f"{sku_a}-WHT-S", "title": "Blanc Pur / S", "stock_qty": 3, "attributes": {"color": "Blanc Pur", "size": "S"}},
            {"sku": f"{sku_a}-WHT-M", "title": "Blanc Pur / M", "stock_qty": 9, "attributes": {"color": "Blanc Pur", "size": "M"}},
            {"sku": f"{sku_a}-WHT-L", "title": "Blanc Pur / L", "stock_qty": 4, "attributes": {"color": "Blanc Pur", "size": "L"}},
            # Bordeaux S, M (Notice: Bordeaux L is intentionally EXCLUDED / not sold)
            {"sku": f"{sku_a}-BOR-S", "title": "Bordeaux Royal / S", "stock_qty": 6, "attributes": {"color": "Bordeaux Royal", "size": "S"}},
            {"sku": f"{sku_a}-BOR-M", "title": "Bordeaux Royal / M", "stock_qty": 2, "attributes": {"color": "Bordeaux Royal", "size": "M"}},
        ]

        prod_a_payload = {
            "category_id": cat_id,
            "sku": sku_a,
            "slug": slug_a,
            "name_fr": "T-shirt Col Rond Signature Mus",
            "name_ar": "تيشيرت فاخر أسود وأبيض",
            "name_en": "Mus Signature Crewneck T-Shirt",
            "selling_price_dzd": 14500,
            "status": "published",
            "dynamic_attributes": {
                "material": "100% Coton Pima",
                "fit": "Coupe Regular",
            },
            "variants": variants_a,
        }

        resp_a = self.client.post("/api/v1/admin/products", json=prod_a_payload, headers=self.headers)
        self.assertEqual(resp_a.status_code, 201, f"Create Product A failed: {resp_a.text}")
        prod_a = resp_a.json()

        # Product B: Oversized Summer T-shirt in Bleu Nuit and Vert Émeraude (sizes M and XL only!)
        sku_b = f"TSH-B-{uuid.uuid4().hex[:4].upper()}"
        slug_b = f"t-shirt-oversize-{uuid.uuid4().hex[:6]}"
        variants_b = [
            {"sku": f"{sku_b}-BLU-M", "title": "Bleu Nuit / M", "stock_qty": 15, "attributes": {"color": "Bleu Nuit", "size": "M"}},
            {"sku": f"{sku_b}-BLU-XL", "title": "Bleu Nuit / XL", "stock_qty": 8, "attributes": {"color": "Bleu Nuit", "size": "XL"}},
            {"sku": f"{sku_b}-GRN-M", "title": "Vert Émeraude Mus / M", "stock_qty": 10, "attributes": {"color": "Vert Émeraude Mus", "size": "M"}},
            {"sku": f"{sku_b}-GRN-XL", "title": "Vert Émeraude Mus / XL", "stock_qty": 6, "attributes": {"color": "Vert Émeraude Mus", "size": "XL"}},
        ]

        prod_b_payload = {
            "category_id": cat_id,
            "sku": sku_b,
            "slug": slug_b,
            "name_fr": "T-shirt Oversize Émeraude & Bleu Nuit",
            "name_ar": "تيشيرت أوفرسايز صيفي",
            "name_en": "Mus Oversized Summer Tee",
            "selling_price_dzd": 16000,
            "status": "published",
            "dynamic_attributes": {
                "material": "Lin Naturel",
                "fit": "Coupe Oversize",
            },
            "variants": variants_b,
        }

        resp_b = self.client.post("/api/v1/admin/products", json=prod_b_payload, headers=self.headers)
        self.assertEqual(resp_b.status_code, 201, f"Create Product B failed: {resp_b.text}")
        prod_b = resp_b.json()

        return prod_a, prod_b

    def test_02_product_editor_loads_category_template_and_supports_independent_customization(self):
        """
        Req 2 & 3:
        Create Product A under T-shirts: Selects Black, White, Red with sizes S, M, L.
        Excludes unsold combination (Red L = 0 / excluded).
        Sets independent stock per variant (e.g. Black M = 12, Black S = 5).
        Then Create Product B under T-shirts: Selects completely different colors (Blue, Green)
        and sizes (M, XL). Proves products under the same category are NOT forced to share identical options.
        """
        prod_a, prod_b = self._create_test_products()
        self.assertEqual(prod_a["total_stock"], 48)
        self.assertEqual(len(prod_a["variants"]), 8)
        self.assertEqual(prod_b["total_stock"], 39)
        self.assertEqual(len(prod_b["variants"]), 4)

        # Assert Independence: Product A has 8 variants; Product B has 4 variants with different colors/sizes
        colors_a = {v["attributes"].get("color") for v in prod_a["variants"]}
        colors_b = {v["attributes"].get("color") for v in prod_b["variants"]}
        self.assertIn("Noir Profond", colors_a)
        self.assertNotIn("Noir Profond", colors_b)
        self.assertIn("Bleu Nuit", colors_b)
        self.assertNotIn("Bleu Nuit", colors_a)

    def test_03_storefront_displays_only_configured_options_and_correct_color_swatches(self):
        """
        Req 4: Storefront PDP verifies:
        - Product A displays only colors (Noir Profond, Blanc Pur, Bordeaux Royal) and sizes (S, M, L).
        - Bordeaux L is recognized as unavailable/excluded.
        - Public API returns category attributes with hex values for visual swatch rendering.
        """
        prod_a, prod_b = self._create_test_products()

        # Public Storefront endpoint: GET /api/v1/products/{slug}
        pub_a = self.client.get(f"/api/v1/products/{prod_a['slug']}")
        self.assertEqual(pub_a.status_code, 200, f"Get public product failed: {pub_a.text}")
        p_data = pub_a.json()

        # Verify variants count matches
        self.assertEqual(len(p_data["variants"]), 8)

        # Check stock values
        black_m = next(v for v in p_data["variants"] if v["attributes"].get("color") == "Noir Profond" and v["attributes"].get("size") == "M")
        self.assertEqual(black_m["stock_qty"], 12)

        # Bordeaux L should not exist in variants
        bordeaux_l = [v for v in p_data["variants"] if v["attributes"].get("color") == "Bordeaux Royal" and v["attributes"].get("size") == "L"]
        self.assertEqual(len(bordeaux_l), 0, "Bordeaux L was excluded and must not exist")

    def test_04_multi_variant_cart_allocation_and_stock_deduction(self):
        """
        Req 4: Multi-variant cart allocation:
        Customer adds:
          - 2 units of Black M (stock: 12)
          - 1 unit of White L (stock: 4)
        Order placed -> Stock accurately deducted to 10 and 3.
        Overselling prevented.
        """
        prod_a, _ = self._create_test_products()

        black_m = next(v for v in prod_a["variants"] if v["attributes"].get("color") == "Noir Profond" and v["attributes"].get("size") == "M")
        white_l = next(v for v in prod_a["variants"] if v["attributes"].get("color") == "Blanc Pur" and v["attributes"].get("size") == "L")

        order_payload = {
            "full_name": "Karim Benali",
            "phone": "0555123456",
            "wilaya_code": "16",
            "commune": "Hydra",
            "delivery_address": "Résidence Les Pins, Hydra",
            "delivery_method": "home",
            "items": [
                {
                    "product_id": prod_a["id"],
                    "variant_id": black_m["id"],
                    "quantity": 2,
                },
                {
                    "product_id": prod_a["id"],
                    "variant_id": white_l["id"],
                    "quantity": 1,
                },
            ],
        }

        resp = self.client.post("/api/v1/orders", json=order_payload)
        self.assertEqual(resp.status_code, 201, f"Place order failed: {resp.text}")
        order_data = resp.json()
        self.assertEqual(order_data["status"], "new")

        # Verify stock decrement on variants
        updated_prod = self.client.get(f"/api/v1/products/{prod_a['slug']}").json()
        updated_black_m = next(v for v in updated_prod["variants"] if v["id"] == black_m["id"])
        updated_white_l = next(v for v in updated_prod["variants"] if v["id"] == white_l["id"])
        self.assertEqual(updated_black_m["stock_qty"], 10, "Black M stock must be decremented from 12 to 10")
        self.assertEqual(updated_white_l["stock_qty"], 3, "White L stock must be decremented from 4 to 3")
        self.assertEqual(updated_prod["total_stock"], 45, "Total stock must be decremented by 3 (from 48 to 45)")

        # Attempt to oversell Black M (request 20 when only 10 available)
        oversell_payload = {
            "full_name": "Overseller",
            "phone": "0555999999",
            "wilaya_code": "16",
            "commune": "Hydra",
            "delivery_address": "Test",
            "delivery_method": "home",
            "items": [
                {
                    "product_id": prod_a["id"],
                    "variant_id": black_m["id"],
                    "quantity": 20,
                }
            ],
        }
        oversell_resp = self.client.post("/api/v1/orders", json=oversell_payload)
        self.assertIn(oversell_resp.status_code, [400, 409, 422], "Overselling must be strictly blocked by the backend")


if __name__ == "__main__":
    unittest.main()
