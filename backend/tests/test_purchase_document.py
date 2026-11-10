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


class TestPurchaseOrderDocument(unittest.TestCase):
    """Purchase order printable document: supplier identity, items, totals."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        self.supplier_id = self.client.post("/api/v1/admin/suppliers", headers=self.headers, json={
            "name": f"Supplier {self.suffix}", "contact_person": "Fatima",
            "phone": "+213550000011", "email": f"sup-{self.suffix}@example.com",
            "tax_id": "NIF-XYZ", "address": "Zone industrielle, Alger",
        }).json()
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"pod-{self.suffix}", "name_fr": f"POD {self.suffix}", "name_ar": "x", "name_en": "POD",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        self.product = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"pod-product-{self.suffix}", "sku": f"PO-{self.suffix.upper()}",
            "name_fr": "POD", "selling_price_dzd": 5000, "status": "published",
            "variants": [{"sku": f"PO-{self.suffix.upper()}-A", "title": "A", "stock_qty": 0, "attributes": {"slot": "A"}}]}).json()

    def _create_po(self, qty: int = 5, cost: int = 2000):
        return self.client.post("/api/v1/admin/purchases", headers=self.headers, json={
            "supplier_id": self.supplier_id["id"], "shipping_dzd": 500, "tax_dzd": 0,
            "items": [{"product_id": self.product["id"], "variant_id": self.product["variants"][0]["id"],
                       "quantity": qty, "unit_cost_dzd": cost}],
        })

    # ------------------------------------------------------------------ tests
    def test_01_document_has_supplier_and_items(self):
        po = self._create_po().json()
        r = self.client.get(f"/api/v1/admin/purchases/{po['id']}/document", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["document_title"], "Bon de commande fournisseur")
        self.assertEqual(d["supplier_name"], f"Supplier {self.suffix}")
        self.assertEqual(d["supplier_tax_id"], "NIF-XYZ")
        self.assertEqual(d["total_items_ordered"], 5)
        self.assertEqual(d["total_items_received"], 0)
        self.assertIn("boutique_info", d)
        self.assertEqual(len(d["items"]), 1)

    def test_02_outstanding_matches_total(self):
        po = self._create_po(qty=4, cost=1000).json()
        d = self.client.get(f"/api/v1/admin/purchases/{po['id']}/document", headers=self.headers).json()
        self.assertEqual(d["outstanding_dzd"], d["total_cost_dzd"])
        self.assertEqual(d["paid_amount_dzd"], 0)

    def test_03_after_receive_and_pay(self):
        po = self._create_po().json()
        self.client.post(f"/api/v1/admin/purchases/{po['id']}/receive", headers=self.headers)
        self.client.post(f"/api/v1/admin/purchases/{po['id']}/pay", headers=self.headers)
        d = self.client.get(f"/api/v1/admin/purchases/{po['id']}/document", headers=self.headers).json()
        self.assertEqual(d["total_items_received"], 5)
        self.assertEqual(d["outstanding_dzd"], 0)

    def test_04_404(self):
        self.assertEqual(self.client.get("/api/v1/admin/purchases/999999/document", headers=self.headers).status_code, 404)

    def test_05_anon(self):
        self.assertEqual(self.client.get("/api/v1/admin/purchases/1/document").status_code, 401)


if __name__ == "__main__":
    unittest.main()
