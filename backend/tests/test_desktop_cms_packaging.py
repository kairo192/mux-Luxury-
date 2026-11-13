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


if __name__ == "__main__":
    unittest.main()
