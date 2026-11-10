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


class TestAuditLogs(unittest.TestCase):
    """Audit log viewer: filters by action, entity, admin, text; facets."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        cls.admin_user_id = login.json()["user"]["id"]
        ed = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"})
        cls.editor_headers = {"Authorization": f"Bearer {ed.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:6]
        # Produce a known audited action in this test (create a category)
        self.category_id = self.client.post("/api/v1/admin/categories", headers=self.headers, json={
            "slug": f"al-{self.suffix}", "name_fr": f"AL {self.suffix}", "name_ar": "x", "name_en": "AL",
            "display_order": 99, "is_active": True, "show_on_homepage": False,
        }).json()["id"]

    # ------------------------------------------------------------------ tests
    def test_01_list_returns_items(self):
        r = self.client.get("/api/v1/admin/audit-logs", headers=self.headers, params={"limit": 50})
        self.assertEqual(r.status_code, 200)
        self.assertIn("items", r.json())
        self.assertGreater(len(r.json()["items"]), 0)
        first = r.json()["items"][0]
        self.assertIn("action", first)
        self.assertIn("details", first)  # parsed JSON

    def test_02_filter_by_entity_type(self):
        r = self.client.get("/api/v1/admin/audit-logs", headers=self.headers, params={"entity_type": "category", "limit": 20})
        for it in r.json()["items"]:
            self.assertEqual(it["entity_type"], "category")

    def test_03_filter_by_action(self):
        r = self.client.get("/api/v1/admin/audit-logs", headers=self.headers, params={"action": "admin_login", "limit": 20})
        for it in r.json()["items"]:
            self.assertEqual(it["action"], "admin_login")

    def test_04_text_search_matches_entity_id(self):
        r = self.client.get("/api/v1/admin/audit-logs", headers=self.headers, params={"q": str(self.category_id)})
        found = any(it["entity_id"] == str(self.category_id) for it in r.json()["items"])
        self.assertTrue(found)

    def test_05_filter_by_admin_user(self):
        r = self.client.get("/api/v1/admin/audit-logs", headers=self.headers, params={"admin_user_id": self.admin_user_id, "limit": 20})
        for it in r.json()["items"]:
            self.assertEqual(it["admin_user_id"], self.admin_user_id)

    def test_06_facets(self):
        r = self.client.get("/api/v1/admin/audit-logs/facets", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        actions = {a["code"] for a in r.json()["actions"]}
        self.assertIn("admin_login", actions)
        entities = {e["code"] for e in r.json()["entity_types"]}
        self.assertIn("category", entities)

    def test_07_permissions(self):
        # product_manager lacks settings:write
        self.assertEqual(self.client.get("/api/v1/admin/audit-logs", headers=self.editor_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/admin/audit-logs").status_code, 401)


if __name__ == "__main__":
    unittest.main()
