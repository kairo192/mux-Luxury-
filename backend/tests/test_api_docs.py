"""docs/api/openapi.json and docs/api/ENDPOINTS.md are generated from the code: they must match it."""
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


class TestApiDocs(unittest.TestCase):
    def test_generated_api_docs_are_up_to_date(self):
        r = subprocess.run([sys.executable, "scripts/generate_api_docs.py", "--check"], cwd=BACKEND,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_only_login_and_first_start_are_public_under_admin(self):
        text = (BACKEND.parent / "docs" / "api" / "ENDPOINTS.md").read_text(encoding="utf-8")
        public_admin = sorted({line.split("`")[1] for line in text.splitlines()
                               if "/api/v1/admin/" in line and "| public |" in line})
        self.assertEqual(public_admin, ["/api/v1/admin/auth/initialize-owner", "/api/v1/admin/auth/login",
                                        "/api/v1/admin/auth/setup-status"])


if __name__ == "__main__":
    unittest.main()
