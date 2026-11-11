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


class TestPointOfSale(unittest.TestCase):
    """POS: cash register sessions, barcode lookup, sales, idempotency and refunds."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        # product_manager account: has products:write but NOT pos:sell / pos:refund
        editor = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"},
        )
        assert editor.status_code == 200, editor.text
        cls.editor_headers = {"Authorization": f"Bearer {editor.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:8]
        self._ensure_register_closed()
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variants = {v["attributes"]["slot"]: v for v in self.product["variants"]}

    def tearDown(self):
        self._ensure_register_closed()

    # ------------------------------------------------------------------ helpers
    def _ensure_register_closed(self):
        cur = self.client.get("/api/v1/admin/pos/register/current", headers=self.headers)
        if cur.status_code == 200 and cur.json().get("open"):
            self.client.post(
                "/api/v1/admin/pos/register/close",
                headers=self.headers,
                json={"counted_cash_dzd": 0},
            )

    def _create_category(self) -> int:
        resp = self.client.post(
            "/api/v1/admin/categories",
            headers=self.headers,
            json={
                "slug": f"pos-test-{self.suffix}",
                "name_fr": f"POS Test {self.suffix}",
                "name_ar": "اختبار",
                "name_en": "POS Test",
                "display_order": 99,
                "is_active": True,
                "show_on_homepage": False,
            },
        )
        assert resp.status_code == 201, resp.text
        category_id = resp.json()["id"]
        r = self.client.post(
            "/api/v1/admin/category-attributes",
            headers=self.headers,
            json={
                "category_id": category_id,
                "attr_key": "slot",
                "label_fr": "Slot",
                "input_type": "single_select",
                "is_variant_axis": True,
                "options": [
                    {"value": "A", "label_fr": "A"},
                    {"value": "B", "label_fr": "B"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        return category_id

    def _create_product(self) -> dict:
        sku = f"POS-{self.suffix.upper()}"
        resp = self.client.post(
            "/api/v1/admin/products",
            headers=self.headers,
            json={
                "category_id": self.category_id,
                "slug": f"pos-product-{self.suffix}",
                "sku": sku,
                "name_fr": f"Produit POS {self.suffix}",
                "selling_price_dzd": 5000,
                "purchase_cost_dzd": 2000,
                "status": "published",
                "variants": [
                    {
                        "sku": f"{sku}-A",
                        "barcode": f"BC-{self.suffix}-A",
                        "title": "Slot A",
                        "stock_qty": 5,
                        "price_override_dzd": 3000,
                        "attributes": {"slot": "A"},
                    },
                    {
                        "sku": f"{sku}-B",
                        "barcode": f"BC-{self.suffix}-B",
                        "title": "Slot B",
                        "stock_qty": 3,
                        "attributes": {"slot": "B"},
                    },
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _open_register(self, opening=10000):
        resp = self.client.post(
            "/api/v1/admin/pos/register/open",
            headers=self.headers,
            json={"opening_float_dzd": opening},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _stock_by_sku(self, sku: str) -> int:
        resp = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers, params={"code": sku})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["match_type"], "variant", body)
        return body["variant"]["stock_qty"]

    # -------------------------------------------------------------------- tests
    def test_01_register_open_close_variance(self):
        self._open_register(opening=10000)
        cur = self.client.get("/api/v1/admin/pos/register/current", headers=self.headers)
        self.assertTrue(cur.json()["open"])
        self.assertEqual(cur.json()["session"]["expected_cash_dzd"], 10000)
        # second open rejected
        dup = self.client.post("/api/v1/admin/pos/register/open", headers=self.headers,
                               json={"opening_float_dzd": 0})
        self.assertEqual(dup.status_code, 409, dup.text)
        # close with an over-count → positive variance
        close = self.client.post("/api/v1/admin/pos/register/close", headers=self.headers,
                                 json={"counted_cash_dzd": 10500})
        self.assertEqual(close.status_code, 200, close.text)
        self.assertEqual(close.json()["expected_cash_dzd"], 10000)
        self.assertEqual(close.json()["variance_dzd"], 500)
        self.assertEqual(close.json()["status"], "closed")

    def test_02_lookup_by_barcode_and_sku(self):
        r = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers,
                            params={"code": f"BC-{self.suffix}-A"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["match_type"], "variant")
        self.assertEqual(r.json()["variant"]["unit_price_dzd"], 3000)  # price override wins
        self.assertEqual(r.json()["variant"]["stock_qty"], 5)
        # by variant SKU
        r2 = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers,
                             params={"code": f"POS-{self.suffix.upper()}-B"})
        self.assertEqual(r2.json()["match_type"], "variant")
        self.assertEqual(r2.json()["variant"]["unit_price_dzd"], 5000)  # falls back to product price
        # unknown code
        r3 = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers,
                             params={"code": "NONE-XYZ-000"})
        self.assertEqual(r3.json()["match_type"], "none")

    def test_03_sale_requires_open_register(self):
        va = self.variants["A"]
        resp = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 3000}],
        })
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertIn("caisse", resp.json()["detail"].lower())

    def test_04_cash_sale_deducts_stock_and_change(self):
        self._open_register()
        va = self.variants["A"]
        resp = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 2}],
            "payments": [{"method": "cash", "amount_dzd": 6000, "tendered_dzd": 10000}],
        })
        self.assertEqual(resp.status_code, 201, resp.text)
        sale = resp.json()
        self.assertEqual(sale["total_dzd"], 6000)
        self.assertEqual(sale["payments"][0]["change_dzd"], 4000)
        self.assertEqual(sale["sale_type"], "sale")
        self.assertEqual(self._stock_by_sku(va["sku"]), 3)
        # register reflects the cash
        cur = self.client.get("/api/v1/admin/pos/register/current", headers=self.headers)
        self.assertEqual(cur.json()["session"]["sales_total_dzd"], 6000)
        self.assertEqual(cur.json()["session"]["expected_cash_dzd"], 16000)

    def test_05_idempotent_sale_not_double_charged(self):
        self._open_register()
        va = self.variants["A"]
        body = {
            "items": [{"variant_id": va["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 3000}],
        }
        h = {**self.headers, "Idempotency-Key": f"idem-{self.suffix}"}
        r1 = self.client.post("/api/v1/admin/pos/sales", headers=h, json=body)
        r2 = self.client.post("/api/v1/admin/pos/sales", headers=h, json=body)
        self.assertEqual(r1.status_code, 201, r1.text)
        self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(r1.json()["id"], r2.json()["id"])  # same sale returned
        self.assertEqual(self._stock_by_sku(va["sku"]), 4)  # deducted exactly once

    def test_06_insufficient_stock_and_payment_mismatch(self):
        self._open_register()
        va = self.variants["A"]
        over = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 99}],
            "payments": [{"method": "cash", "amount_dzd": 297000}],
        })
        self.assertEqual(over.status_code, 409, over.text)
        mism = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 2999}],
        })
        self.assertEqual(mism.status_code, 422, mism.text)
        self.assertEqual(self._stock_by_sku(va["sku"]), 5)  # nothing deducted

    def test_07_partial_then_full_refund_restocks(self):
        self._open_register()
        va = self.variants["A"]
        sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 3}],
            "payments": [{"method": "cash", "amount_dzd": 9000}],
        }).json()
        self.assertEqual(self._stock_by_sku(va["sku"]), 2)
        # partial refund of 1
        r1 = self.client.post(f"/api/v1/admin/pos/sales/{sale['id']}/refund", headers=self.headers, json={
            "items": [{"variant_id": va["id"], "quantity": 1}],
        })
        self.assertEqual(r1.status_code, 201, r1.text)
        self.assertEqual(r1.json()["sale_type"], "refund")
        self.assertEqual(r1.json()["total_dzd"], 3000)
        self.assertEqual(self._stock_by_sku(va["sku"]), 3)
        detail = self.client.get(f"/api/v1/admin/pos/sales/{sale['id']}", headers=self.headers)
        self.assertEqual(detail.json()["status"], "partially_refunded")
        # refund the rest (no items → all remaining)
        r2 = self.client.post(f"/api/v1/admin/pos/sales/{sale['id']}/refund", headers=self.headers, json={})
        self.assertEqual(r2.status_code, 201, r2.text)
        self.assertEqual(self._stock_by_sku(va["sku"]), 5)
        detail2 = self.client.get(f"/api/v1/admin/pos/sales/{sale['id']}", headers=self.headers)
        self.assertEqual(detail2.json()["status"], "refunded")
        # over-refund rejected
        r3 = self.client.post(f"/api/v1/admin/pos/sales/{sale['id']}/refund", headers=self.headers, json={})
        self.assertEqual(r3.status_code, 409, r3.text)

    def test_08_permissions_enforced(self):
        self._open_register()
        va = self.variants["A"]
        # product_manager lacks pos:sell
        resp = self.client.post("/api/v1/admin/pos/sales", headers=self.editor_headers, json={
            "items": [{"variant_id": va["id"], "quantity": 1}],
            "payments": [{"method": "cash", "amount_dzd": 3000}],
        })
        self.assertEqual(resp.status_code, 403, resp.text)
        # and cannot open/close the register
        self.assertEqual(
            self.client.post("/api/v1/admin/pos/register/open", headers=self.editor_headers,
                             json={"opening_float_dzd": 0}).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
