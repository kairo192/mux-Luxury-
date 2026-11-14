"""
.env keys and the code must agree (app/settings.py is the single list):
every key the server reads is registered, every key a template offers is read
somewhere, the templates are generated (not hand-edited), and keys of features
that are not built are never offered.
"""
import os
import re
import unittest
from pathlib import Path

import tempfile

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from app import settings

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"

# Read by the code for tests / process plumbing, never configured by the owner.
INTERNAL = {"APP_ENV_FILE", "PYTEST_CURRENT_TEST"}


def _python_reads():
    names = set()
    pat = re.compile(r"""(?:os\.getenv|os\.environ\.get|environ\[|_int_env|_env_bool|_seed_password)\(\s*["']([A-Z][A-Z0-9_]+)["']""")
    reg = re.compile(r"""app_settings\.(?:get|get_int|raw)\(\s*["']([A-Z][A-Z0-9_]+)["']""")
    for f in APP.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        names |= set(pat.findall(text)) | set(reg.findall(text))
    return names


def _script_reads():
    names = set()
    files = list((ROOT / "infrastructure").rglob("*.sh")) + [ROOT / "docker-compose.yml"]
    for f in files:
        names |= set(re.findall(r"\$\{?([A-Z][A-Z0-9_]+)", f.read_text(encoding="utf-8")))
    return names


class TestSettingsRegistry(unittest.TestCase):
    def test_every_key_the_server_reads_is_registered(self):
        known = set(settings.BY_NAME) | set(settings.ALIASES) | INTERNAL
        unknown = sorted(_python_reads() - known)
        self.assertEqual(unknown, [], "read by backend/app but missing from app/settings.py")

    def test_every_template_key_is_read_somewhere(self):
        read = _python_reads() | _script_reads()
        offered = [s.name for s in settings.SETTINGS if s.in_template]
        dead = sorted(n for n in offered if n not in read and not any(a in read for a in settings.BY_NAME[n].aliases))
        self.assertEqual(dead, [], "offered by the .env templates but read by nothing")

    def test_templates_are_generated_not_hand_edited(self):
        for rel, profile in settings.TEMPLATE_FILES.items():
            with self.subTest(template=rel):
                self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), settings.render_template(profile),
                                 f"{rel} differs: run `python3 -m app.settings templates` in backend/")

    def test_templates_offer_only_registered_keys(self):
        for rel in settings.TEMPLATE_FILES:
            keys = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", (ROOT / rel).read_text(encoding="utf-8"), re.M))
            self.assertEqual(sorted(keys - set(settings.BY_NAME)), [], rel)

    def test_keys_of_removed_features_are_reported_as_unused(self):
        import tempfile as _tf
        with _tf.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("APP_ENV=production\nCHARGILY_SECRET_KEY=x\nYALIDINE_API_TOKEN=y\nSMTP_PASSWORD=z\n")
        rep = settings.check_file(f.name)
        os.unlink(f.name)
        self.assertEqual(rep["unused"], ["CHARGILY_SECRET_KEY", "SMTP_PASSWORD", "YALIDINE_API_TOKEN"])

    def _complete_production_env(self):
        env = {"APP_ENV": "production"}
        for s in settings.SETTINGS:
            if s.required_in_production:
                env[s.name] = "x" * 40
        env["DATABASE_URL"] = "postgresql://luxe_app_user:" + "p" * 30 + "@db:5432/luxe_ecommerce"
        return env

    def test_placeholder_inside_database_url_is_reported(self):
        env = self._complete_production_env()
        self.assertTrue(settings.configuration_report(env, production=True)["ok"])
        env["DATABASE_URL"] = "postgresql://luxe_app_user:<CHANGE_ME_POSTGRES_PASSWORD>@db:5432/luxe_ecommerce"
        rep = settings.configuration_report(env, production=True)
        self.assertFalse(rep["ok"])
        self.assertTrue(any(p.startswith("DATABASE_URL") for p in rep["problems"]))

    def test_offsite_switched_on_without_its_keys_blocks(self):
        env = self._complete_production_env()
        rep = settings.configuration_report(env, production=True)
        self.assertTrue(rep["ok"])                                  # off-site off = warning only
        self.assertTrue(any(p.startswith("S3_BACKUP_ENABLED") for p in rep["problems"]))
        env.update({"S3_BACKUP_ENABLED": "true", "S3_ENDPOINT_URL": "https://s3.example", "S3_BUCKET_NAME": "b",
                    "S3_ACCESS_KEY_ID": "k"})
        rep = settings.configuration_report(env, production=True)
        self.assertFalse(rep["ok"])
        self.assertTrue(any(p.startswith("S3_SECRET_ACCESS_KEY") for p in rep["problems"]))

    def test_report_never_contains_secret_values(self):
        env = {s.name: f"value-of-{s.name}" for s in settings.SETTINGS}
        rep = settings.configuration_report(env, production=True)
        flat = repr(rep["groups"])
        for s in settings.SETTINGS:
            if s.secret:
                self.assertNotIn(f"value-of-{s.name}", flat, s.name)

    def test_old_names_still_work(self):
        env = {"CORS_ALLOWED_ORIGINS": "https://boutique.example", "MAX_LOGIN_ATTEMPTS_PER_MINUTE": "8"}
        self.assertEqual(settings.get("CORS_ORIGINS", env=env), "https://boutique.example")
        self.assertEqual(settings.get_int("LOGIN_ATTEMPTS_PER_MINUTE", 1, 30, env=env), 8)

    def test_production_reports_missing_required_settings(self):
        rep = settings.configuration_report({"APP_ENV": "production"}, production=True)
        self.assertFalse(rep["ok"])
        missing = " ".join(rep["problems"])
        for name in ("SECRET_KEY", "DATABASE_URL", "BACKUP_ENCRYPTION_KEY"):
            self.assertIn(name, missing)



class TestConfigurationEndpoint(unittest.TestCase):
    """CMS → Sauvegardes & Sécurité shows the owner what is set or missing."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.seed import seed_initial_data
        from app.security import reset_rate_limits
        seed_initial_data()
        reset_rate_limits()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        cls.owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        ed = cls.client.post("/api/v1/admin/auth/login", json={"email": "editor@mus-luxury.com", "password": "EditorLuxury2026!"})
        cls.editor = {"Authorization": f"Bearer {ed.json()['access_token']}"}

    def test_owner_sees_states_never_secret_values(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {"S3_SECRET_ACCESS_KEY": "s3-secret-value-xyz", "BACKUP_ENCRYPTION_KEY": "b" * 64}):
            r = self.client.get("/api/v1/admin/system/configuration", headers=self.owner)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.text
        self.assertIn("SECRET_KEY", body)
        self.assertNotIn("s3-secret-value-xyz", body)
        self.assertNotIn("b" * 64, body)
        self.assertNotIn(os.environ["SECRET_KEY"], body)

    def test_other_roles_refused(self):
        self.assertIn(self.client.get("/api/v1/admin/system/configuration", headers=self.editor).status_code, (401, 403))
        self.assertEqual(self.client.get("/api/v1/admin/system/configuration").status_code, 401)


if __name__ == "__main__":
    unittest.main()
