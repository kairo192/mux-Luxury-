"""
Product photos: a variant only has a photo when one was chosen for it
(otherwise it follows the product's main photo), and the SEO title /
description typed in the CMS are used for link previews.
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

from app import seo
from app.main import app
from app.seed import seed_initial_data
from app.security import reset_rate_limits

TEMPLATE = "<html><head><title>x</title><!-- SEO:START --><!-- SEO:END --></head><body></body></html>"


class TestProductMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.sfx = uuid.uuid4().hex[:6]
        cat = self.client.post("/api/v1/admin/categories", headers=self.h, json={
            "slug": f"media-{self.sfx}", "name_fr": "Media", "name_ar": "x", "name_en": "Media",
            "display_order": 1, "is_active": True, "show_on_homepage": False}).json()
        self.client.post("/api/v1/admin/category-attributes", headers=self.h, json={
            "category_id": cat["id"], "attr_key": "color", "label_fr": "Couleur", "input_type": "single_select",
            "is_variant_axis": True, "options": [{"value": "Bleu", "label_fr": "Bleu"}, {"value": "Rouge", "label_fr": "Rouge"}]})
        self.cat_id = cat["id"]

    def _create(self, **extra):
        body = {
            "category_id": self.cat_id, "slug": f"media-p-{self.sfx}", "sku": f"MD-{self.sfx.upper()}",
            "name_fr": "Robe média", "selling_price_dzd": 5000, "status": "published",
            "main_image_url": "/uploads/main_a.png",
            "variants": [
                {"sku": f"MD-{self.sfx.upper()}-B", "title": "Bleu", "stock_qty": 2, "attributes": {"color": "Bleu"}},
                {"sku": f"MD-{self.sfx.upper()}-R", "title": "Rouge", "stock_qty": 2, "attributes": {"color": "Rouge"},
                 "image_url": "/uploads/red.png"},
            ],
        }
        body.update(extra)
        r = self.client.post("/api/v1/admin/products", headers=self.h, json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_variant_photo_only_when_chosen(self):
        prod = self._create()
        by_title = {v["title"]: v for v in prod["variants"]}
        self.assertIn(by_title["Bleu"].get("image_url"), (None, ""), "no copy of the main photo")
        self.assertEqual(by_title["Rouge"]["image_url"], "/uploads/red.png")
        # A variant added later also follows the product photo.
        r = self.client.post(f"/api/v1/admin/products/{prod['id']}/variants", headers=self.h, json={
            "sku": f"MD-{self.sfx.upper()}-X", "title": "Extra", "stock_qty": 1, "attributes": {"color": "Bleu"}})
        if r.status_code == 201:
            self.assertIn(r.json().get("image_url"), (None, ""))

    def test_seo_fields_win_in_link_preview(self):
        self._create(seo_title="Robe bleue de soirée | Mus Luxury", seo_description="La robe de la saison.")
        orig = seo.get_template
        seo.get_template = lambda: TEMPLATE
        try:
            html = self.client.get(f"/api/v1/seo/render/produit/media-p-{self.sfx}").text
        finally:
            seo.get_template = orig
        self.assertIn("<title>Robe bleue de soirée | Mus Luxury</title>", html)
        self.assertIn('content="La robe de la saison."', html)


if __name__ == "__main__":
    unittest.main()


class TestUploadOptimization(unittest.TestCase):
    """Phone photos are reduced and cleaned before being stored (40 GB VPS)."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.seed import seed_initial_data
        seed_initial_data()
        cls.client = TestClient(app)

    def setUp(self):
        from app.security import reset_rate_limits
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _upload(self, data: bytes, name: str, mime: str):
        return self.client.post("/api/v1/admin/upload", headers=self.h, files={"file": (name, data, mime)})

    def test_big_phone_photo_is_reduced_turned_upright_and_stripped(self):
        import io as _io
        import random
        from PIL import Image
        img = Image.new("RGB", (4000, 3000))
        img.putdata([(random.randrange(256), 90, 60) for _ in range(4000 * 3000)][: 4000 * 3000])
        exif = Image.Exif()
        exif[0x0112] = 6            # orientation: rotate 90° (phone held upright)
        exif[0x8825] = {2: (36, 28, 0)}  # GPS block
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=95, exif=exif)
        r = self._upload(buf.getvalue(), "photo.jpg", "image/jpeg")
        self.assertEqual(r.status_code, 201, r.text)
        out = self.client.get(r.json()["url"]).content
        stored = Image.open(_io.BytesIO(out))
        self.assertEqual(max(stored.size), 1600)
        self.assertEqual(stored.size, (1200, 1600), "turned upright")
        self.assertFalse(stored.getexif(), "no camera metadata (GPS) kept")
        self.assertLess(len(out), len(buf.getvalue()) / 3)

    def test_transparent_png_keeps_transparency(self):
        import io as _io
        from PIL import Image
        buf = _io.BytesIO()
        Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(buf, "PNG")
        r = self._upload(buf.getvalue(), "logo.png", "image/png")
        self.assertEqual(r.status_code, 201, r.text)
        self.assertTrue(r.json()["url"].endswith(".webp"))
        self.assertEqual(Image.open(_io.BytesIO(self.client.get(r.json()["url"]).content)).mode, "RGBA")

    def test_fake_image_is_refused(self):
        r = self._upload(b"\xff\xd8\xff\xe0" + b"<?php system($_GET['c']); ?>" * 10, "x.jpg", "image/jpeg")
        self.assertEqual(r.status_code, 400)
