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


class TestUserManagement(unittest.TestCase):
    """Staff user & role management with lockout guards and backend-enforced perms."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        cls.headers = cls._login("admin@musluxury.dz", "MusLuxury2026!")
        cls.editor_headers = cls._login("editor@musluxury.dz", "EditorLuxury2026!")

    @classmethod
    def _login(cls, email, pw):
        r = cls.client.post("/api/v1/admin/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()
        self.suffix = uuid.uuid4().hex[:8]
        roles = self.client.get("/api/v1/admin/roles", headers=self.headers).json()["items"]
        self.role_by_name = {r["name"]: r for r in roles}

    def _create_user(self, role_name="cashier", **over):
        body = {
            "email": f"user-{self.suffix}@musluxury.dz",
            "full_name": "Employé Test",
            "phone": "+213550000099",
            "role_id": self.role_by_name[role_name]["id"],
            "password": "StaffPass2026!",
        }
        body.update(over)
        return self.client.post("/api/v1/admin/users", headers=self.headers, json=body)

    # ------------------------------------------------------------------ tests
    def test_01_roles_include_cashier_with_perms(self):
        self.assertIn("cashier", self.role_by_name)
        self.assertIn("pos:sell", self.role_by_name["cashier"]["permissions"])
        self.assertIn("super_admin", self.role_by_name)

    def test_02_create_cashier_can_login_with_pos_perms(self):
        r = self._create_user()
        self.assertEqual(r.status_code, 201, r.text)
        login = self.client.post("/api/v1/admin/auth/login", json={"email": f"user-{self.suffix}@musluxury.dz", "password": "StaffPass2026!"})
        self.assertEqual(login.status_code, 200, login.text)
        perms = login.json()["user"]["permissions"]
        self.assertIn("pos:sell", perms)
        self.assertNotIn("settings:write", perms)

    def test_03_duplicate_email_conflict(self):
        self.assertEqual(self._create_user().status_code, 201)
        dup = self._create_user(role_name="order_manager")
        self.assertEqual(dup.status_code, 409, dup.text)

    def test_04_weak_password_rejected(self):
        r = self._create_user(password="short")
        self.assertEqual(r.status_code, 422, r.text)

    def test_05_deactivate_blocks_login(self):
        uid = self._create_user().json()["id"]
        upd = self.client.put(f"/api/v1/admin/users/{uid}", headers=self.headers, json={"is_active": False})
        self.assertEqual(upd.status_code, 200, upd.text)
        self.assertFalse(upd.json()["is_active"])
        login = self.client.post("/api/v1/admin/auth/login", json={"email": f"user-{self.suffix}@musluxury.dz", "password": "StaffPass2026!"})
        self.assertEqual(login.status_code, 401, login.text)

    def test_06_role_change_takes_effect_after_relogin(self):
        uid = self._create_user(role_name="order_manager").json()["id"]
        # promote to admin
        self.client.put(f"/api/v1/admin/users/{uid}", headers=self.headers, json={"role_id": self.role_by_name["admin"]["id"]})
        login = self.client.post("/api/v1/admin/auth/login", json={"email": f"user-{self.suffix}@musluxury.dz", "password": "StaffPass2026!"})
        self.assertIn("pos:refund", login.json()["user"]["permissions"])  # admin has it, order_manager didn't

    def test_07_reset_password(self):
        uid = self._create_user().json()["id"]
        rp = self.client.post(f"/api/v1/admin/users/{uid}/reset-password", headers=self.headers, json={"new_password": "BrandNewPass2026!"})
        self.assertEqual(rp.status_code, 200, rp.text)
        old = self.client.post("/api/v1/admin/auth/login", json={"email": f"user-{self.suffix}@musluxury.dz", "password": "StaffPass2026!"})
        self.assertEqual(old.status_code, 401)
        new = self.client.post("/api/v1/admin/auth/login", json={"email": f"user-{self.suffix}@musluxury.dz", "password": "BrandNewPass2026!"})
        self.assertEqual(new.status_code, 200)

    def test_08_cannot_remove_last_super_admin(self):
        # Find the (single) seeded super admin
        users = self.client.get("/api/v1/admin/users", headers=self.headers).json()["items"]
        supers = [u for u in users if u["role_name"] == "super_admin" and u["is_active"]]
        self.assertGreaterEqual(len(supers), 1)
        if len(supers) == 1:
            sid = supers[0]["id"]
            # demote attempt → blocked
            demote = self.client.put(f"/api/v1/admin/users/{sid}", headers=self.headers, json={"role_id": self.role_by_name["admin"]["id"]})
            self.assertEqual(demote.status_code, 400, demote.text)

    def test_09_permission_enforced(self):
        # product_manager lacks settings:write
        self.assertEqual(self.client.get("/api/v1/admin/users", headers=self.editor_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/admin/users").status_code, 401)


if __name__ == "__main__":
    unittest.main()
