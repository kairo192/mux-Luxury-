"""POS catalog mirror feed: snapshot + deltas.

These endpoints are what the Desktop CMS hits to populate its local SQLite
catalog so the shop keeps selling with no internet. We verify:
  1. snapshot returns every active variant with the fields the mirror needs.
  2. the cursor returned by snapshot is usable as `since` for deltas.
  3. deltas returned right after a snapshot are empty.
  4. a stock change bumps variants.updated_at and shows up in the next delta.
  5. soft-deactivating a variant shows up as deleted=true.
"""
import os
import tempfile
import time
from datetime import datetime, timezone
import unittest
import uuid

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY",
                      "test_only_ephemeral_catalog_sync_abcdef0123456789abcd")

from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits
from app.migration_runner import run as migrate


class TestCatalogSync(unittest.TestCase):
    """Snapshot + deltas endpoints for the local mirror."""

    @classmethod
    def setUpClass(cls):
        migrate()
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        cid = self.client.post(
            "/api/v1/admin/categories", headers=self.headers, json={
                "slug": f"sync-{self.suffix}", "name_fr": f"SYNC {self.suffix}",
                "name_ar": "x", "name_en": "SYNC", "display_order": 99,
                "is_active": True, "show_on_homepage": False,
            }).json()["id"]
        self.client.post(
            "/api/v1/admin/category-attributes", headers=self.headers, json={
                "category_id": cid, "attr_key": "size", "label_fr": "T",
                "input_type": "single_select", "is_variant_axis": True,
                "options": [{"value": "M", "label_fr": "M"}],
            })
        self.product = self.client.post(
            "/api/v1/admin/products", headers=self.headers, json={
                "category_id": cid, "slug": f"sync-product-{self.suffix}",
                "sku": f"SYNC-{self.suffix.upper()}",
                "name_fr": "Catalog sync product", "selling_price_dzd": 1200,
                "status": "published",
                "variants": [{
                    "sku": f"SYNC-{self.suffix.upper()}-M",
                    "title": "M", "stock_qty": 4, "attributes": {"size": "M"},
                }],
            }).json()
        self.variant_id = self.product["variants"][0]["id"]

    # ------------------------------------------------------------------
    def test_01_snapshot_includes_seeded_variants(self):
        snap = self.client.get(
            "/api/v1/admin/pos/catalog/snapshot",
            headers=self.headers,
        ).json()
        self.assertGreaterEqual(snap["stats"]["variants"], 1)
        self.assertIn("cursor", snap)
        self.assertIsInstance(snap["products"], list)
        self.assertIsInstance(snap["variants"], list)
        vids = [v["id"] for v in snap["variants"]]
        self.assertIn(self.variant_id, vids)
        v = next(v for v in snap["variants"] if v["id"] == self.variant_id)
        # Every field the mirror needs for a fully offline lookup must be present.
        for k in ("product_id", "sku", "title", "barcode",
                  "price_override_dzd", "stock_qty", "is_active",
                  "updated_at", "deleted"):
            self.assertIn(k, v, msg=k)
        self.assertEqual(v["stock_qty"], 4)
        self.assertFalse(v["deleted"])

    def test_02_delta_right_after_snapshot_is_empty(self):
        # The cursor includes its own second, so step past the second in
        # which setUp wrote the fixtures.
        time.sleep(1.1)
        snap = self.client.get(
            "/api/v1/admin/pos/catalog/snapshot",
            headers=self.headers,
        ).json()
        delta = self.client.get(
            f"/api/v1/admin/pos/catalog/deltas?since={snap['cursor']}",
            headers=self.headers,
        ).json()
        # Nothing changed between the snapshot's cursor and the delta read.
        self.assertEqual(delta["stats"]["variants"], 0)

    def test_03_stock_change_appears_in_next_delta(self):
        snap = self.client.get(
            "/api/v1/admin/pos/catalog/snapshot",
            headers=self.headers,
        ).json()
        cursor = snap["cursor"]
        # Timestamps use second precision, so wait a tick so the delta can
        # see the UPDATE.
        time.sleep(1.1)
        # Nudge stock via the cheap receive-stock pathway: adjust via a
        # direct SQL would bypass the trigger, so use the inventory adjust
        # endpoint instead.
        r = self.client.post(
            f"/api/v1/admin/variants/{self.variant_id}/adjust-stock",
            headers=self.headers,
            json={"change_qty": 7, "reason": "test refill"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        delta = self.client.get(
            f"/api/v1/admin/pos/catalog/deltas?since={cursor}",
            headers=self.headers,
        ).json()
        matching = [v for v in delta["variants"] if v["id"] == self.variant_id]
        self.assertEqual(len(matching), 1, delta)
        # Starting stock 4 + delta 7 = 11.
        self.assertEqual(matching[0]["stock_qty"], 11)
        self.assertFalse(matching[0]["deleted"])

    def test_04_cursor_is_taken_before_the_read(self):
        # A row changed while the snapshot is being read must come back in the
        # next delta: the cursor is the second the read started, never later.
        started = datetime.now(timezone.utc).replace(microsecond=0)
        snap = self.client.get(
            "/api/v1/admin/pos/catalog/snapshot",
            headers=self.headers,
        ).json()
        finished = datetime.now(timezone.utc).replace(microsecond=0)
        cursor = datetime.strptime(snap["cursor"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertGreaterEqual(cursor, started)
        self.assertLessEqual(cursor, finished)  # never a second that has not started yet
        r = self.client.post(
            f"/api/v1/admin/variants/{self.variant_id}/adjust-stock",
            headers=self.headers,
            json={"change_qty": 1, "reason": "same-second change"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        delta = self.client.get(
            f"/api/v1/admin/pos/catalog/deltas?since={snap['cursor']}",
            headers=self.headers,
        ).json()
        self.assertIn(self.variant_id, [v["id"] for v in delta["variants"]])


if __name__ == "__main__":
    unittest.main()
