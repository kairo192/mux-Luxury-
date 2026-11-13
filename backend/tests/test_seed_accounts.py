"""
Accounts created at first start. This repository is public: in PRODUCTION the
known development passwords and placeholders must never become a real login.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from app import seed


class TestSeedAccountPasswords(unittest.TestCase):
    def pw(self, value, production=True):
        env = {} if value is None else {"ADMIN_INITIAL_PASSWORD": value}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(seed, "is_production", return_value=production):
            if value is None:
                os.environ.pop("ADMIN_INITIAL_PASSWORD", None)
            return seed._seed_password("ADMIN_INITIAL_PASSWORD", seed._DEV_ADMIN_PASSWORD)

    def test_production_refuses_known_and_weak_passwords(self):
        for bad in (None, "", "short", seed._DEV_ADMIN_PASSWORD, seed._DEV_EDITOR_PASSWORD,
                    "disabled-in-production", "REPLACE_production_password", "<CHANGE_ME_STRONG_DEV_PASSWORD>"):
            with self.subTest(bad=bad):
                self.assertIsNone(self.pw(bad), "no account with this password in production")

    def test_production_accepts_a_strong_configured_password(self):
        self.assertEqual(self.pw("Kx9!pLm2#Qw7vR"), "Kx9!pLm2#Qw7vR")

    def test_development_keeps_its_known_password(self):
        self.assertEqual(self.pw(None, production=False), seed._DEV_ADMIN_PASSWORD)


if __name__ == "__main__":
    unittest.main()
