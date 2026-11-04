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


class TestVariantManagement(unittest.TestCase):
    """Variant CRUD, option library and storefront-facing invariant tests."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        # Every test gets its own category + product so tests never depend on
        # execution order or on mutations performed by a previous test.
        self.suffix = uuid.uuid4().hex[:8]
        self.category_id = self._create_category()
        self.product = self._create_product()

    # ------------------------------------------------------------------ helpers
    def _create_category(self) -> int:
        resp = self.client.post(
            "/api/v1/admin/categories",
            headers=self.headers,
            json={
                "slug": f"variant-test-{self.suffix}",
                "name_fr": f"Test Variantes {self.suffix}",
                "name_ar": "اختبار",
                "name_en": "Variant Test",
                "display_order": 99,
                "is_active": True,
                "show_on_homepage": False,
            },
        )
        assert resp.status_code == 201, resp.text
        category_id = resp.json()["id"]
        for attr_key, label, input_type, options in [
            ("color", "Couleur", "color", ["Noir", "Blanc"]),
            ("size", "Pointure", "size", ["40", "41"]),
        ]:
            r = self.client.post(
                "/api/v1/admin/category-attributes",
                headers=self.headers,
                json={
                    "category_id": category_id,
                    "attr_key": attr_key,
                    "label_fr": label,
                    "input_type": input_type,
                    "is_variant_axis": True,
                    "is_filterable": True,
                    "options": [
                        {"value": v, "label_fr": v, "color_hex": "#111111" if v == "Noir" else "#FAFAFA"}
                        for v in options
                    ],
                },
            )
            assert r.status_code == 201, r.text
        return category_id

    def _create_product(self) -> dict:
        sku = f"VT-{self.suffix.upper()}"
        resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.headers,
            json={
                "category_id": self.category_id,
                "slug": f"variant-product-{self.suffix}",
                "sku": sku,
                "name_fr": f"Produit Variantes {self.suffix}",
                "selling_price_dzd": 5000,
                "purchase_cost_dzd": 2000,
                "status": "published",
                "weight_grams": 900,
                "dimensions_cm": "30x20x10",
                "tags": "test,variantes",
                "variants": [
                    {
                        "sku": f"{sku}-NOIR-40",
                        "title": "Noir / 40",
                        "stock_qty": 5,
                        "attributes": {"color": "Noir", "size": "40"},
                    }
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _find_product(self) -> dict:
        resp = self.client.get(
            f"/api/v1/admin/products?q=VT-{self.suffix.upper()}",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()["items"]
        self.assertTrue(items, "product not found in admin list")
        return items[0]

    def _variant_by_attrs(self, product: dict, attrs: dict) -> dict:
        for variant in product["variants"]:
            if variant["attributes"] == attrs:
                return variant
        self.fail(f"variant {attrs} not found in {[v['attributes'] for v in product['variants']]}")

    def _create_variant(self, attributes: dict, stock_qty: int = 1, **extra) -> dict:
        payload = {"stock_qty": stock_qty, "attributes": attributes, **extra}
        resp = self.client.post(
            f"/api/v1/admin/products/{self.product['id']}/variants",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    # -------------------------------------------------------------------- tests
    def test_01_create_variant_and_reject_duplicates(self):
        created = self._create_variant({"color": "Blanc", "size": "41"}, stock_qty=3)
        self.assertTrue(created["sku"].startswith(f"VT-{self.suffix.upper()}"))
        self.assertEqual(created["attributes"], {"color": "Blanc", "size": "41"})
        self.assertEqual(created["stock_qty"], 3)
        self.assertEqual(created["effective_price_dzd"], 5000)
        self.assertTrue(created["is_active"])

        dup = self.client.post(
            f"/api/v1/admin/products/{self.product['id']}/variants",
            headers=self.headers,
            json={"stock_qty": 1, "attributes": {"color": "Blanc", "size": "41"}},
        )
        self.assertEqual(dup.status_code, 409, dup.text)

        dup_sku = self.client.post(
            f"/api/v1/admin/products/{self.product['id']}/variants",
            headers=self.headers,
            json={"sku": created["sku"], "stock_qty": 1, "attributes": {"color": "Noir", "size": "41"}},
        )
        self.assertEqual(dup_sku.status_code, 409, dup_sku.text)

        unknown_attr = self.client.post(
            f"/api/v1/admin/products/{self.product['id']}/variants",
            headers=self.headers,
            json={"stock_qty": 1, "attributes": {"couleur": "Rouge"}},
        )
        self.assertEqual(unknown_attr.status_code, 422, unknown_attr.text)

        # A custom value is auto-registered in the option library instead of being rejected.
        custom = self._create_variant({"color": "Camel", "size": "41"})
        self.assertEqual(custom["attributes"]["color"], "Camel")
        category = self.client.get(f"/api/v1/categories/variant-test-{self.suffix}")
        color_attr = next(a for a in category.json()["attributes"] if a["attr_key"] == "color")
        self.assertIn("Camel", [o["value"] for o in color_attr["options"]])

    def test_02_update_variant_price_stock_and_attributes(self):
        product = self._find_product()
        variant = self._variant_by_attrs(product, {"color": "Noir", "size": "40"})

        r = self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"price_override_dzd": 4200, "stock_qty": 9, "weight_grams": 850},
        )
        self.assertEqual(r.status_code, 200, r.text)
        updated = r.json()
        self.assertEqual(updated["price_override_dzd"], 4200)
        self.assertEqual(updated["effective_price_dzd"], 4200)
        self.assertEqual(updated["stock_qty"], 9)
        self.assertEqual(updated["weight_grams"], 850)

        movements = self.client.get(
            f"/api/v1/admin/inventory/movements?variant_id={variant['id']}",
            headers=self.headers,
        )
        self.assertEqual(movements.status_code, 200, movements.text)
        reasons = [m["reason"] for m in movements.json()["items"]]
        self.assertIn("variant_edit", reasons)

        negative = self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"price_override_dzd": -10},
        )
        self.assertEqual(negative.status_code, 422, negative.text)

        # Clearing the override falls back to the product price.
        cleared = self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"clear_price_override": True},
        )
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertIsNone(cleared.json()["price_override_dzd"])
        self.assertEqual(cleared.json()["effective_price_dzd"], 5000)

        # Switching attributes recomputes the combination signature.
        moved = self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"attributes": {"color": "Blanc", "size": "40"}},
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["attributes"], {"color": "Blanc", "size": "40"})
        self.assertIn("color:Blanc", moved.json()["combination_signature"])

        # Moving onto an existing combination is refused.
        self._create_variant({"color": "Noir", "size": "41"})
        clash = self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"attributes": {"color": "Noir", "size": "41"}},
        )
        self.assertEqual(clash.status_code, 409, clash.text)

    def test_03_bulk_update_stock_price_and_activation(self):
        second = self._create_variant({"color": "Blanc", "size": "41"}, stock_qty=2)
        product = self._find_product()
        variant_ids = [v["id"] for v in product["variants"]]
        self.assertEqual(len(variant_ids), 2)

        r = self.client.post(
            "/api/v1/admin/variants/bulk-update",
            headers=self.headers,
            json={
                "variant_ids": variant_ids,
                "set_stock_qty": 12,
                "set_price_override_dzd": 3900,
                "is_active": True,
                "reason": "inventaire_mensuel",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["updated_count"], 2)
        self.assertEqual(r.json()["missing_ids"], [])

        refreshed = self._find_product()
        for variant in refreshed["variants"]:
            if variant["id"] in variant_ids:
                self.assertEqual(variant["stock_qty"], 12)
                self.assertEqual(variant["price_override_dzd"], 3900)

        # Relative adjustment respects the floor at zero.
        adjusted = self.client.post(
            "/api/v1/admin/variants/bulk-update",
            headers=self.headers,
            json={"variant_ids": [second["id"]], "adjust_stock_qty": -2},
        )
        self.assertEqual(adjusted.status_code, 200, adjusted.text)
        self.assertEqual(
            self._variant_by_attrs(self._find_product(), {"color": "Blanc", "size": "41"})["stock_qty"], 10
        )

        too_low = self.client.post(
            "/api/v1/admin/variants/bulk-update",
            headers=self.headers,
            json={"variant_ids": variant_ids, "adjust_stock_qty": -999},
        )
        self.assertEqual(too_low.status_code, 400, too_low.text)

        # Clearing overrides falls back to the product price.
        cleared = self.client.post(
            "/api/v1/admin/variants/bulk-update",
            headers=self.headers,
            json={"variant_ids": variant_ids, "clear_price_override": True},
        )
        self.assertEqual(cleared.status_code, 200, cleared.text)
        for variant in self._find_product()["variants"]:
            self.assertIsNone(variant["price_override_dzd"])

        # Unknown ids are reported, not silently ignored.
        missing = self.client.post(
            "/api/v1/admin/variants/bulk-update",
            headers=self.headers,
            json={"variant_ids": [999999], "set_stock_qty": 1},
        )
        self.assertEqual(missing.status_code, 200, missing.text)
        self.assertEqual(missing.json()["missing_ids"], [999999])

    def test_04_variant_option_library_rename_keeps_variants_consistent(self):
        category = self.client.get(f"/api/v1/categories/variant-test-{self.suffix}")
        self.assertEqual(category.status_code, 200, category.text)
        attrs = {a["attr_key"]: a for a in category.json()["attributes"]}
        color_attr = attrs["color"]
        noir_option = next(o for o in color_attr["options"] if o["value"] == "Noir")
        self.assertIn("id", noir_option)

        renamed = self.client.put(
            f"/api/v1/admin/attribute-options/{noir_option['id']}",
            headers=self.headers,
            json={"value": "Noir Mat", "label_fr": "Noir Mat", "color_hex": "#000000", "display_order": 1},
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["value"], "Noir Mat")

        product = self._find_product()
        values = {v["attributes"].get("color") for v in product["variants"]}
        self.assertIn("Noir Mat", values)
        self.assertNotIn("Noir", values)

        # A used option cannot be deleted...
        blocked = self.client.delete(
            f"/api/v1/admin/attribute-options/{noir_option['id']}",
            headers=self.headers,
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)

        # ...but an unused one can.
        fresh = self.client.post(
            f"/api/v1/admin/category-attributes/{color_attr['id']}/options",
            headers=self.headers,
            json={"value": "Bordeaux", "label_fr": "Bordeaux", "color_hex": "#800020"},
        )
        self.assertEqual(fresh.status_code, 201, fresh.text)
        duplicate = self.client.post(
            f"/api/v1/admin/category-attributes/{color_attr['id']}/options",
            headers=self.headers,
            json={"value": "Bordeaux", "label_fr": "Bordeaux"},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        deleted = self.client.delete(
            f"/api/v1/admin/attribute-options/{fresh.json()['id']}",
            headers=self.headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_05_attribute_update_and_category_reorder_and_admin_listing(self):
        category = self.client.get(f"/api/v1/categories/variant-test-{self.suffix}")
        attrs = {a["attr_key"]: a for a in category.json()["attributes"]}
        size_attr = attrs["size"]

        updated = self.client.put(
            f"/api/v1/admin/category-attributes/{size_attr['id']}",
            headers=self.headers,
            json={"label_fr": "Taille (EU)", "is_required": True, "unit": "EU", "display_order": 2},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        updated_attrs = {a["attr_key"]: a for a in updated.json()["attributes"]}
        self.assertEqual(updated_attrs["size"]["label_fr"], "Taille (EU)")
        self.assertTrue(updated_attrs["size"]["is_required"])
        self.assertEqual(updated_attrs["size"]["unit"], "EU")

        invalid_type = self.client.put(
            f"/api/v1/admin/category-attributes/{size_attr['id']}",
            headers=self.headers,
            json={"input_type": "not_a_real_type"},
        )
        self.assertEqual(invalid_type.status_code, 422, invalid_type.text)

        reorder = self.client.put(
            "/api/v1/admin/categories-reorder",
            headers=self.headers,
            json={"items": [{"id": self.category_id, "display_order": 3}]},
        )
        self.assertEqual(reorder.status_code, 200, reorder.text)
        self.assertEqual(reorder.json()["updated_count"], 1)

        admin_list = self.client.get("/api/v1/admin/categories", headers=self.headers)
        self.assertEqual(admin_list.status_code, 200, admin_list.text)
        row = next(c for c in admin_list.json()["items"] if c["id"] == self.category_id)
        self.assertEqual(row["display_order"], 3)

    def test_06_archived_category_visible_in_admin_not_storefront(self):
        resp = self.client.post(
            "/api/v1/admin/categories",
            headers=self.headers,
            json={
                "slug": f"archive-test-{self.suffix}",
                "name_fr": "Archive Test",
                "name_ar": "أرشيف",
                "name_en": "Archive Test",
                "display_order": 98,
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        category_id = resp.json()["id"]

        archived = self.client.delete(
            f"/api/v1/admin/categories/{category_id}", headers=self.headers
        )
        self.assertEqual(archived.status_code, 200, archived.text)

        admin_list = self.client.get("/api/v1/admin/categories?include_archived=true", headers=self.headers)
        ids = [c["id"] for c in admin_list.json()["items"]]
        self.assertIn(category_id, ids)

        active_only = self.client.get("/api/v1/admin/categories?include_archived=false", headers=self.headers)
        self.assertNotIn(category_id, [c["id"] for c in active_only.json()["items"]])

        public = self.client.get("/api/v1/categories")
        self.assertNotIn(category_id, [c["id"] for c in public.json()["items"]])

    def test_07_order_uses_server_variant_price_and_rejects_cross_variant_stock(self):
        product = self._find_product()
        variant = self._variant_by_attrs(product, {"color": "Noir", "size": "40"})
        self.client.put(
            f"/api/v1/admin/variants/{variant['id']}",
            headers=self.headers,
            json={"price_override_dzd": 6100, "stock_qty": 2},
        )

        order = self.client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": f"variant-price-{self.suffix}"},
            json={
                "full_name": "Client Test",
                "phone": "0555112233",
                "wilaya_code": "16",
                "commune": "Alger Centre",
                "delivery_address": "12 Rue des Tests",
                "delivery_method": "home",
                "items": [{"variant_id": variant["id"], "quantity": 2, "client_tampered_price": 1}],
            },
        )
        self.assertEqual(order.status_code, 201, order.text)
        body = order.json()
        self.assertEqual(body["items"][0]["unit_price_dzd"], 6100)
        self.assertEqual(body["subtotal_dzd"], 12200)

        # Stock is now zero: a second order for the same variant must fail.
        exhausted = self.client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": f"variant-price-oos-{self.suffix}"},
            json={
                "full_name": "Client Test",
                "phone": "0555112244",
                "wilaya_code": "16",
                "commune": "Alger Centre",
                "delivery_address": "12 Rue des Tests",
                "delivery_method": "home",
                "items": [{"variant_id": variant["id"], "quantity": 1}],
            },
        )
        self.assertEqual(exhausted.status_code, 409, exhausted.text)

        # A variant referenced by an order is deactivated, never destroyed.
        deleted = self.client.delete(
            f"/api/v1/admin/variants/{variant['id']}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["deactivated"])
        self.assertFalse(deleted.json()["deleted"])

        public = self.client.get(f"/api/v1/products/variant-product-{self.suffix}")
        self.assertEqual(public.status_code, 200, public.text)
        public_ids = [v["id"] for v in public.json()["variants"]]
        self.assertNotIn(variant["id"], public_ids)

    def test_08_unused_variant_is_hard_deleted(self):
        created = self._create_variant({"color": "Blanc", "size": "41"}, stock_qty=1)
        variant_id = created["id"]

        deleted = self.client.delete(f"/api/v1/admin/variants/{variant_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["deleted"])
        self.assertFalse(deleted.json()["deactivated"])

        again = self.client.delete(f"/api/v1/admin/variants/{variant_id}", headers=self.headers)
        self.assertEqual(again.status_code, 404, again.text)

    def test_09_product_metadata_roundtrip(self):
        product = self._find_product()
        r = self.client.put(
            f"/api/v1/admin/products/{product['id']}",
            headers=self.headers,
            json={
                "name_fr": "Produit Variantes Édité",
                "selling_price_dzd": 5200,
                "expected_version": product["version"],
                "barcode": "6130000000012",
                "description_ar": "وصف",
                "weight_grams": 950,
                "dimensions_cm": "31x21x11",
                "tags": "cuir,premium",
                "status": "published",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["name_fr"], "Produit Variantes Édité")
        self.assertEqual(body["barcode"], "6130000000012")
        self.assertEqual(body["weight_grams"], 950)
        self.assertEqual(body["dimensions_cm"], "31x21x11")
        self.assertEqual(body["tags"], "cuir,premium")
        self.assertEqual(body["version"], product["version"] + 1)

        stale = self.client.put(
            f"/api/v1/admin/products/{product['id']}",
            headers=self.headers,
            json={
                "name_fr": "Conflit",
                "selling_price_dzd": 5200,
                "expected_version": product["version"],
            },
        )
        self.assertEqual(stale.status_code, 409, stale.text)


if __name__ == "__main__":
    unittest.main()
