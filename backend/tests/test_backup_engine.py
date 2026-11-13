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

    def test_01b_backup_is_streamed_not_held_in_memory(self):
        """The API container has 256 MB on a 2 GB VPS: a backup must not hold
        the whole database in memory."""
        import json as _json
        import tracemalloc
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            for i in range(8000):
                cur.execute(
                    "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
                    (None, "memory_probe", "product", str(i), _json.dumps({"note": "x" * 200})))
        tracemalloc.start()
        meta = bk.create_backup("manual")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertGreater(meta["total_rows"], 8000)
        self.assertLess(peak, 8 * 1024 * 1024, f"peak {peak / 1e6:.1f} MB")
        self.assertTrue(bk.verify_backup(meta["name"])["ok"])

    def test_01d_backup_reads_one_consistent_view(self):
        """A row committed while the backup runs must not appear half-way:
        every table is read from the view the backup started with."""
        from unittest import mock
        before = _count("audit_logs")
        orig = bk._iter_table
        state = {"done": False}

        def iter_then_commit_elsewhere(conn, table, *a, **kw):
            rows = orig(conn, table, *a, **kw)
            cols = next(rows)                       # the first read has happened
            if not state["done"] and table != "audit_logs":
                state["done"] = True
                with db_session(commit=True) as other:
                    other.cursor().execute(
                        "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) "
                        "VALUES (?, ?, ?, ?, ?)", (None, "during_backup", "test", "1", "{}"))
            yield cols
            yield from rows

        with mock.patch.object(bk, "_iter_table", iter_then_commit_elsewhere):
            meta = bk.create_backup("manual")
        self.assertTrue(state["done"])
        self.assertEqual(_count("audit_logs"), before + 1)       # committed for real
        self.assertEqual(meta["counts"]["audit_logs"], before)   # but not in this backup

    def test_01e_integrity_check_finds_orphans_on_both_engines(self):
        """The bulk replace turns FK enforcement off (both engines): the check
        before commit must still catch a row pointing at nothing."""
        with db_session() as conn:
            bk._begin_bulk(conn)
            try:
                bk._check_integrity(conn)                          # clean database: passes
                _, rows = bk._query(conn, "SELECT id FROM permissions ORDER BY id LIMIT 1")
                try:
                    bk._exec(conn, "INSERT INTO role_permissions (role_id, permission_id) VALUES (987654, %d)" % rows[0][0])
                except Exception:
                    # PostgreSQL role without the right to switch FK checks off:
                    # they stay on during the replace, so no orphan can exist.
                    self.skipTest("foreign keys stay enforced for this database role")
                with self.assertRaises(bk.BackupError) as ctx:
                    bk._check_integrity(conn)
                self.assertIn("orphelins", str(ctx.exception))
            finally:
                bk._raw(conn).rollback()
                bk._end_bulk(conn)
        self.assertEqual(_count("role_permissions WHERE role_id = 987654"), 0)

    def test_01f_restore_brings_back_the_photos_saved_with_the_backup(self):
        from pathlib import Path
        from unittest import mock
        uploads = Path(tempfile.mkdtemp(prefix="luxe_up_test_"))
        (uploads / "products").mkdir()
        (uploads / "products" / "sac.jpg").write_bytes(b"photo-bytes")
        with mock.patch.dict(os.environ, {"UPLOAD_DIR": str(uploads)}):
            meta = bk.create_backup("manual", include_media=True)
            self.assertTrue(meta["media"])
            (uploads / "products" / "sac.jpg").unlink()           # new server: photos missing
            out = bk.restore_backup(meta["name"])
            self.assertEqual(out["media_files"], 1)
            self.assertEqual((uploads / "products" / "sac.jpg").read_bytes(), b"photo-bytes")
            # A damaged photo archive is refused before anything changes.
            media = Path(bk.backup_dir()) / meta["media"]["name"]
            media.write_bytes(media.read_bytes()[:-10] + b"0123456789")
            with self.assertRaises(bk.BackupError):
                bk.restore_backup(meta["name"])

    def test_01c_pc_copy_download_and_import_back(self):
        """A copy kept on the owner's PC: encrypted, owner only, audited, and
        restorable after being sent back."""
        meta = bk.create_backup("manual")
        r = self.client.get(f"/api/v1/admin/system/backups/{meta['name']}/download", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.content.startswith(bk.MAGIC), "the PC copy stays encrypted")
        self.assertIn("no-store", r.headers.get("cache-control", ""))
        self.assertNotIn("content-encoding", r.headers, "encrypted copies are not re-compressed (1 vCPU)")
        # sent back (e.g. after a server loss) -> listed and verifiable
        up = self.client.post("/api/v1/admin/system/backups/import", headers=self.headers,
                              files={"file": (meta["name"], r.content, "application/octet-stream")})
        self.assertEqual(up.status_code, 201, up.text)
        self.assertTrue(up.json()["name"].startswith("luxe_app_imported_"))
        self.assertTrue(bk.verify_backup(up.json()["name"])["ok"])
        # junk and other-key files are refused
        junk = self.client.post("/api/v1/admin/system/backups/import", headers=self.headers,
                                files={"file": ("x.json.gz.enc", b"not a backup", "application/octet-stream")})
        self.assertEqual(junk.status_code, 409)
        tampered = bytearray(r.content); tampered[-5] ^= 0xFF
        bad = self.client.post("/api/v1/admin/system/backups/import", headers=self.headers,
                               files={"file": (meta["name"], bytes(tampered), "application/octet-stream")})
        self.assertEqual(bad.status_code, 409)
        # path tricks refused
        self.assertIn(self.client.get("/api/v1/admin/system/backups/..%2F..%2Fetc%2Fpasswd/download", headers=self.headers).status_code, (404, 409))

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
        newest = bk.list_backups()[0]["name"] if bk.list_backups() else "luxe_app_manual_20260101_000000.json.gz.enc"
        self.assertEqual(self.client.get(f"/api/v1/admin/system/backups/{newest}/download", headers=ed).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/admin/system/backups/import", headers=ed,
                                          files={"file": ("x", b"x", "application/octet-stream")}).status_code, 403)
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

    def test_06b_restore_streams_and_refuses_damaged_files_before_touching_data(self):
        import gzip as _gzip
        import json as _json
        import tracemalloc
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            for i in range(6000):
                cur.execute(
                    "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
                    (None, "restore_probe", "product", str(i), _json.dumps({"note": "y" * 200})))
        meta = bk.create_backup("manual")
        before = _count("audit_logs")

        # A truncated file is refused and nothing is deleted.
        path = bk.backup_dir() / meta["name"]
        raw = bk._read_backup(meta["name"])
        text = _gzip.decompress(raw).decode("utf-8").splitlines(keepends=True)
        cut = _gzip.compress("".join(text[: len(text) // 2]).encode("utf-8"))
        broken = "luxe_app_manual_20260101_000000_beef.json.gz"
        (bk.backup_dir() / broken).write_bytes(cut)
        with self.assertRaises(bk.BackupError):
            bk.restore_backup(broken)
        self.assertEqual(_count("audit_logs"), before, "a damaged backup never empties the database")
        (bk.backup_dir() / broken).unlink()

        # A good one restores with little memory (rows streamed in batches).
        tracemalloc.start()
        res = bk.restore_backup(meta["name"])
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertTrue(res["restored"])
        self.assertGreaterEqual(_count("audit_logs"), before)
        self.assertLess(peak, 12 * 1024 * 1024, f"restore peak {peak / 1e6:.1f} MB")
        self.assertTrue(path.exists())

    def test_06c_old_format_backup_still_restores(self):
        """Backups made before the streamed format (one JSON document)."""
        import gzip as _gzip
        import json as _json
        snap = bk.load_snapshot(bk.create_backup("manual")["name"])
        v1 = {"format": bk.FORMAT_V1, "created_at": snap.get("created_at"), "engine": snap.get("engine"),
              "tables": snap["tables"], "counts": snap["counts"]}
        name = "luxe_app_manual_20250101_000000_01d1.json.gz"
        (bk.backup_dir() / name).write_bytes(_gzip.compress(_json.dumps(v1).encode("utf-8")))
        self.assertTrue(bk.verify_backup(name)["ok"])
        cats = _count("categories")
        self.assertTrue(bk.restore_backup(name)["restored"])
        self.assertEqual(_count("categories"), cats)
        (bk.backup_dir() / name).unlink()

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
        # The public list is revalidated on every load; admin lists are never stored.
        self.assertIn("no-cache", public_before.headers.get("cache-control", ""))  # browsers revalidate: no stale category
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
