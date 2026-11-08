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


class TestDeliveryNote(unittest.TestCase):
    """Delivery note (bon de livraison) for online orders: shipping-focused."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        ed = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@musluxury.dz", "password": "EditorLuxury2026!"})
        cls.editor_headers = {"Authorization": f"Bearer {ed.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"dn-{self.suffix}", "name_fr": f"DN {self.suffix}", "name_ar": "x", "name_en": "DN",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        self.product = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"dn-product-{self.suffix}", "sku": f"DN-{self.suffix.upper()}",
            "name_fr": "DN Product", "selling_price_dzd": 4000, "status": "published",
            "variants": [{"sku": f"DN-{self.suffix.upper()}-A", "title": "A", "stock_qty": 10, "attributes": {"slot": "A"}}]}).json()

    def _create_order(self):
        return self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"dn-{self.suffix}"}, json={
            "full_name": "Client Livraison", "phone": "0551234569", "wilaya_code": "09",
            "commune": "Ouled Yaïch", "delivery_address": "Rue 42, Ouled Yaïch", "delivery_method": "home",
            "items": [{"variant_id": self.product["variants"][0]["id"], "quantity": 2}]})

    # ------------------------------------------------------------------ tests
    def test_01_delivery_note_contains_shipping_info(self):
        oid = self._create_order().json()["order_id"]
        r = self.client.get(f"/api/v1/admin/orders/{oid}/delivery-note", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["document_title"], "Bon de livraison")
        self.assertEqual(d["commune"], "Ouled Yaïch")
        self.assertEqual(d["delivery_address"], "Rue 42, Ouled Yaïch")
        self.assertEqual(d["customer_phone"], "0551234569")
        self.assertEqual(d["total_items"], 2)
        self.assertGreater(len(d["items"]), 0)
        # Items carry shipping-relevant fields only (name, variant, SKU, qty)
        for it in d["items"]:
            self.assertIn("quantity", it)
            self.assertIn("sku", it)

    def test_02_cod_amount_populated_for_cod_orders(self):
        order = self._create_order().json()
        r = self.client.get(f"/api/v1/admin/orders/{order['order_id']}/delivery-note", headers=self.headers).json()
        self.assertEqual(r["cod_amount_dzd"], order["total_dzd"])

    def test_03_boutique_info_populated(self):
        oid = self._create_order().json()["order_id"]
        r = self.client.get(f"/api/v1/admin/orders/{oid}/delivery-note", headers=self.headers).json()
        self.assertIn("name", r["boutique_info"])

    def test_04_404(self):
        self.assertEqual(self.client.get("/api/v1/admin/orders/999999/delivery-note", headers=self.headers).status_code, 404)

    def test_05_permission(self):
        oid = self._create_order().json()["order_id"]
        self.assertEqual(self.client.get(f"/api/v1/admin/orders/{oid}/delivery-note", headers=self.editor_headers).status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/admin/orders/{oid}/delivery-note").status_code, 401)


if __name__ == "__main__":
    unittest.main()
