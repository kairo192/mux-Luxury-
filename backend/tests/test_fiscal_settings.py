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


class TestFiscalSettings(unittest.TestCase):
    """Configurable fiscal settings: tax, legal identity, receipt prefixes."""

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

    def tearDown(self):
        # The DB is shared across the whole suite: never leak a non-zero POS tax
        # rate into later POS/sync/report tests that pay exactly the item price.
        self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={"pos_tax_rate_percent": 0})

    # ------------------------------------------------------------------ tests
    def test_01_defaults_returned(self):
        r = self.client.get("/api/v1/admin/fiscal/settings", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("fiscal_legal_name", d)
        self.assertIn("pos_tax_rate_percent", d)
        self.assertEqual(d["pos_tax_rate_percent"], 0)

    def test_02_update_tax_and_identity(self):
        r = self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={
            "pos_tax_rate_percent": 19,
            "settings": {
                "fiscal_legal_name": "Mus Luxury SARL",
                "fiscal_nif": "1234567890123",
                "fiscal_nis": "987654321",
                "fiscal_rc": "16/00-0001234 B",
            },
        })
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["pos_tax_rate_percent"], 19)
        self.assertEqual(d["fiscal_legal_name"], "Mus Luxury SARL")
        self.assertEqual(d["fiscal_nif"], "1234567890123")

    def test_03_unknown_key_rejected(self):
        r = self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={
            "settings": {"session_revoked_ns:1": "9999999"}})
        self.assertEqual(r.status_code, 422, r.text)

    def test_04_tax_rate_range(self):
        r = self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={"pos_tax_rate_percent": 150})
        self.assertEqual(r.status_code, 422)
        r = self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={"pos_tax_rate_percent": -5})
        self.assertEqual(r.status_code, 422)

    def test_05_pos_receipt_reflects_configured_identity(self):
        # Set the legal name & NIF, then make a tiny POS sale and inspect the receipt
        self.client.put("/api/v1/admin/fiscal/settings", headers=self.headers, json={
            "settings": {"fiscal_commercial_name": f"Mus Luxury Boutique {self.suffix}", "fiscal_nif": "99999"}})
        # minimal product + variant
        cid = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"fs-{self.suffix}", "name_fr": f"FS {self.suffix}", "name_ar": "x", "name_en": "FS",
            "display_order": 99, "is_active": True, "show_on_homepage": False}).json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        p = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": cid, "slug": f"fs-product-{self.suffix}", "sku": f"FS-{self.suffix.upper()}",
            "name_fr": "FS", "selling_price_dzd": 3000, "status": "published",
            "variants": [{"sku": f"FS-{self.suffix.upper()}-A", "title": "A", "stock_qty": 5, "attributes": {"slot": "A"}}]}).json()
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": p["variants"][0]["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 3000}]}).json()
        self.assertEqual(sale["boutique_info"]["name"], f"Mus Luxury Boutique {self.suffix}")
        self.assertEqual(sale["boutique_info"]["nif"], "99999")
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})

    def test_06_permissions(self):
        # Writing requires settings:write
        self.assertEqual(self.client.put("/api/v1/admin/fiscal/settings", headers=self.editor_headers, json={"pos_tax_rate_percent": 5}).status_code, 403)
        # Reading is allowed to dashboard:read holders (editor is product_manager with dashboard:read)
        r = self.client.get("/api/v1/admin/fiscal/settings", headers=self.editor_headers)
        self.assertEqual(r.status_code, 200)
        # Anon rejected
        self.assertEqual(self.client.get("/api/v1/admin/fiscal/settings").status_code, 401)


if __name__ == "__main__":
    unittest.main()
