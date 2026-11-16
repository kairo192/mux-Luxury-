"""
Login rate limit in nginx (2026-11-16): after a few wrong passwords the CMS said
"cannot reach the server", because nginx answered 503 without CORS headers, even
to the browser's preflight. Now preflights are not counted, and a limited login
gets 429 with the app's CORS headers, which the CMS shows as "too many attempts".
"""
import re
import unittest
from pathlib import Path

NGINX = Path(__file__).resolve().parents[2] / "infrastructure" / "nginx" / "nginx.conf"


class TestNginxLoginLimit(unittest.TestCase):
    def setUp(self):
        self.conf = NGINX.read_text(encoding="utf-8")

    def test_preflight_is_not_a_login_attempt(self):
        self.assertRegex(self.conf, r'map \$request_method \$auth_limit_key \{\s*OPTIONS "";')
        self.assertIn("limit_req_zone $auth_limit_key zone=auth_limit:10m rate=5r/m;", self.conf)

    def test_limited_login_gets_429_the_app_can_read(self):
        blocks = re.findall(r"location /api/v1/admin/auth/ \{.*?\n        \}", self.conf, re.S)
        self.assertEqual(len(blocks), 2)                       # api.* and the shop host
        for b in blocks:
            self.assertIn("limit_req_status 429;", b)
            self.assertIn("error_page 429 = @auth_too_many;", b)
        named = re.findall(r"location @auth_too_many \{.*?\n        \}", self.conf, re.S)
        self.assertEqual(len(named), 2)
        for n in named:
            self.assertIn("Access-Control-Allow-Origin $auth_cors_origin always", n)
            self.assertIn("return 429", n)

    def test_cors_on_429_only_for_known_origins(self):
        m = re.search(r"map \$http_origin \$auth_cors_origin \{(.*?)\}", self.conf, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn('default "";', body)                     # unknown sites get no CORS
        self.assertIn('"http://tauri.localhost"', body)
        self.assertNotIn("*", body)


if __name__ == "__main__":
    unittest.main()
