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


class TestInventoryCounts(unittest.TestCase):
    """Physical inventory counts: add lines, variance, apply → real movements."""

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
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variants = self.product["variants"]  # 2 variants, stock 10 and 3

    def _create_category(self) -> int:
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"inv-{self.suffix}", "name_fr": f"Inv {self.suffix}", "name_ar": "x", "name_en": "Inv",
            "display_order": 99, "is_active": True, "show_on_homepage": False})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}, {"value": "B", "label_fr": "B"}]})
        return cid

    def _create_product(self) -> dict:
        sku = f"INV-{self.suffix.upper()}"
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"inv-product-{self.suffix}", "sku": sku,
            "name_fr": f"Inv {self.suffix}", "selling_price_dzd": 3000, "status": "published",
            "variants": [
                {"sku": f"{sku}-A", "title": "A", "stock_qty": 10, "attributes": {"slot": "A"}},
                {"sku": f"{sku}-B", "title": "B", "stock_qty": 3, "attributes": {"slot": "B"}},
            ]})
        assert r.status_code == 201, r.text
        return r.json()

    def _stock(self, sku: str) -> int:
        r = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers, params={"code": sku})
        return r.json()["variant"]["stock_qty"]

    def _open(self):
        r = self.client.post("/api/v1/admin/inventory/counts", headers=self.headers, json={"name": f"Compte {self.suffix}"})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    # ------------------------------------------------------------------ tests
    def test_01_open_and_add_line_shows_variance(self):
        cid = self._open()
        va = self.variants[0]  # stock 10
        r = self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": va["id"], "counted_qty": 8})
        self.assertEqual(r.status_code, 200, r.text)
        line = next(l for l in r.json()["items"] if l["variant_id"] == va["id"])
        self.assertEqual(line["expected_qty"], 10)
        self.assertEqual(line["counted_qty"], 8)
        self.assertEqual(line["variance"], -2)
        self.assertEqual(r.json()["total_variance_abs"], 2)

    def test_02_rescan_accumulates_counted(self):
        cid = self._open()
        va = self.variants[0]
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": va["id"], "counted_qty": 3})
        r = self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": va["id"], "counted_qty": 5})
        line = next(l for l in r.json()["items"] if l["variant_id"] == va["id"])
        self.assertEqual(line["counted_qty"], 8)  # 3 + 5

    def test_03_apply_writes_real_movements_and_sets_stock(self):
        cid = self._open()
        va, vb = self.variants
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": va["id"], "counted_qty": 7})  # -3
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": vb["id"], "counted_qty": 5})  # +2
        r = self.client.post(f"/api/v1/admin/inventory/counts/{cid}/apply", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "applied")
        self.assertEqual(self._stock(va["sku"]), 7)
        self.assertEqual(self._stock(vb["sku"]), 5)
        # movements show up with reason physical_count_reconcile
        mv = self.client.get("/api/v1/admin/inventory/movements", headers=self.headers, params={"variant_id": va["id"]})
        self.assertTrue(any(m["reason"] == "physical_count_reconcile" and m["change_qty"] == -3 for m in mv.json()["items"]))

    def test_04_apply_is_idempotent(self):
        cid = self._open()
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": self.variants[0]["id"], "counted_qty": 9})
        self.client.post(f"/api/v1/admin/inventory/counts/{cid}/apply", headers=self.headers)
        again = self.client.post(f"/api/v1/admin/inventory/counts/{cid}/apply", headers=self.headers)
        self.assertEqual(again.status_code, 409, again.text)

    def test_05_apply_recomputes_delta_against_live_stock(self):
        # Count at 10, sell 2 BEFORE applying, apply counted=10 → stock becomes 10 (not 12).
        cid = self._open()
        va = self.variants[0]
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": va["id"], "counted_qty": 10})
        self.client.post("/api/v1/admin/pos/register/open", headers=self.headers, json={"opening_float_dzd": 0})
        self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 6000}],
        })
        self.client.post("/api/v1/admin/pos/register/close", headers=self.headers, json={"counted_cash_dzd": 0})
        self.assertEqual(self._stock(va["sku"]), 8)  # after sale
        self.client.post(f"/api/v1/admin/inventory/counts/{cid}/apply", headers=self.headers)
        self.assertEqual(self._stock(va["sku"]), 10)  # applied to live, becomes exactly counted

    def test_06_cannot_modify_applied(self):
        cid = self._open()
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": self.variants[0]["id"], "counted_qty": 9})
        self.client.post(f"/api/v1/admin/inventory/counts/{cid}/apply", headers=self.headers)
        r = self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": self.variants[1]["id"], "counted_qty": 3})
        self.assertEqual(r.status_code, 409, r.text)

    def test_07_cancel_is_noop_on_stock(self):
        cid = self._open()
        self.client.put(f"/api/v1/admin/inventory/counts/{cid}/lines", headers=self.headers, json={"variant_id": self.variants[0]["id"], "counted_qty": 5})
        r = self.client.post(f"/api/v1/admin/inventory/counts/{cid}/cancel", headers=self.headers)
        self.assertEqual(r.json()["status"], "cancelled")
        self.assertEqual(self._stock(self.variants[0]["sku"]), 10)  # untouched

    def test_08_permission(self):
        # product_manager has products:write but NOT inventory:write
        r = self.client.post("/api/v1/admin/inventory/counts", headers=self.editor_headers, json={})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self.client.get("/api/v1/admin/inventory/counts").status_code, 401)


if __name__ == "__main__":
    unittest.main()
