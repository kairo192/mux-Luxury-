"""End-to-end proof that the label-print → scan loop closes.

The POS workflow depends on a round-trip:
  1. The Desktop CMS assigns a barcode to a product variant.
  2. The label printer prints a sticky label with that barcode.
  3. A cashier scans the label at the register.
  4. /api/v1/admin/pos/lookup resolves the barcode back to the variant.
  5. The variant is added to the cart and the sale completes.

Everything server-side (steps 1 and 4) is covered here; the hardware
layers (2 and 3) have their own Rust/ESC-POS/ZPL unit tests.
"""
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
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_barcode_loop_tests_1234567890abcd")

from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestBarcodeScanLoop(unittest.TestCase):
    """Label-print → scan-at-register round trip, server-side portion."""

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

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]

        cid = self.client.post(
            "/api/v1/admin/categories", headers=self.headers, json={
                "slug": f"bar-{self.suffix}", "name_fr": f"BAR {self.suffix}",
                "name_ar": "x", "name_en": "BAR", "display_order": 99,
                "is_active": True, "show_on_homepage": False,
            }).json()["id"]
        self.client.post(
            "/api/v1/admin/category-attributes", headers=self.headers, json={
                "category_id": cid, "attr_key": "size", "label_fr": "Taille",
                "input_type": "single_select", "is_variant_axis": True,
                "options": [{"value": "M", "label_fr": "M"}],
            })
        self.product = self.client.post(
            "/api/v1/admin/products", headers=self.headers, json={
                "category_id": cid, "slug": f"bar-product-{self.suffix}",
                "sku": f"BAR-{self.suffix.upper()}",
                "name_fr": "Barcode product", "selling_price_dzd": 2500,
                "status": "published",
                "variants": [{
                    "sku": f"BAR-{self.suffix.upper()}-M",
                    "title": "M", "stock_qty": 10, "attributes": {"size": "M"},
                }],
            }).json()
        self.variant_id = self.product["variants"][0]["id"]

    # ------------------------------------------------------------------
    def _assign(self, code=None):
        payload = {"barcode": code} if code else {}
        r = self.client.post(
            f"/api/v1/admin/variants/{self.variant_id}/assign-barcode",
            headers=self.headers, json=payload,
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ------------------------------------------------------------------ tests
    def test_01_internal_barcode_round_trip(self):
        """Generate an internal barcode, then look it up as if scanned."""
        info = self._assign()  # auto-generates
        self.assertTrue(info.get("barcode"), info)
        code = info["barcode"]
        lookup = self.client.get(
            f"/api/v1/admin/pos/lookup?code={code}",
            headers=self.headers,
        ).json()
        self.assertEqual(lookup["match_type"], "variant")
        self.assertEqual(lookup["variant"]["variant_id"], self.variant_id)
        self.assertEqual(lookup["variant"]["unit_price_dzd"], 2500)

    @staticmethod
    def _ean13_check_digit(twelve_digits: str) -> int:
        total = 0
        for i, ch in enumerate(twelve_digits):
            d = int(ch)
            total += d if i % 2 == 0 else 3 * d
        return (10 - (total % 10)) % 10

    def test_02_custom_ean13_round_trip(self):
        """A pasted real EAN-13 is accepted and resolves back to the variant."""
        twelve = "620987654321"  # 12 digits; test range (6)
        ean = twelve + str(self._ean13_check_digit(twelve))
        valid = self.client.get(
            f"/api/v1/admin/barcodes/validate?code={ean}",
            headers=self.headers,
        ).json()
        self.assertTrue(valid.get("valid"), f"fixture EAN-13 invalid: {valid}")
        self._assign(ean)
        lookup = self.client.get(
            f"/api/v1/admin/pos/lookup?code={ean}",
            headers=self.headers,
        ).json()
        self.assertEqual(lookup["match_type"], "variant")
        self.assertEqual(lookup["variant"]["barcode"], ean)
        self.assertEqual(lookup["variant"]["variant_id"], self.variant_id)

    def test_03_scan_leads_to_sale(self):
        """The resolved variant can be added to a POS sale in the same call."""
        info = self._assign()
        code = info["barcode"]
        # Open a register so the sale endpoint accepts us.
        self.client.post(
            "/api/v1/admin/pos/register/open",
            headers=self.headers,
            json={"register_name": "Main", "opening_float_dzd": 0},
        )
        # Scan simulation.
        lookup = self.client.get(
            f"/api/v1/admin/pos/lookup?code={code}",
            headers=self.headers,
        ).json()
        variant = lookup["variant"]
        # Sell it.
        sale = self.client.post(
            "/api/v1/admin/pos/sales",
            headers={**self.headers, "Idempotency-Key": f"test-{self.suffix}"},
            json={
                "items": [{"variant_id": variant["variant_id"], "quantity": 1}],
                "payments": [{"method": "cash", "amount_dzd": variant["unit_price_dzd"]}],
            },
        )
        self.assertEqual(sale.status_code, 201, sale.text)
        self.assertEqual(sale.json()["total_dzd"], variant["unit_price_dzd"])

    def test_04_unknown_scan_returns_search(self):
        """A scan of a code no one assigned returns search (not 404)."""
        lookup = self.client.get(
            "/api/v1/admin/pos/lookup?code=ZZZZZZZZZZZZZ",
            headers=self.headers,
        ).json()
        self.assertIn(lookup["match_type"], ("search", "none"))
        # Importantly: not an exception, so the UI can show "no match" cleanly.

    def test_05_po_labels_batch_matches_received_quantities(self):
        """After a PO is receipted, /purchases/{id}/labels returns one entry
        per variant with copies = quantity received. This is what the Desktop
        CMS pipes straight into the native label printer."""
        info = self._assign()  # make sure the variant has a barcode
        self.assertTrue(info["barcode"])

        # Need a supplier for the PO.
        sup = self.client.post(
            "/api/v1/admin/suppliers", headers=self.headers, json={
                "name": f"Fournisseur {self.suffix}", "phone": "+213550000012",
            }).json()
        po = self.client.post(
            "/api/v1/admin/purchases", headers=self.headers, json={
                "supplier_id": sup["id"], "shipping_dzd": 0, "tax_dzd": 0,
                "items": [{
                    "product_id": self.product["id"],
                    "variant_id": self.variant_id,
                    "quantity": 7, "unit_cost_dzd": 1000,
                }],
            }).json()
        self.client.post(
            f"/api/v1/admin/purchases/{po['id']}/receive",
            headers=self.headers,
        )
        batch = self.client.get(
            f"/api/v1/admin/purchases/{po['id']}/labels",
            headers=self.headers,
        ).json()
        self.assertEqual(batch["total_copies"], 7)
        self.assertEqual(len(batch["labels"]), 1)
        label = batch["labels"][0]
        self.assertEqual(label["copies"], 7)
        self.assertEqual(label["sku"], f"BAR-{self.suffix.upper()}-M")
        self.assertEqual(label["variant_id"], self.variant_id)
        self.assertFalse(label["needs_barcode"])
        self.assertEqual(batch["variants_without_barcode"], 0)

    def test_06_po_labels_flag_variants_without_barcode(self):
        """A received PO on a variant without a barcode is included in the
        response but flagged, so the UI can prompt to assign one before printing."""
        # No _assign() call this time — variant has no barcode.
        sup = self.client.post(
            "/api/v1/admin/suppliers", headers=self.headers, json={
                "name": f"Fournisseur {self.suffix}", "phone": "+213550000013",
            }).json()
        po = self.client.post(
            "/api/v1/admin/purchases", headers=self.headers, json={
                "supplier_id": sup["id"], "shipping_dzd": 0, "tax_dzd": 0,
                "items": [{
                    "product_id": self.product["id"],
                    "variant_id": self.variant_id,
                    "quantity": 3, "unit_cost_dzd": 900,
                }],
            }).json()
        self.client.post(
            f"/api/v1/admin/purchases/{po['id']}/receive", headers=self.headers,
        )
        batch = self.client.get(
            f"/api/v1/admin/purchases/{po['id']}/labels",
            headers=self.headers,
        ).json()
        self.assertEqual(batch["variants_without_barcode"], 1)
        self.assertEqual(batch["labels"][0]["needs_barcode"], True)
        self.assertEqual(batch["labels"][0]["barcode_value"], "")


if __name__ == "__main__":
    unittest.main()
