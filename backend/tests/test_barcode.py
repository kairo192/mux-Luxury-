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

from app.main import app, ean_check_digit
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestBarcode(unittest.TestCase):
    """Barcode generation, validation, duplicate prevention, assignment and labels."""

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
        self.suffix = uuid.uuid4().hex[:8]
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]

    def _create_category(self) -> int:
        resp = self.client.post(
            "/api/v1/admin/categories",
            headers=self.headers,
            json={
                "slug": f"bc-test-{self.suffix}",
                "name_fr": f"BC Test {self.suffix}",
                "name_ar": "اختبار",
                "name_en": "BC Test",
                "display_order": 99,
                "is_active": True,
                "show_on_homepage": False,
            },
        )
        assert resp.status_code == 201, resp.text
        cid = resp.json()["id"]
        r = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=self.headers,
            json={
                "category_id": cid,
                "attr_key": "slot",
                "label_fr": "Slot",
                "input_type": "single_select",
                "is_variant_axis": True,
                "options": [{"value": "A", "label_fr": "A"}, {"value": "B", "label_fr": "B"}],
            },
        )
        assert r.status_code == 201, r.text
        return cid

    def _create_product(self) -> dict:
        sku = f"BC-{self.suffix.upper()}"
        resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.headers,
            json={
                "category_id": self.category_id,
                "slug": f"bc-product-{self.suffix}",
                "sku": sku,
                "name_fr": f"Produit BC {self.suffix}",
                "selling_price_dzd": 4200,
                "status": "published",
                "variants": [
                    {"sku": f"{sku}-A", "title": "Slot A", "stock_qty": 5, "attributes": {"slot": "A"}},
                    {"sku": f"{sku}-B", "title": "Slot B", "stock_qty": 2, "price_override_dzd": 7000, "attributes": {"slot": "B"}},
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    # ---------------------------------------------------------------- tests
    def test_01_validate(self):
        ok = self.client.get("/api/v1/admin/barcodes/validate", headers=self.headers, params={"code": "5901234123457"})
        self.assertTrue(ok.json()["valid"])
        self.assertEqual(ok.json()["symbology"], "ean13")
        bad = self.client.get("/api/v1/admin/barcodes/validate", headers=self.headers, params={"code": "5901234123450"})
        self.assertFalse(bad.json()["valid"])
        c128 = self.client.get("/api/v1/admin/barcodes/validate", headers=self.headers, params={"code": "SKU-ABC-9"})
        self.assertTrue(c128.json()["valid"])
        self.assertEqual(c128.json()["symbology"], "code128")

    def test_02_generate_internal_unique_valid(self):
        resp = self.client.post("/api/v1/admin/barcodes/generate", headers=self.headers, json={"count": 5})
        self.assertEqual(resp.status_code, 200, resp.text)
        codes = resp.json()["barcodes"]
        self.assertEqual(len(codes), 5)
        self.assertEqual(len(set(codes)), 5, "generated barcodes must be unique")
        for c in codes:
            self.assertEqual(len(c), 13)
            self.assertTrue(c.startswith("20"), "internal prefix")
            self.assertEqual(ean_check_digit(c[:12]), int(c[12]), "valid EAN-13 check digit")

    def test_03_assign_autogenerate(self):
        resp = self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["internal"])
        self.assertEqual(len(body["barcode"]), 13)
        # POS lookup now resolves the generated barcode
        look = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers, params={"code": body["barcode"]})
        self.assertEqual(look.json()["match_type"], "variant")
        self.assertEqual(look.json()["variant"]["variant_id"], self.variant["id"])

    def test_04_assign_explicit_and_reject_duplicate(self):
        code = "5901234123457"
        r1 = self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={"barcode": code})
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r1.json()["barcode"], code)
        self.assertEqual(r1.json()["symbology"], "ean13")
        # assigning the SAME code to the OTHER variant must conflict
        other = self.product["variants"][1]
        dup = self.client.post(f"/api/v1/admin/variants/{other['id']}/assign-barcode", headers=self.headers, json={"barcode": code})
        self.assertEqual(dup.status_code, 409, dup.text)
        # re-assigning the same code to the SAME variant is allowed (idempotent)
        same = self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={"barcode": code})
        self.assertEqual(same.status_code, 200, same.text)

    def test_05_reject_invalid_check_digit(self):
        bad = self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={"barcode": "5901234123450"})
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_06_clear_barcode(self):
        self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={})
        clr = self.client.delete(f"/api/v1/admin/variants/{self.variant['id']}/barcode", headers=self.headers)
        self.assertEqual(clr.status_code, 200, clr.text)
        self.assertIsNone(clr.json()["barcode"])

    def test_07_label_payload(self):
        self.client.post(f"/api/v1/admin/variants/{self.variant['id']}/assign-barcode", headers=self.headers, json={})
        lab = self.client.get(f"/api/v1/admin/variants/{self.variant['id']}/label", headers=self.headers)
        self.assertEqual(lab.status_code, 200, lab.text)
        d = lab.json()
        self.assertEqual(d["price_dzd"], 4200)  # variant A uses product price
        self.assertEqual(d["symbology"], "ean13")
        self.assertTrue(d["barcode"])
        self.assertEqual(d["sku"], self.variant["sku"])
        # variant B uses its price override
        other = self.product["variants"][1]
        lab2 = self.client.get(f"/api/v1/admin/variants/{other['id']}/label", headers=self.headers)
        self.assertEqual(lab2.json()["price_dzd"], 7000)

    def test_08_unauthorized(self):
        self.assertEqual(
            self.client.post("/api/v1/admin/barcodes/generate", json={"count": 1}).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
