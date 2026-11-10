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


class TestStockWriteOff(unittest.TestCase):
    """Typed stock write-offs: damaged, lost, return_to_supplier, etc."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        ed = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"})
        cls.editor_headers = {"Authorization": f"Bearer {ed.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]  # stock 5

    def _create_category(self) -> int:
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"wo-{self.suffix}", "name_fr": f"WO {self.suffix}", "name_ar": "x", "name_en": "WO",
            "display_order": 99, "is_active": True, "show_on_homepage": False})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}]})
        return cid

    def _create_product(self) -> dict:
        sku = f"WO-{self.suffix.upper()}"
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"wo-product-{self.suffix}", "sku": sku,
            "name_fr": f"WO {self.suffix}", "selling_price_dzd": 3000, "status": "published",
            "variants": [{"sku": f"{sku}-A", "title": "A", "stock_qty": 5, "attributes": {"slot": "A"}}]})
        assert r.status_code == 201, r.text
        return r.json()

    def _stock(self, sku: str) -> int:
        return self.client.get("/api/v1/admin/pos/lookup", headers=self.headers, params={"code": sku}).json()["variant"]["stock_qty"]

    # ------------------------------------------------------------------ tests
    def test_01_reasons_list(self):
        r = self.client.get("/api/v1/admin/inventory/write-off-reasons", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        codes = {it["code"] for it in r.json()["items"]}
        self.assertIn("damaged", codes)
        self.assertIn("return_to_supplier", codes)

    def test_02_damage_deducts_and_records_movement(self):
        r = self.client.post("/api/v1/admin/inventory/write-off", headers=self.headers, json={
            "variant_id": self.variant["id"], "quantity": 2, "reason": "damaged"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["new_qty"], 3)
        self.assertEqual(self._stock(self.variant["sku"]), 3)
        mv = self.client.get("/api/v1/admin/inventory/movements", headers=self.headers, params={"variant_id": self.variant["id"]})
        self.assertTrue(any(m["reason"] == "writeoff_damaged" and m["change_qty"] == -2 for m in mv.json()["items"]))

    def test_03_oversell_rejected(self):
        r = self.client.post("/api/v1/admin/inventory/write-off", headers=self.headers, json={
            "variant_id": self.variant["id"], "quantity": 99, "reason": "lost"})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(self._stock(self.variant["sku"]), 5)  # untouched

    def test_04_invalid_reason(self):
        r = self.client.post("/api/v1/admin/inventory/write-off", headers=self.headers, json={
            "variant_id": self.variant["id"], "quantity": 1, "reason": "stolen_by_aliens"})
        self.assertEqual(r.status_code, 422, r.text)

    def test_05_each_reason_distinct_in_ledger(self):
        for reason, qty in [("damaged", 1), ("lost", 1), ("promotional_giveaway", 1)]:
            self.client.post("/api/v1/admin/inventory/write-off", headers=self.headers, json={
                "variant_id": self.variant["id"], "quantity": qty, "reason": reason})
        mv = self.client.get("/api/v1/admin/inventory/movements", headers=self.headers, params={"variant_id": self.variant["id"]})
        reasons = {m["reason"] for m in mv.json()["items"]}
        self.assertTrue({"writeoff_damaged", "writeoff_lost", "writeoff_promotional_giveaway"}.issubset(reasons))

    def test_06_permissions(self):
        # product_manager has products:write but NOT inventory:write
        r = self.client.post("/api/v1/admin/inventory/write-off", headers=self.editor_headers, json={
            "variant_id": self.variant["id"], "quantity": 1, "reason": "damaged"})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self.client.post("/api/v1/admin/inventory/write-off", json={"variant_id": 1, "quantity": 1, "reason": "damaged"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
