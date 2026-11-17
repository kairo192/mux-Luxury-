"""
nginx rate limits and the desktop CMS (2026-11-16). Opening the CMS sent ~40
requests at once; nginx refused most of them with 503 and no CORS headers (even
the browser's preflights), so every screen said "cannot reach the server", and
the 5-a-minute login limit also caught setup-status on each start.
Now: preflights are never counted, a limited request gets 429 + the app's CORS
headers (the CMS waits and retries), and the strict limit is only on the
endpoints that take a password.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NGINX = ROOT / "infrastructure" / "nginx" / "nginx.conf"


class TestNginxRateLimits(unittest.TestCase):
    def setUp(self):
        self.conf = NGINX.read_text(encoding="utf-8")

    def test_preflight_is_never_counted(self):
        self.assertRegex(self.conf, r'map \$request_method \$rate_limit_key \{\s*OPTIONS "";')
        zones = re.findall(r"limit_req_zone (\S+) zone=(\w+)", self.conf)
        self.assertEqual({z for _, z in zones}, {"general_api", "auth_limit", "orders_limit"})
        for key, zone in zones:
            self.assertEqual(key, "$rate_limit_key", zone)
        # the map is defined before the zones that use its variable
        self.assertLess(self.conf.index("map $request_method $rate_limit_key"), self.conf.index("limit_req_zone"))

    def test_every_limited_request_gets_429_the_app_can_read(self):
        servers = [s for s in self.conf.split("    server {")[1:] if "listen 443" in s]
        self.assertEqual(len(servers), 2)                      # api.* and the shop host
        for srv in servers:
            self.assertIn("limit_req_status 429;", srv)
            self.assertIn("limit_conn_status 429;", srv)
            self.assertIn("error_page 429 = @too_many_requests;", srv)
            named = re.search(r"location @too_many_requests \{(.*?)\n        \}", srv, re.S)
            self.assertIsNotNone(named)
            self.assertIn("Access-Control-Allow-Origin $limit_cors_origin always", named.group(1))
            self.assertIn("return 429", named.group(1))
        self.assertNotIn("503", re.sub(r"#.*", "", self.conf))  # no limit answers 503 any more

    def test_strict_limit_only_where_a_password_is_sent(self):
        strict = re.findall(r"location (.*?) \{\n(?:\s*#.*\n)*\s*limit_req zone=auth_limit", self.conf)
        self.assertEqual(strict, ["~ ^/api/v1/admin/auth/(login|initialize-owner)$"] * 2)
        self.assertNotIn("location /api/v1/admin/auth/ {", self.conf)

    def test_cors_on_429_only_for_known_origins(self):
        m = re.search(r"map \$http_origin \$limit_cors_origin \{(.*?)\}", self.conf, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn('default "";', body)                     # unknown sites get no CORS
        self.assertIn('"http://tauri.localhost"', body)
        self.assertNotIn("*", body)

    def test_cms_sends_few_requests_at_a_time_and_retries_429(self):
        ts = (ROOT / "apps" / "desktop-cms" / "src" / "api" / "adminClient.ts").read_text(encoding="utf-8")
        self.assertIn("const MAX_IN_FLIGHT = 6;", ts)
        self.assertIn("await takeRequestSlot();", ts)
        self.assertIn("releaseRequestSlot();", ts)
        self.assertIn("res.status === 429 && rateLimitRetries < RATE_LIMIT_RETRIES", ts)
        # the stale-session guard stays: a late 401 for an older token never logs out the new session
        self.assertIn("forCurrentSession", ts)

    def test_deploy_recreates_the_proxy(self):
        """The proxy reads nginx.conf through the "current" link, resolved when the
        container is created: v1.0.1 was deployed with the old limits still live."""
        sh = (ROOT / "infrastructure" / "scripts" / "release-deploy.sh").read_text(encoding="utf-8")
        self.assertIn("docker compose up -d --no-deps --force-recreate nginx", sh)
        calls = re.findall(r"^\s*luxe_restart_proxy$", sh, re.M)
        self.assertEqual(len(calls), 2)  # after the switch and after a rollback


if __name__ == "__main__":
    unittest.main()
