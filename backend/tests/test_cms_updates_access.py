"""
Desktop CMS updates are for logged-in staff only (the repository is private
and nothing is on the public website): the API serves latest.json, the signed
installer and its .sig with a valid CMS login, and refuses everything else.
"""
import os
import tempfile
import unittest
from pathlib import Path

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

BASE = "/api/v1/admin/updates/cms"
SETUP = "MusLuxuryCMS_1.2.0_x64-setup.exe"


class TestCmsUpdatesAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        reset_rate_limits()
        r = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert r.status_code == 200, r.text
        cls.owner = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"})
        assert r.status_code == 200, r.text
        cls.editor = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "cms").mkdir()
        self._old = os.environ.get("LUXE_UPDATES_DIR")
        os.environ["LUXE_UPDATES_DIR"] = str(root)
        self.addCleanup(self._restore)
        self.cms = root / "cms"
        (root / "secret.txt").write_text("outside the update folder")
        (self.cms / "notes.txt").write_text("not an update file")

    def _restore(self):
        if self._old is None:
            os.environ.pop("LUXE_UPDATES_DIR", None)
        else:
            os.environ["LUXE_UPDATES_DIR"] = self._old

    def _publish(self):
        (self.cms / "latest.json").write_text('{"version":"1.2.0"}')
        (self.cms / SETUP).write_bytes(b"MZ installer bytes")
        (self.cms / f"{SETUP}.sig").write_text("signature")

    def test_refused_without_a_valid_login(self):
        self._publish()
        for path in ("latest.json", SETUP, f"{SETUP}.sig"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(f"{BASE}/{path}").status_code, 401)
                bad = {"Authorization": "Bearer not-a-real-token"}
                self.assertEqual(self.client.get(f"{BASE}/{path}", headers=bad).status_code, 401)

    def test_logged_in_staff_get_the_files_uncached(self):
        self._publish()
        for headers in (self.owner, self.editor):           # any staff role, not only the owner
            r = self.client.get(f"{BASE}/latest.json", headers=headers)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {"version": "1.2.0"})
            self.assertIn("no-store", r.headers["cache-control"])
            r = self.client.get(f"{BASE}/{SETUP}", headers=headers)
            self.assertEqual((r.status_code, r.content), (200, b"MZ installer bytes"))
            self.assertEqual(self.client.get(f"{BASE}/{SETUP}.sig", headers=headers).text, "signature")

    def test_nothing_published_yet_means_no_update(self):
        r = self.client.get(f"{BASE}/latest.json", headers=self.owner)
        self.assertEqual(r.status_code, 204)                  # the updater reads 204 as "no update"

    def test_only_update_files_can_be_read(self):
        self._publish()
        for name in ("notes.txt", "..%2Fsecret.txt", "%2E%2E%2Fsecret.txt", "MusLuxuryCMS_..%2F..%2Fsecret.txt",
                     "MusLuxuryCMS_1.0.0-setup.exe.bak", "MusLuxuryCMS_1.9.9_x64-setup.exe"):
            with self.subTest(name=name):
                r = self.client.get(f"{BASE}/{name}", headers=self.owner)
                self.assertEqual(r.status_code, 404, r.text)
                self.assertNotIn(b"outside the update folder", r.content)


if __name__ == "__main__":
    unittest.main()
