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


class TestSuppliers(unittest.TestCase):
    """Supplier management: list with aggregates + per-supplier detail."""

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
        # Create a supplier + a product so we can build a purchase order
        self.supplier_id = self.client.post("/api/v1/admin/suppliers", headers=self.headers, json={
            "name": f"Fournisseur {self.suffix}",
            "contact_person": "Ahmed",
            "phone": "+213550000001",
            "email": "sup@example.com",
            "tax_id": "NIF-1234",
        }).json()["id"]
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"sup-{self.suffix}", "name_fr": f"Sup {self.suffix}", "name_ar": "x", "name_en": "Sup",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        p = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"sup-product-{self.suffix}", "sku": f"SU-{self.suffix.upper()}",
            "name_fr": "Sup", "selling_price_dzd": 5000, "purchase_cost_dzd": 3000, "status": "published",
            "variants": [{"sku": f"SU-{self.suffix.upper()}-A", "title": "A", "stock_qty": 0, "attributes": {"slot": "A"}}]})
        self.product_id = p.json()["id"]
        self.variant_id = p.json()["variants"][0]["id"]

    def _create_po(self, qty: int, unit_cost: int, shipping: int = 0):
        return self.client.post("/api/v1/admin/purchases", headers=self.headers, json={
            "supplier_id": self.supplier_id,
            "shipping_dzd": shipping,
            "tax_dzd": 0,
            "items": [{"product_id": self.product_id, "variant_id": self.variant_id, "quantity": qty, "unit_cost_dzd": unit_cost}],
        })

    # ------------------------------------------------------------------ tests
    def test_01_list_includes_aggregates(self):
        r = self.client.get("/api/v1/admin/suppliers", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mine = next(s for s in r.json()["items"] if s["id"] == self.supplier_id)
        self.assertIn("purchase_orders_count", mine)
        self.assertIn("outstanding_dzd", mine)
        self.assertEqual(mine["purchase_orders_count"], 0)
        self.assertEqual(mine["outstanding_dzd"], 0)

    def test_02_po_lifts_total_and_outstanding(self):
        po = self._create_po(5, 3000)
        self.assertEqual(po.status_code, 201, po.text)
        po_id = po.json()["id"]
        # Receive the PO to leave 'draft' state
        rec = self.client.post(f"/api/v1/admin/purchases/{po_id}/receive", headers=self.headers)
        self.assertEqual(rec.status_code, 200, rec.text)

        detail = self.client.get(f"/api/v1/admin/suppliers/{self.supplier_id}", headers=self.headers).json()
        self.assertEqual(detail["stats"]["purchase_orders_count"], 1)
        self.assertEqual(detail["stats"]["total_purchased_dzd"], 15000)  # 5 * 3000
        self.assertEqual(detail["stats"]["total_paid_dzd"], 0)
        self.assertEqual(detail["stats"]["outstanding_dzd"], 15000)
        self.assertEqual(len(detail["recent_purchase_orders"]), 1)

        # After paying the PO, outstanding goes back to zero
        self.client.post(f"/api/v1/admin/purchases/{po_id}/pay", headers=self.headers)
        detail2 = self.client.get(f"/api/v1/admin/suppliers/{self.supplier_id}", headers=self.headers).json()
        self.assertEqual(detail2["stats"]["outstanding_dzd"], 0)
        self.assertEqual(detail2["stats"]["total_paid_dzd"], 15000)

    def test_03_detail_404(self):
        self.assertEqual(self.client.get("/api/v1/admin/suppliers/999999", headers=self.headers).status_code, 404)

    def test_04_anon_rejected(self):
        self.assertEqual(self.client.get("/api/v1/admin/suppliers").status_code, 401)
        self.assertEqual(self.client.get(f"/api/v1/admin/suppliers/{self.supplier_id}").status_code, 401)


if __name__ == "__main__":
    unittest.main()
