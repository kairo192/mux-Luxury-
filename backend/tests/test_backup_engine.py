"""
Database administration: backups, restore, "nouvelle base de données",
category archive/restore and the "deleted categories come back" regression.
"""
import os
import tempfile
import unittest

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")
os.environ.setdefault("BACKUP_ENCRYPTION_KEY", "test_only_ephemeral_backup_encryption_key_2026_0123456789abcdef")
_BACKUP_DIR = tempfile.mkdtemp(prefix="luxe_bk_test_")
os.environ["BACKUP_DIR"] = _BACKUP_DIR

from fastapi.testclient import TestClient

from app import backup_engine as bk
from app.database import db_session
from app.main import app
from app.migration_runner import run as migrate
from app.seed import seed_initial_data
from app.security import reset_rate_limits

OWNER = {"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"}
EDITOR = {"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"}


def _count(table: str) -> int:
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        return int(cur.fetchone()["cnt"])


class TestBackupEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        migrate()
        cls.client = TestClient(app)

    def setUp(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", json=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _editor_headers(self):
        r = self.client.post("/api/v1/admin/auth/login", json=EDITOR)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ------------------------------------------------------------ engine --
    def test_01_backup_is_encrypted_verifiable_and_listed(self):
        meta = bk.create_backup("manual")
        self.assertTrue(meta["encrypted"])
        self.assertTrue(meta["name"].endswith(".json.gz.enc"))
        raw = (bk.backup_dir() / meta["name"]).read_bytes()
        self.assertTrue(raw.startswith(bk.MAGIC))
        self.assertNotIn(b"admin@mus-luxury.com", raw)  # really encrypted
        self.assertTrue(bk.verify_backup(meta["name"])["ok"])
        self.assertIn(meta["name"], [b["name"] for b in bk.list_backups()])

    def test_02_wrong_key_is_refused_with_clear_message(self):
        meta = bk.create_backup("manual")
        old = os.environ["BACKUP_ENCRYPTION_KEY"]
        try:
            os.environ["BACKUP_ENCRYPTION_KEY"] = "another_key_that_is_long_enough_0123456789"
            with self.assertRaises(bk.BackupError):
                bk.load_snapshot(meta["name"])
        finally:
            os.environ["BACKUP_ENCRYPTION_KEY"] = old

    def test_03_path_traversal_names_are_rejected(self):
        for name in ["../luxe_store.sqlite3", "luxe_app_manual_x.json.gz", "/etc/passwd"]:
            with self.assertRaises(bk.BackupError):
                bk.load_snapshot(name)

    # --------------------------------------------------------- endpoints --
    def test_04_database_endpoints_are_owner_only(self):
        ed = self._editor_headers()
        self.assertEqual(self.client.get("/api/v1/admin/system/database", headers=ed).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/admin/system/reset", headers=ed,
                                          json={"password": "x", "confirm": "EFFACER"}).status_code, 403)
        r = self.client.get("/api/v1/admin/system/database", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        expected_engine = "PostgreSQL" if os.environ.get("LUXE_DB_ENGINE") == "postgres" else "SQLite"
        self.assertEqual(body["engine"], expected_engine)
        self.assertTrue(body["encryption"])
        self.assertTrue(any(c["table"] == "categories" for c in body["counts"]))

    def test_05_reset_requires_word_and_password(self):
        r = self.client.post("/api/v1/admin/system/reset", headers=self.headers,
                             json={"password": OWNER["password"], "confirm": "oui"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/v1/admin/system/reset", headers=self.headers,
                             json={"password": "wrong-password", "confirm": "EFFACER"})
        self.assertEqual(r.status_code, 403)
        self.assertGreater(_count("categories"), 0, "nothing may be erased on a refused reset")

    def test_06_reset_then_restore_roundtrip(self):
        cats, prods, zones, admins = _count("categories"), _count("products"), _count("delivery_zones"), _count("admin_users")
        self.assertGreater(cats, 0)
        manual = self.client.post("/api/v1/admin/system/backups", headers=self.headers, json={}).json()

        r = self.client.post("/api/v1/admin/system/reset", headers=self.headers,
                             json={"password": OWNER["password"], "confirm": "effacer", "keep_settings": True})
        self.assertEqual(r.status_code, 200, r.text)
        res = r.json()
        self.assertTrue(res["safety_backup"].startswith("luxe_app_pre-reset_"))
        self.assertEqual(_count("categories"), 0)
        self.assertEqual(_count("products"), 0)
        self.assertEqual(_count("delivery_zones"), zones, "wilayas are kept")
        self.assertEqual(_count("admin_users"), admins, "staff accounts are kept")

        # Still logged in and working after the reset; new ids start again.
        r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": "apres-reset", "name_fr": "Après reset", "name_ar": "x", "name_en": "After",
            "display_order": 1, "is_active": True, "show_on_homepage": False})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["id"], 1)

        # The POS catalog epoch changed → POS PCs will re-download the catalog.
        snap = self.client.get("/api/v1/admin/pos/catalog/snapshot", headers=self.headers).json()
        self.assertNotEqual(snap["catalog_epoch"], "initial")

        r = self.client.post(f"/api/v1/admin/system/backups/{manual['name']}/restore", headers=self.headers,
                             json={"password": OWNER["password"], "confirm": "RESTAURER"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(_count("categories"), cats)
        self.assertEqual(_count("products"), prods)
        if os.environ.get("LUXE_DB_ENGINE") != "postgres":
            # PostgreSQL enforces foreign keys itself; SQLite needs the check.
            with db_session() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

        kinds = {b["kind"] for b in bk.list_backups()}
        self.assertTrue({"manual", "pre-reset", "pre-restore"} <= kinds)

    # ------------------------------------------------------- categories --
    def test_07_deleted_category_never_comes_back_and_archive_can_be_restored(self):
        def create(slug):
            r = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
                "slug": slug, "name_fr": slug, "name_ar": "x", "name_en": slug,
                "display_order": 50, "is_active": True, "show_on_homepage": False})
            self.assertEqual(r.status_code, 201, r.text)
            return r.json()["id"]

        gone, archived = create("cat-gone"), create("cat-archived")
        public_before = self.client.get("/api/v1/categories")
        # The public list is cacheable only briefly; admin lists never.
        self.assertIn("max-age=30", public_before.headers.get("cache-control", ""))
        admin_list = self.client.get("/api/v1/admin/categories?include_archived=true", headers=self.headers)
        self.assertIn("no-store", admin_list.headers.get("cache-control", ""))

        self.assertEqual(self.client.delete(f"/api/v1/admin/categories/{gone}?hard_delete=true", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/admin/categories/{archived}", headers=self.headers).status_code, 200)

        items = self.client.get("/api/v1/admin/categories?include_archived=true", headers=self.headers).json()["items"]
        ids = {c["id"]: c for c in items}
        self.assertNotIn(gone, ids)
        self.assertIsNotNone(ids[archived]["deleted_at"])
        public = {c["id"] for c in self.client.get("/api/v1/categories").json()["items"]}
        self.assertNotIn(gone, public)
        self.assertNotIn(archived, public)

        r = self.client.post(f"/api/v1/admin/categories/{archived}/restore", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        public = {c["id"] for c in self.client.get("/api/v1/categories").json()["items"]}
        self.assertIn(archived, public)


if __name__ == "__main__":
    unittest.main()
