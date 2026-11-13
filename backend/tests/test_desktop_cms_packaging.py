"""
The Windows installer of the desktop CMS must work on any laptop:
- the INSTALLED app talks to https://api.mus-luxury.com (it runs at
  http://tauri.localhost on Windows, which must not be mistaken for a developer
  machine pointing at 127.0.0.1:8000);
- it may reach that server (CSP) and the server accepts its origin (CORS);
- WebView2 is installed by the installer when missing, and the C runtime is
  linked into the program (no "VCRUNTIME140.dll was not found").
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMS = ROOT / "apps" / "desktop-cms"
API = "https://api.mus-luxury.com"


class TestDesktopCmsPackaging(unittest.TestCase):
    def test_installed_app_uses_the_production_server(self):
        src = (CMS / "src" / "api" / "adminClient.ts").read_text(encoding="utf-8")
        body = src[src.index("function resolveDefaultApiBaseUrl"):src.index("let apiBaseUrl")]
        dev_check = re.search(r"if \((h === [^)]*)\)", body).group(1)
        self.assertNotIn("tauri.localhost", dev_check, "the installed app would call this PC instead of the server")
        self.assertIn(f'return "{API}/api/v1";', body)
        workflow = (ROOT / ".github" / "workflows" / "build-desktop-cms.yml").read_text(encoding="utf-8")
        self.assertIn(f"VITE_CMS_API_URL: {API}/api/v1", workflow)

    def test_app_may_reach_the_server_and_server_accepts_the_app(self):
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        connect = re.search(r"connect-src ([^;]*)", conf["app"]["security"]["csp"]).group(1).split()
        self.assertIn(API, connect)
        main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"http://tauri.localhost"', main)

    def test_installer_brings_what_a_fresh_laptop_lacks(self):
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        win = conf["bundle"]["windows"]
        self.assertIn(win["webviewInstallMode"]["type"], ("embedBootstrapper", "offlineInstaller"))
        self.assertIn("nsis", conf["bundle"]["targets"])
        self.assertEqual(win["nsis"]["installMode"], "currentUser")       # no admin rights needed
        cargo_cfg = (CMS / "src-tauri" / ".cargo" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("x86_64-pc-windows-msvc", cargo_cfg)
        self.assertIn("+crt-static", cargo_cfg)


    def test_automatic_updates_come_from_the_shop_server_and_are_verified(self):
        """The repository is private: installed apps cannot download GitHub
        release files, so updates are served by mus-luxury.com/downloads/cms."""
        manifest = "https://mus-luxury.com/downloads/cms/latest.json"
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["plugins"]["updater"]["endpoints"], [manifest])
        self.assertIn(f'"{manifest}"', (CMS / "src-tauri" / "src" / "app_services.rs").read_text(encoding="utf-8"))
        self.assertIn(f'"update_manifest": "{manifest}"', (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8"))
        # Public key committed and baked into every build; private key only in CI secrets.
        pub = (CMS / "src-tauri" / "updater-key.pub").read_text(encoding="utf-8").strip()
        self.assertRegex(pub, r"^[A-Za-z0-9+/=]{40,}$")
        workflow = (ROOT / ".github" / "workflows" / "build-desktop-cms.yml").read_text(encoding="utf-8")
        self.assertIn("src-tauri/updater-key.pub", workflow)
        self.assertIn('--base-url "https://mus-luxury.com/downloads/cms"', workflow)
        self.assertIn("publish-to-server:", workflow)
        # Only the updater's files go on the server: no fixed public "download the CMS" link.
        self.assertNotRegex(workflow, r"(cp|mv|scp)[^\n]*MusLuxuryCMS-setup\.exe")
        self.assertNotIn("release/*.msi", workflow)
        # The server serves that folder.
        nginx = (ROOT / "infrastructure" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
        self.assertIn("location /downloads/", nginx)
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("/var/lib/luxe/downloads:ro", compose)
        # No private key material is ever committed.
        self.assertNotIn("PRIVATE KEY", pub)
        self.assertFalse((CMS / "src-tauri" / "updater-key").exists())

    def test_publisher_is_kirodev(self):
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["bundle"]["publisher"], "Kirodev")


if __name__ == "__main__":
    unittest.main()
