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

from app.database import db_session
from app.main import app, _client_ts_to_utc_text, _csv_date, _shop_day_of, _utc_range_for_days
from app.seed import seed_initial_data
from app.security import reset_rate_limits


class TestShopTimezone(unittest.TestCase):
    """Times are stored in UTC; days in reports are the shop's (Algeria, UTC+1)."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/admin/auth/login", json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()

    def test_01_helpers(self):
        self.assertEqual(_utc_range_for_days("2026-03-10", "2026-03-10"), ("2026-03-09 23:00:00", "2026-03-10 23:00:00"))
        self.assertEqual(_shop_day_of("2026-03-09 23:30:00"), "2026-03-10")
        self.assertEqual(_shop_day_of("2026-03-09 22:59:59.999"), "2026-03-09")
        self.assertEqual(_shop_day_of("2026-03-09 23"), "2026-03-10")  # hour bucket
        self.assertEqual(_csv_date("2026-03-09 23:30:00"), "2026-03-10 00:30")
        self.assertEqual(_csv_date("2026-03-09"), "2026-03-09")  # plain dates unchanged
        # offline POS sale times are stored in one comparable UTC form
        self.assertEqual(_client_ts_to_utc_text("2026-03-09T23:30:00"), "2026-03-09 23:30:00")
        self.assertEqual(_client_ts_to_utc_text("2026-03-09T23:30:00.123Z"), "2026-03-09 23:30:00")
        self.assertEqual(_client_ts_to_utc_text("2026-03-10T00:30:00+01:00"), "2026-03-09 23:30:00")
        self.assertIsNone(_client_ts_to_utc_text("hier soir"))

    def test_02_late_night_movement_counts_on_the_shop_day(self):
        tag = uuid.uuid4().hex[:6]
        r = self.client.post("/api/v1/admin/treasury/movements", headers=self.headers, json={
            "account_type": "cash_box", "movement_type": "inflow", "amount_dzd": 777,
            "description": f"Nuit {tag}", "source_reference": f"tz-{tag}"})
        self.assertIn(r.status_code, (200, 201), r.text)
        # 00:30 in Algiers on 10 March 2026 = 23:30 UTC on 9 March.
        with db_session(commit=True) as conn:
            conn.cursor().execute(
                "UPDATE cash_movements SET created_at = ? WHERE id = ?",
                ("2026-03-09 23:30:00", r.json()["movement_id"]))

        def report(day):
            return self.client.get("/api/v1/admin/reports/treasury", headers=self.headers,
                                   params={"from": day, "to": day}).json()

        on_day = report("2026-03-10")
        refs = {m.get("source_reference") for m in on_day["movements"]} if "movements" in on_day else None
        self.assertEqual(on_day["totals"]["inflow_dzd"] >= 777, True)
        if refs is not None:
            self.assertIn(f"tz-{tag}", refs)
        self.assertIn("2026-03-10", [d["day"] for d in on_day["by_day"]])
        prev = report("2026-03-09")
        self.assertNotIn("2026-03-10", [d["day"] for d in prev["by_day"]])
        if "movements" in prev:
            self.assertNotIn(f"tz-{tag}", {m.get("source_reference") for m in prev["movements"]})

        csv = self.client.get("/api/v1/admin/reports/treasury.csv", headers=self.headers,
                              params={"from": "2026-03-10", "to": "2026-03-10"}).text
        self.assertIn("2026-03-10 00:30", csv)


if __name__ == "__main__":
    unittest.main()
