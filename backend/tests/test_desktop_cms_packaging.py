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
        release files, so the API serves updates — to logged-in staff only."""
        base = "https://api.mus-luxury.com/api/v1/admin/updates/cms"
        manifest = f"{base}/latest.json"
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["plugins"]["updater"]["endpoints"], [manifest])
        self.assertIn(f'"{manifest}"', (CMS / "src-tauri" / "src" / "app_services.rs").read_text(encoding="utf-8"))
        common = (ROOT / "backend" / "app" / "common.py").read_text(encoding="utf-8")
        self.assertIn(f'CMS_UPDATE_BASE_URL = "{base}"', common)
        # HTTPS only: the updater must never be allowed plain HTTP.
        self.assertNotIn("dangerousInsecureTransportProtocol", json.dumps(conf))
        # Public key committed and baked into every build; private key only in CI secrets.
        pub = (CMS / "src-tauri" / "updater-key.pub").read_text(encoding="utf-8").strip()
        self.assertRegex(pub, r"^[A-Za-z0-9+/=]{40,}$")
        workflow = (ROOT / ".github" / "workflows" / "build-desktop-cms.yml").read_text(encoding="utf-8")
        self.assertIn("src-tauri/updater-key.pub", workflow)
        self.assertIn(f'--base-url "{base}"', workflow)
        self.assertIn("publish-to-server:", workflow)
        # Only the updater's files go on the server: no fixed public "download the CMS" link.
        for m in re.finditer(r"MusLuxuryCMS-setup\.exe", workflow):
            self.assertTrue(workflow[:m.start()].endswith("rm -f "),
                            "a fixed MusLuxuryCMS-setup.exe may only appear to be deleted")
        self.assertNotIn("release/*.msi", workflow)
        # Not on the public website: nginx does not serve the folder, only the API
        # container reads it (and it checks the login, tests/test_cms_updates_access.py).
        nginx = (ROOT / "infrastructure" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
        self.assertNotIn("/downloads/", nginx)
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        api_block = compose[compose.index("\n  api:"):compose.index("\n  nginx:")]
        self.assertIn("${LUXE_DOWNLOADS_DIR:-./downloads}:/var/lib/luxe/updates:ro", api_block)
        self.assertIn("LUXE_UPDATES_DIR: /var/lib/luxe/updates", api_block)
        self.assertEqual(compose.count("LUXE_DOWNLOADS_DIR"), 1)
        # The app sends the staff login with the check AND the download.
        rs = (CMS / "src-tauri" / "src" / "app_services.rs").read_text(encoding="utf-8")
        self.assertIn('.header("Authorization", format!("Bearer {token}"))', rs)
        self.assertEqual(rs.count("logged_in_updater(&app, &token)?"), 2)
        self.assertNotIn("app.updater()", rs)
        # ...and never to another host: the download address is checked before any
        # request (unit test installer_downloads_only_from_the_shop_update_address).
        self.assertIn("ensure_trusted_download(u)?;", rs)
        self.assertIn("ensure_trusted_download(&update)?;", rs)
        self.assertIn('const UPDATE_FILES_HOST: &str = "api.mus-luxury.com";', rs)
        self.assertIn("client.redirect(reqwest::redirect::Policy::none())", rs)   # no redirect followed
        # No private key material is ever committed.
        self.assertNotIn("PRIVATE KEY", pub)
        self.assertFalse((CMS / "src-tauri" / "updater-key").exists())

    def test_publication_uses_the_folder_nginx_serves(self):
        """The workflow asks the server (same function as release-deploy.sh) instead of
        assuming /opt/luxe, and two releases never publish at the same time."""
        import subprocess, shutil, tempfile
        workflow = (ROOT / ".github" / "workflows" / "build-desktop-cms.yml").read_text(encoding="utf-8")
        self.assertIn("infrastructure/scripts/downloads-dir.sh", workflow)
        self.assertIn("group: publish-desktop-cms-server", workflow)
        self.assertNotIn("DEST=/opt/luxe", workflow)
        if not shutil.which("bash"):
            self.skipTest("needs bash")
        scripts = ROOT / "infrastructure" / "scripts"
        helper = (scripts / "compose-project.sh").read_text() + (scripts / "downloads-dir.sh").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "srv"; (root / "shared").mkdir(parents=True)
            env = root / "shared" / ".env"
            env.write_text("APP_ENV=production\n")
            run = lambda: subprocess.run(["bash", "-s", "--", str(root)], input=helper, capture_output=True,
                                         text=True, timeout=30)
            r = run()
            self.assertEqual(r.returncode, 0, r.stderr)
            # Compare as paths: bash joins with "/", Windows paths use "\" (same folder).
            self.assertEqual(Path(r.stdout.strip()), root / "shared" / "downloads")    # default
            self.assertTrue((root / "shared" / "downloads" / "cms").is_dir())
            custom = Path(tmp) / "custom-dl"
            env.write_text(f"APP_ENV=production\nLUXE_DOWNLOADS_DIR={custom}\n")
            r = run()
            self.assertEqual(Path(r.stdout.strip()), custom)                            # configured override
            self.assertTrue((custom / "cms").is_dir())

    def test_setup_script_proves_the_signing_key_matches(self):
        ps1 = (ROOT / "infrastructure" / "scripts" / "setup-github-secrets.ps1").read_text(encoding="utf-8")
        self.assertIn("Assert-KeyMatchesRepo $signKey $signPass $repoPub", ps1)
        self.assertIn("tauri signer sign", ps1)
        # "$name:" inside a PowerShell string is a drive-scoped variable: the script would not start.
        self.assertEqual(re.findall(r'"[^"\n]*\$(?!env:)[A-Za-z_]\w*:[^"\n]*"', ps1), [])

    def test_publisher_is_kirodev(self):
        conf = json.loads((CMS / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["bundle"]["publisher"], "Kirodev")


if __name__ == "__main__":
    unittest.main()
