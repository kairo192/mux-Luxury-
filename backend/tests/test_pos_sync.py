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


class TestPosOfflineSync(unittest.TestCase):
    """Offline batch replay: idempotent, never double-synced, oversell → conflict."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        editor = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@musluxury.dz", "password": "EditorLuxury2026!"})
        cls.editor_headers = {"Authorization": f"Bearer {editor.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:8]
        self.category_id = self._create_category()
        self.product = self._create_product()
        self.variant = self.product["variants"][0]  # stock 5, price 3000

    def _create_category(self) -> int:
        resp = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"sync-{self.suffix}", "name_fr": f"Sync {self.suffix}", "name_ar": "x", "name_en": "Sync",
            "display_order": 99, "is_active": True, "show_on_homepage": False,
        })
        assert resp.status_code == 201, resp.text
        cid = resp.json()["id"]
        r = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": cid, "attr_key": "slot", "label_fr": "Slot", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "A", "label_fr": "A"}],
        })
        assert r.status_code == 201, r.text
        return cid

    def _create_product(self) -> dict:
        sku = f"SY-{self.suffix.upper()}"
        resp = self.client.post("/api/v1/admin/products", headers=self.headers, json={
            "category_id": self.category_id, "slug": f"sync-product-{self.suffix}", "sku": sku,
            "name_fr": f"Sync {self.suffix}", "selling_price_dzd": 3000, "status": "published",
            "variants": [{"sku": f"{sku}-A", "title": "Slot A", "stock_qty": 5, "attributes": {"slot": "A"}}],
        })
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _stock(self) -> int:
        r = self.client.get("/api/v1/admin/pos/lookup", headers=self.headers, params={"code": self.variant["sku"]})
        return r.json()["variant"]["stock_qty"]

    def _op(self, txn: str, qty: int, amount: int):
        return {
            "client_txn_id": txn,
            "type": "sale",
            "created_at_client": "2026-11-07T10:30:00",
            "payload": {
                "items": [{"variant_id": self.variant["id"], "quantity": qty}],
                "payments": [{"method": "cash", "amount_dzd": amount}],
            },
        }

    # ------------------------------------------------------------------ tests
    def test_01_sync_creates_and_deducts(self):
        txn = f"txn-{self.suffix}-1"
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json={"operations": [self._op(txn, 2, 6000)]})
        self.assertEqual(r.status_code, 200, r.text)
        res = r.json()["results"][0]
        self.assertEqual(res["status"], "created")
        self.assertEqual(r.json()["summary"]["created"], 1)
        self.assertEqual(self._stock(), 3)

    def test_02_replay_is_idempotent(self):
        txn = f"txn-{self.suffix}-2"
        batch = {"operations": [self._op(txn, 2, 6000)]}
        first = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json=batch)
        self.assertEqual(first.json()["results"][0]["status"], "created")
        self.assertEqual(self._stock(), 3)
        # Replay the exact same batch — must be a duplicate, no second deduction.
        again = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json=batch)
        self.assertEqual(again.json()["results"][0]["status"], "duplicate")
        self.assertEqual(again.json()["summary"]["duplicate"], 1)
        self.assertEqual(self._stock(), 3)  # unchanged — never synced twice

    def test_03_oversell_is_conflict_not_deducted(self):
        txn = f"txn-{self.suffix}-3"
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json={"operations": [self._op(txn, 99, 297000)]})
        res = r.json()["results"][0]
        self.assertEqual(res["status"], "conflict")
        self.assertEqual(res["reason"], "insufficient_stock")
        self.assertEqual(res["available"], 5)
        self.assertEqual(self._stock(), 5)  # nothing deducted → no oversell

    def test_04_mixed_batch(self):
        done = f"txn-{self.suffix}-ok"
        # Pre-sync one op so it becomes a duplicate in the batch below.
        self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json={"operations": [self._op(done, 1, 3000)]})
        self.assertEqual(self._stock(), 4)
        batch = {"operations": [
            self._op(done, 1, 3000),                      # duplicate
            self._op(f"txn-{self.suffix}-new", 2, 6000),  # created
            self._op(f"txn-{self.suffix}-big", 50, 150000),  # conflict (only 4 left)
        ]}
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json=batch)
        summary = r.json()["summary"]
        self.assertEqual(summary["duplicate"], 1)
        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["conflict"], 1)
        self.assertEqual(self._stock(), 2)  # only the 'created' op (qty 2) deducted

    def test_05_payment_mismatch_conflict(self):
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json={"operations": [self._op(f"txn-{self.suffix}-pm", 1, 2999)]})
        res = r.json()["results"][0]
        self.assertEqual(res["status"], "conflict")
        self.assertEqual(res["reason"], "payment_mismatch")
        self.assertEqual(self._stock(), 5)

    def test_06_no_open_register_required(self):
        # No register opened at all — offline sales are historical facts and still sync.
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.headers, json={"operations": [self._op(f"txn-{self.suffix}-nr", 1, 3000)]})
        self.assertEqual(r.json()["results"][0]["status"], "created")
        self.assertEqual(self._stock(), 4)

    def test_07_permission(self):
        r = self.client.post("/api/v1/admin/pos/sync", headers=self.editor_headers, json={"operations": [self._op("txn-x-perm", 1, 3000)]})
        self.assertEqual(r.status_code, 403, r.text)


if __name__ == "__main__":
    unittest.main()
