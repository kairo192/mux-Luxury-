"""Regression tests for the fixes made after the code review of the router split:
private costs, barcodes, archive/restore, hidden categories, register replay,
refund tax, expense ledger, settings bounds."""
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

from app.database import db_session
from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestReviewFixes(unittest.TestCase):
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
        self.suffix = uuid.uuid4().hex[:8]
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"review-{self.suffix}", "name_fr": f"Revue {self.suffix}", "name_ar": "مراجعة",
            "name_en": "Review", "display_order": 99, "is_active": True, "show_on_homepage": False,
        })
        self.assertEqual(r.status_code, 201, r.text)
        self.category_id = r.json()["id"]
        r = self.client.post("/api/v1/admin/category-attributes", headers=self.headers, json={
            "category_id": self.category_id, "attr_key": "color", "label_fr": "Couleur", "input_type": "color",
            "is_variant_axis": True, "is_filterable": True,
            "options": [{"value": v, "label_fr": v} for v in ("Noir", "Blanc")],
        })
        self.assertEqual(r.status_code, 201, r.text)

    # ------------------------------------------------------------------ helpers
    def _product(self, *, barcode=None, variants=None, tag="P"):
        sku = f"RV-{tag}-{self.suffix.upper()}"
        variants = variants or [{"color": "Noir"}]
        payload = {
            "category_id": self.category_id, "slug": f"review-{tag.lower()}-{self.suffix}", "sku": sku,
            "name_fr": f"Revue {tag} {self.suffix}", "selling_price_dzd": 5000, "purchase_cost_dzd": 2000,
            "status": "published", "barcode": barcode,
            "variants": [
                {"sku": f"{sku}-{i}", "title": v["color"], "stock_qty": 5, "attributes": {"color": v["color"]},
                 "purchase_cost_dzd": 2500, "barcode": v.get("barcode")}
                for i, v in enumerate(variants)
            ],
        }
        r = self.client.post("/api/v1/admin/products", headers=self.headers, json=payload)
        return r

    def _ok_product(self, **kw):
        r = self._product(**kw)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    # ------------------------------------------------------------------ tests
    def test_public_catalogue_hides_variant_purchase_cost(self):
        prod = self._ok_product()
        public = self.client.get(f"/api/v1/products/{prod['slug']}")
        self.assertEqual(public.status_code, 200, public.text)
        body = public.json()
        self.assertNotIn("purchase_cost_dzd", body)
        for v in body["variants"]:
            self.assertNotIn("purchase_cost_dzd", v)
        admin = self.client.get(f"/api/v1/admin/products?q={prod['sku']}", headers=self.headers).json()["items"][0]
        self.assertEqual(admin["variants"][0]["purchase_cost_dzd"], 2500)

    def test_barcode_cannot_be_reused_on_another_article(self):
        code = f"RV{self.suffix.upper()}"
        self._ok_product(tag="A", variants=[{"color": "Noir", "barcode": code}])
        dup = self._product(tag="B", variants=[{"color": "Noir", "barcode": code}])
        self.assertEqual(dup.status_code, 409, dup.text)
        dup_product = self._product(tag="C", barcode=code)
        self.assertEqual(dup_product.status_code, 409, dup_product.text)

    def test_republishing_restores_only_variants_the_archive_switched_off(self):
        prod = self._ok_product(variants=[{"color": "Noir"}, {"color": "Blanc"}])
        by_color = {v["attributes"]["color"]: v["id"] for v in prod["variants"]}
        r = self.client.put(f"/api/v1/admin/variants/{by_color['Blanc']}", headers=self.headers,
                            json={"is_active": False})
        self.assertEqual(r.status_code, 200, r.text)
        for status in ("archived", "published"):
            r = self.client.post("/api/v1/admin/products/bulk-status", headers=self.headers,
                                 json={"product_ids": [prod["id"]], "status": status})
            self.assertEqual(r.status_code, 200, r.text)
        admin = self.client.get(f"/api/v1/admin/products?q={prod['sku']}", headers=self.headers).json()["items"][0]
        active = {v["attributes"]["color"]: v["is_active"] for v in admin["variants"]}
        self.assertEqual(active, {"Noir": True, "Blanc": False})

    def test_products_of_a_hidden_category_cannot_be_ordered(self):
        prod = self._ok_product()
        variant_id = prod["variants"][0]["id"]
        r = self.client.put(f"/api/v1/admin/categories/{self.category_id}", headers=self.headers,
                            json={"is_active": False})
        self.assertIn(r.status_code, (200, 204), r.text)
        order = self.client.post("/api/v1/orders", headers={"Idempotency-Key": f"rv-{self.suffix}"}, json={
            "full_name": "Client Revue", "phone": "0770" + self.suffix[:6].translate(str.maketrans("abcdef", "123456")),
            "wilaya_code": "16", "commune": "Alger Centre", "delivery_address": "1 rue de la Revue, Alger",
            "delivery_method": "home", "items": [{"variant_id": variant_id, "quantity": 1}],
        })
        self.assertEqual(order.status_code, 404, order.text)

    def test_paying_then_cancelling_an_expense_keeps_the_ledger_balanced(self):
        r = self.client.post("/api/v1/admin/expenses", headers=self.headers, json={
            "description": f"Loyer {self.suffix}", "category": "loyer", "amount_dzd": 3000,
            "payment_method": "check", "payment_status": "pending",
        })
        self.assertEqual(r.status_code, 201, r.text)
        exp_id = r.json()["id"]
        r = self.client.post(f"/api/v1/admin/expenses/{exp_id}/pay?payment_method=check", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        again = self.client.post(f"/api/v1/admin/expenses/{exp_id}/pay?payment_method=check", headers=self.headers)
        self.assertEqual(again.status_code, 400, again.text)
        r = self.client.delete(f"/api/v1/admin/expenses/{exp_id}", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT entry_number, account_code, debit_dzd, credit_dzd FROM accounting_ledger WHERE source_document = ?",
                (f"EXP-{exp_id}",),
            )
            rows = {r["entry_number"]: dict(r) for r in cur.fetchall()}
        self.assertEqual(set(rows), {f"EXP-{exp_id}-D", f"EXP-{exp_id}-C", f"EXP-{exp_id}-RD", f"EXP-{exp_id}-RC"})
        self.assertEqual(rows[f"EXP-{exp_id}-C"]["account_code"], "5120")  # a cheque leaves the bank
        self.assertEqual(sum(r["debit_dzd"] for r in rows.values()), sum(r["credit_dzd"] for r in rows.values()))

    def test_generic_settings_route_bounds_the_tax_rate(self):
        r = self.client.put("/api/v1/admin/settings", headers=self.headers,
                            json={"settings": {"pos_tax_rate_percent": "150"}})
        self.assertEqual(r.status_code, 422, r.text)

    def test_refund_credit_note_keeps_the_tax(self):
        prod = self._ok_product()
        variant_id = prod["variants"][0]["id"]
        r = self.client.put("/api/v1/admin/settings", headers=self.headers,
                            json={"settings": {"pos_tax_rate_percent": "19"}})
        self.assertEqual(r.status_code, 200, r.text)
        try:
            cur = self.client.get("/api/v1/admin/pos/register/current", headers=self.headers).json()
            if not cur.get("session"):
                r = self.client.post("/api/v1/admin/pos/register/open", headers=self.headers,
                                     json={"opening_float_dzd": 0})
                self.assertEqual(r.status_code, 201, r.text)
            sale = self.client.post("/api/v1/admin/pos/sales", headers=self.headers, json={
                "items": [{"variant_id": variant_id, "quantity": 1}],
                "payments": [{"method": "cash", "amount_dzd": 5950}],
            })
            self.assertEqual(sale.status_code, 201, sale.text)
            sale_body = sale.json()
            self.assertEqual(sale_body["tax_dzd"], 950)
            refund = self.client.post(f"/api/v1/admin/pos/sales/{sale_body['id']}/refund", headers=self.headers,
                                      json={"refund_method": "cash"})
            self.assertEqual(refund.status_code, 201, refund.text)
            rb = refund.json()
            self.assertEqual(rb["tax_dzd"], 950)
            self.assertEqual(rb["total_dzd"], 5950)
            self.assertEqual(rb["subtotal_dzd"] - rb["discount_dzd"] + rb["tax_dzd"], rb["total_dzd"])
        finally:
            self.client.put("/api/v1/admin/settings", headers=self.headers,
                            json={"settings": {"pos_tax_rate_percent": "0"}})


if __name__ == "__main__":
    unittest.main()
