"""
Hostile or odd input on the PUBLIC routes must get a clear 4xx in French —
never a server error (found by fuzzing: a NUL character crashed PostgreSQL
with a 500 on /products?category=%00 and on the order form).
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
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestInputHygiene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        slug = cls.client.get("/api/v1/products?page_size=1").json()["items"][0]["slug"]
        cls.variant_id = cls.client.get(f"/api/v1/products/{slug}").json()["variants"][0]["id"]

    def setUp(self):
        reset_rate_limits()

    def order(self, **over):
        body = {"full_name": "Karim Test", "phone": "0661" + str(uuid.uuid4().int)[:6], "wilaya_code": "16",
                "commune": "Alger Centre", "delivery_address": "1 rue Didouche", "delivery_method": "home",
                "items": [{"variant_id": self.variant_id, "quantity": 1}]}
        body.update(over)
        return self.client.post("/api/v1/orders", json=body, headers={"Idempotency-Key": uuid.uuid4().hex})

    def test_nul_character_refused_in_french(self):
        r = self.client.get("/api/v1/products?category=%00")
        self.assertEqual(r.status_code, 422)
        self.assertIn("Caractère invalide", r.json()["detail"])
        r = self.order(full_name="Karim\u0000")
        self.assertEqual(r.status_code, 422)
        self.assertIn("Caractère invalide", r.json()["detail"])

    def test_direction_override_characters_removed_from_names(self):
        r = self.order(full_name=chr(0x202E) + "Karim" + chr(0x200F) + " Test")  # right-to-left override, RTL mark
        self.assertEqual(r.status_code, 201, r.text)
        ref = r.json()["order_reference"]
        login = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        found = self.client.get("/api/v1/admin/orders", params={"q": ref}, headers=headers).json()["items"]
        self.assertEqual(found[0]["customer_name"], "Karim Test")

    def test_phone_error_is_french(self):
        r = self.order(phone="12345")
        self.assertEqual(r.status_code, 422)
        self.assertIn("Numéro de mobile algérien invalide", r.text)

    def test_uploads_and_normal_json_unaffected(self):
        # a JSON body without NUL goes through untouched (order created)
        self.assertEqual(self.order().status_code, 201)
        # multipart uploads are not read by the NUL guard: a photo with 0x00 bytes is fine
        login = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), (120, 30, 60)).save(buf, "PNG")
        self.assertIn(b"\x00", buf.getvalue())
        up = self.client.post("/api/v1/admin/upload", headers=headers, files={"file": ("p.png", buf.getvalue(), "image/png")})
        self.assertIn(up.status_code, (200, 201), up.text)


if __name__ == "__main__":
    unittest.main()
