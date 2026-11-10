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


class TestPosInvoice(unittest.TestCase):
    """Formal invoice payload for POS sales: legal identifiers + tax breakdown."""

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
        # Configure fiscal identity so the invoice carries NIF/NIS/RC
        self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={
            "settings": {"fiscal_legal_name": "Mus Luxury SARL", "fiscal_nif": "99999", "fiscal_nis": "11111", "fiscal_rc": "16/0001"}
        })
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"inv-{self.suffix}", "name_fr": f"Inv {self.suffix}", "name_ar": "x", "name_en": "Inv",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        p = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"inv-product-{self.suffix}", "sku": f"IN-{self.suffix.upper()}",
            "name_fr": "Inv", "selling_price_dzd": 5000, "status": "published",
            "variants": [{"sku": f"IN-{self.suffix.upper()}-A", "title": "A", "stock_qty": 10, "attributes": {"slot": "A"}}]}).json()
        self.variant_id = p["variants"][0]["id"]
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})

    def tearDown(self):
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

    # ------------------------------------------------------------------ tests
    def test_01_invoice_carries_legal_identity(self):
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant_id, "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 5000}]}).json()
        inv = self.client.get(f"/api/v1/admin/pos/sales/{sale['id']}/invoice", headers=self.headers)
        self.assertEqual(inv.status_code, 200, inv.text)
        b = inv.json()["boutique_info"]
        self.assertEqual(b["nif"], "99999")
        self.assertEqual(b["nis"], "11111")
        self.assertEqual(b["rc"], "16/0001")
        self.assertEqual(inv.json()["document_title"], "Facture")
        self.assertFalse(inv.json()["is_business_invoice"])  # no customer attached

    def test_02_business_invoice_when_customer_attached(self):
        c = self.client.post("/api/v1/admin/customers", headers=self.headers, json={
            "full_name": "SARL Client", "phone": "0555000001"}).json()
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "customer_id": c["id"],
            "items": [{"variant_id": self.variant_id, "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 10000}]}).json()
        inv = self.client.get(f"/api/v1/admin/pos/sales/{sale['id']}/invoice", headers=self.headers).json()
        self.assertTrue(inv["is_business_invoice"])
        self.assertEqual(inv["customer"]["full_name"], "SARL Client")

    def test_03_tax_percent_derived_from_amounts(self):
        # Set a 19% tax rate, make a sale, check derived tax_percent
        self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={"pos_tax_rate_percent": 19})
        try:
            sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
                "items": [{"variant_id": self.variant_id, "quantity": 1}],
                "payments": [{"method": "cash", "amount_dzd": 5950}]}).json()  # 5000 + 950 VAT
            inv = self.client.get(f"/api/v1/admin/pos/sales/{sale['id']}/invoice", headers=self.headers).json()
            self.assertEqual(inv["tax_percent"], 19.0)
        finally:
            self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={"pos_tax_rate_percent": 0})

    def test_04_refund_invoice_is_credit_note(self):
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": self.variant_id, "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 10000}]}).json()
        refund = self.client.post(f"/api/v1/admin/pos/sales/{sale['id']}/refund", headers=self.headers, json={}).json()
        inv = self.client.get(f"/api/v1/admin/pos/sales/{refund['id']}/invoice", headers=self.headers).json()
        self.assertEqual(inv["document_title"], "Avoir (remboursement)")


if __name__ == "__main__":
    unittest.main()
