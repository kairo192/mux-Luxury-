import os
import socket
import tempfile
import threading
import unittest

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


class TestDevices(unittest.TestCase):
    """Device registry: CRUD, default selection, and honest test results."""

    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        login = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@musluxury.dz", "password": "MusLuxury2026!"},
        )
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        editor = cls.client.post(
            "/api/v1/admin/auth/login",
            json={"email": "editor@musluxury.dz", "password": "EditorLuxury2026!"},
        )
        cls.editor_headers = {"Authorization": f"Bearer {editor.json()['access_token']}"}

    def setUp(self):
        reset_rate_limits()

    def _create(self, **over):
        body = {
            "name": "Imprimante caisse",
            "device_type": "receipt_printer",
            "connection_type": "windows",
            "config": {"windows_printer_name": "POS-80", "paper_width_mm": 80},
            "capabilities": ["text", "cut"],
            "location": "Caisse 1",
        }
        body.update(over)
        r = self.client.post("/api/v1/admin/devices", headers=self.headers, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    # ------------------------------------------------------------------ tests
    def test_01_create_and_list(self):
        dev = self._create()
        self.assertEqual(dev["status"], "unknown")  # never fabricated on creation
        self.assertEqual(dev["config"]["paper_width_mm"], 80)
        self.assertIn("text", dev["capabilities"])
        lst = self.client.get("/api/v1/admin/devices", headers=self.headers)
        self.assertTrue(any(d["id"] == dev["id"] for d in lst.json()["items"]))

    def test_02_single_default_per_type(self):
        a = self._create(name="Printer A", is_default=True)
        b = self._create(name="Printer B")
        self.assertTrue(a["is_default"])
        self.client.post(f"/api/v1/admin/devices/{b['id']}/set-default", headers=self.headers)
        items = {d["id"]: d for d in self.client.get("/api/v1/admin/devices", headers=self.headers).json()["items"]}
        self.assertFalse(items[a["id"]]["is_default"])
        self.assertTrue(items[b["id"]]["is_default"])

    def test_03_network_requires_host_port(self):
        bad = self.client.post("/api/v1/admin/devices", headers=self.headers, json={
            "name": "Net printer", "device_type": "receipt_printer", "connection_type": "network", "config": {"host": "192.168.1.50"},
        })
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_04_network_test_probe_reachable_and_unreachable(self):
        # Spin up a real listening socket; the probe must reach it.
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            dev = self._create(name="Net OK", connection_type="network", config={"host": "127.0.0.1", "port": port})
            res = self.client.post(f"/api/v1/admin/devices/{dev['id']}/test", headers=self.headers, json={})
            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual(res.json()["status"], "ok")
            self.assertEqual(res.json()["test_method"], "tcp_probe")
        finally:
            srv.close()
        # Now the port is closed → probe must report an error, not a fabricated ok.
        res2 = self.client.post(f"/api/v1/admin/devices/{dev['id']}/test", headers=self.headers, json={})
        self.assertEqual(res2.json()["status"], "error")
        self.assertIsNotNone(res2.json()["last_error"])

    def test_05_non_network_without_signal_stays_unknown(self):
        dev = self._create(name="USB scanner", device_type="barcode_scanner", connection_type="usb", config={})
        res = self.client.post(f"/api/v1/admin/devices/{dev['id']}/test", headers=self.headers, json={})
        self.assertEqual(res.json()["status"], "unknown")  # not fabricated
        self.assertEqual(res.json()["test_method"], "unavailable")
        # Local bridge reports success → honest 'ok'
        res2 = self.client.post(f"/api/v1/admin/devices/{dev['id']}/test", headers=self.headers, json={"success": True, "capabilities": ["hid"]})
        self.assertEqual(res2.json()["status"], "ok")
        self.assertIn("hid", res2.json()["capabilities"])

    def test_06_update_and_delete(self):
        dev = self._create()
        up = self.client.put(f"/api/v1/admin/devices/{dev['id']}", headers=self.headers, json={"location": "Caisse 2", "config": {"windows_printer_name": "POS-58", "paper_width_mm": 58}})
        self.assertEqual(up.status_code, 200, up.text)
        self.assertEqual(up.json()["location"], "Caisse 2")
        self.assertEqual(up.json()["config"]["paper_width_mm"], 58)
        dele = self.client.delete(f"/api/v1/admin/devices/{dev['id']}", headers=self.headers)
        self.assertEqual(dele.status_code, 200, dele.text)
        gone = self.client.get("/api/v1/admin/devices", headers=self.headers)
        self.assertFalse(any(d["id"] == dev["id"] for d in gone.json()["items"]))

    def test_07_invalid_type(self):
        bad = self.client.post("/api/v1/admin/devices", headers=self.headers, json={
            "name": "x", "device_type": "teleporter", "connection_type": "usb",
        })
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_08_permissions(self):
        # product_manager lacks devices:write
        r = self.client.post("/api/v1/admin/devices", headers=self.editor_headers, json={
            "name": "x", "device_type": "receipt_printer", "connection_type": "usb",
        })
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self.client.get("/api/v1/admin/devices").status_code, 401)


if __name__ == "__main__":
    unittest.main()
