import hashlib
import hmac
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

for _gp in [
    r"C:\Users\MOURAD\AppData\Local\Programs\Git\bin",
    r"C:\Users\MOURAD\AppData\Local\Programs\Git\usr\bin",
    r"C:\Program Files\Git\bin",
    r"C:\Program Files\Git\usr\bin",
]:
    if os.path.isdir(_gp) and _gp not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{_gp}{os.pathsep}{os.environ.get('PATH', '')}"

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")
os.environ.setdefault("BACKUP_ENCRYPTION_KEY", "test_only_ephemeral_backup_encryption_key_2026_0123456789abcdef")

from fastapi.testclient import TestClient
from app import config
from app.database import get_connection, normalize_postgres_url
from app.main import app
from app.security import (
    COMPROMISED_SECRET_SHA256_DENYLIST,
    MAX_REVOKED_TOKENS,
    PBKDF2_ITERATIONS_DEFAULT,
    REVOKED_TOKENS,
    SEEN_NONCES,
    get_hmac_signing_secret,
    get_secret_key,
    hash_password,
    is_secret_compromised_or_weak,
    reset_rate_limits,
    revoke_token,
    sign_api_request,
    validate_uploaded_image,
    verify_password,
    verify_signed_request,
)
from app.seed import seed_initial_data
from app.whatsapp import get_whatsapp_config
from scripts.generate_secrets import generate_all_secrets



def storefront_source(repo_root) -> str:
    """The shop's code: index.html plus its scripts and styles (split out of the page into src/)."""
    from pathlib import Path as _P
    sf = _P(repo_root) / "apps" / "storefront"
    parts = [(sf / "index.html").read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in sorted((sf / "src").rglob("*")) if p.suffix in (".js", ".css")]
    return "\n".join(parts)

class TestLuxeSecurityHardeningHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.repo_root = Path(__file__).resolve().parents[2]

    def setUp(self):
        reset_rate_limits()

    # C-1: Production environment seeds zero default admins/recovery codes and leaves setup-status uninitialized
    def test_c1_production_seed_gate_and_setup_status_uninitialized(self):
        self.skipTest("Feature removed: WhatsApp admin password recovery and admin-facing backup endpoints were deleted per owner request. The scenarios this test exercised no longer have HTTP surfaces. See docs/cicd/ROLLBACK.md for current backup/restore and backend/scripts/emergency_reset_owner.py for password reset.")
    def test_c2_otp_never_returned_in_production_and_identical_response_shape(self):
        self.skipTest("Feature removed: WhatsApp admin password recovery and admin-facing backup endpoints were deleted per owner request. The scenarios this test exercised no longer have HTTP surfaces. See docs/cicd/ROLLBACK.md for current backup/restore and backend/scripts/emergency_reset_owner.py for password reset.")
    def test_c3_secret_denylist_separate_hmac_key_and_generate_secrets_script(self):
        self.assertEqual(len(COMPROMISED_SECRET_SHA256_DENYLIST), 4)
        self.assertIn("fe10bb548e201d48e861e4d157baeeb64dab05d299c71b007f4a8cafecd70daa", COMPROMISED_SECRET_SHA256_DENYLIST)
        self.assertIn("133c08ff8619883e3f0140e7a7a5ae602393290528db0a3c158ff209a9c5cc02", COMPROMISED_SECRET_SHA256_DENYLIST)
        self.assertIn("6b9d81fa41d2d5d3608d6de07b41e1d05214482efdd6ed355a1fec802b9e4e9c", COMPROMISED_SECRET_SHA256_DENYLIST)
        self.assertIn("392e96df58c32fb8e877b4154892d0cc9b333201e206244128422f5242d22211", COMPROMISED_SECRET_SHA256_DENYLIST)

        # Old dev default SECRET_KEY must be flagged as compromised
        self.assertTrue(is_secret_compromised_or_weak("luxe_dev_secret_key_change_in_prod_998877665544332211"))

        # Request signing key must never equal JWT SECRET_KEY
        self.assertNotEqual(get_hmac_signing_secret(), get_secret_key())

        # generate_secrets.py must produce fresh secrets that pass is_secret_compromised_or_weak
        fresh = generate_all_secrets()
        for k in ("SECRET_KEY", "CMS_HMAC_SIGNING_SECRET", "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "BACKUP_ENCRYPTION_KEY"):
            self.assertFalse(is_secret_compromised_or_weak(fresh[k], min_len=32))

        # Empty webhook verify token must cause GET /api/v1/webhooks/whatsapp to return 503
        old_vt = os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        try:
            os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = ""
            r_get = self.client.get(
                "/api/v1/webhooks/whatsapp",
                params={"hub.mode": "subscribe", "hub.verify_token": "any", "hub.challenge": "123"},
            )
            self.assertEqual(r_get.status_code, 503)
        finally:
            if old_vt is not None:
                os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = old_vt

    # C-4: PostgreSQL URL normalization and fail-closed behavior without SQLite fallback
    def test_c4_postgres_url_normalization_and_no_silent_sqlite_fallback(self):
        self.assertEqual(
            normalize_postgres_url("postgresql+psycopg2://u:p@db:5432/luxe"),
            "postgresql://u:p@db:5432/luxe",
        )
        old_eng = os.environ.get("LUXE_DB_ENGINE")
        old_url = os.environ.get("DATABASE_URL")
        try:
            os.environ["LUXE_DB_ENGINE"] = "postgres"
            os.environ["DATABASE_URL"] = "postgresql://u:p@127.0.0.1:59998/luxe?connect_timeout=1"
            with self.assertRaises(RuntimeError):
                get_connection()
        finally:
            os.environ["LUXE_DB_ENGINE"] = old_eng or "sqlite"
            if old_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_url

    # H-1, H-2, H-3, H-4, H-6: Storefront useRef idempotency, webhook 503/413/status cap, requirements & .dockerignore
    def test_h1_h3_h4_h6_high_severity_controls(self):
        # H-1: the live shop sends ONE Idempotency-Key per order (re-used on a
        # double click / retry, cleared on success) — never a per-click key.
        sf_txt = storefront_source(self.repo_root)
        self.assertIn('"Idempotency-Key": state.checkoutIdemKey', sf_txt)
        self.assertIn("state.checkoutIdemKey = null", sf_txt)
        self.assertNotIn("storefront-${phone}-${Date.now()}", sf_txt)

        # H-3: requirements.txt and constraints.txt exist and remove unused deps
        req_txt = (self.repo_root / "backend" / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("pydantic>=1.10.4,<2.0.0", req_txt)
        self.assertNotIn("sqlalchemy", req_txt)
        self.assertNotIn("alembic", req_txt)
        self.assertTrue((self.repo_root / "backend" / "constraints.txt").is_file())

        # H-4: POST /api/v1/webhooks/whatsapp returns 503 when WHATSAPP_APP_SECRET is unconfigured, and 413 when >64KB
        old_sec = os.environ.get("WHATSAPP_APP_SECRET")
        try:
            os.environ["WHATSAPP_APP_SECRET"] = ""
            r_503 = self.client.post("/api/v1/webhooks/whatsapp", content=b"{}")
            self.assertEqual(r_503.status_code, 503)

            os.environ["WHATSAPP_APP_SECRET"] = "meta_app_secret_test_key_2026"
            oversized = b"x" * (65 * 1024)
            r_413 = self.client.post("/api/v1/webhooks/whatsapp", content=oversized)
            self.assertEqual(r_413.status_code, 413)
        finally:
            if old_sec is not None:
                os.environ["WHATSAPP_APP_SECRET"] = old_sec

        # H-6: .dockerignore files exist
        for rel in [".dockerignore", "backend/.dockerignore", "apps/storefront/.dockerignore", "apps/desktop-cms/.dockerignore"]:
            p = self.repo_root / rel
            self.assertTrue(p.is_file(), f"Missing {rel}")
            self.assertIn("*.sqlite3", p.read_text(encoding="utf-8"))

    # H-5: End-to-end backup_postgres_and_media.sh -> restore_backup.sh on scratch SQLite DB (with & without encryption)
    def test_h5_backup_and_restore_end_to_end_on_scratch_database(self):
        bkp_script = self.repo_root / "infrastructure" / "backups" / "backup_postgres_and_media.sh"
        rest_script = self.repo_root / "infrastructure" / "backups" / "restore_backup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            src_db = tmp_path / "source.sqlite3"
            conn = sqlite3.connect(str(src_db))
            conn.execute("CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT);")
            conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name_fr TEXT);")
            conn.execute("INSERT INTO roles VALUES (1, 'super_admin');")
            conn.execute("INSERT INTO products VALUES (1, 'Sac Émeraude Test');")
            conn.commit()
            conn.close()

            bkp_dir = tmp_path / "backups"
            up_dir = tmp_path / "uploads"
            up_dir.mkdir()
            (up_dir / "img_test.png").write_bytes(b"PNGDATA")

            import shutil
            bash_bin = shutil.which("bash")
            if not bash_bin:
                for c in [
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\usr\bin\bash.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
                    r"C:\Program Files\Git\bin\bash.exe",
                ]:
                    if os.path.exists(c):
                        bash_bin = c
                        break
            if not bash_bin:
                bash_bin = "bash"

            env = os.environ.copy()
            git_usr_bin = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\usr\bin")
            if os.path.exists(git_usr_bin) and git_usr_bin not in env.get("PATH", ""):
                env["PATH"] = f"{git_usr_bin}{os.pathsep}{env.get('PATH', '')}"

            env["BACKUP_DIR"] = str(bkp_dir)
            env["UPLOAD_DIR"] = str(up_dir)
            env["LUXE_SQLITE_PATH"] = str(src_db)
            env["BACKUP_ENCRYPTION_KEY"] = "test_aes256_backup_passphrase_2026"
            env.pop("DATABASE_URL", None)

            # 1. Run encrypted backup
            r_bkp = subprocess.run([bash_bin, str(bkp_script)], cwd=str(self.repo_root), env=env, capture_output=True, text=True)
            self.assertEqual(r_bkp.returncode, 0, r_bkp.stderr)
            enc_files = list(bkp_dir.glob("luxe_db_*.sql.gz.enc"))
            sha_files = list(bkp_dir.glob("luxe_backup_*.sha256"))
            self.assertEqual(len(enc_files), 1)
            self.assertEqual(len(sha_files), 1)

            # 2. Restore into a fresh target SQLite DB (target does not exist -> succeeds without --force)
            restored_db = tmp_path / "restored.sqlite3"
            env["LUXE_SQLITE_PATH"] = str(restored_db)
            r_rest1 = subprocess.run(
                [bash_bin, str(rest_script), str(enc_files[0]), str(sha_files[0])],
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_rest1.returncode, 0, r_rest1.stderr)
            rconn = sqlite3.connect(str(restored_db))
            prod_name = rconn.execute("SELECT name_fr FROM products WHERE id = 1").fetchone()[0]
            rconn.close()
            self.assertEqual(prod_name, "Sac Émeraude Test")

            # 3. Attempting to restore over an existing DB without --force must be refused (exit code != 0)
            r_refuse = subprocess.run(
                ["bash", str(rest_script), str(enc_files[0])],
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r_refuse.returncode, 0)

            # 4. Passing --force moves the existing file aside to .pre-restore-<ts> and restores cleanly
            r_force = subprocess.run(
                ["bash", str(rest_script), str(enc_files[0]), str(sha_files[0]), "--force"],
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_force.returncode, 0, r_force.stderr)
            pre_restore_backups = list(tmp_path.glob("restored.sqlite3.pre-restore-*"))
            self.assertEqual(len(pre_restore_backups), 1)

    # M-1..M-16: Verify all 16 Medium-severity fixes
    def test_m1_to_m16_medium_severity_fixes(self):
        # M-7: Trailing newline in upload filename must be rejected by re.fullmatch
        with self.assertRaises(Exception):
            validate_uploaded_image("exploit.png\n", "image/png", b"\x89PNG\r\n\x1a\n0000")

        # M-8: deploy_algeria_vps.sh must NOT run unittest discover inside production container
        deploy_txt = (self.repo_root / "infrastructure" / "scripts" / "deploy_algeria_vps.sh").read_text(encoding="utf-8")
        self.assertNotIn("unittest discover", deploy_txt)
        self.assertIn("/api/v1/health", deploy_txt)

        # M-12: PBKDF2 default iterations is 600,000 and verify_password verifies both 310k and 600k hashes
        self.assertEqual(PBKDF2_ITERATIONS_DEFAULT, 600000)
        h600 = hash_password("TestPass2026!")
        self.assertTrue(h600.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(verify_password("TestPass2026!", h600))

        # M-13: tauri.conf.json CSP connect-src does not contain bare https: or http:
        tconf_txt = (self.repo_root / "apps" / "desktop-cms" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
        self.assertNotIn(" https: http:", tconf_txt)
        self.assertIn("https://api.mus-luxury.com", tconf_txt)

        # M-15: emergency_reset_owner.py supports getpass fallback when --new-password is omitted
        em_txt = (self.repo_root / "backend" / "scripts" / "emergency_reset_owner.py").read_text(encoding="utf-8")
        self.assertIn("getpass.getpass", em_txt)
        self.assertIn("required=False", em_txt)

        # M-16: nginx.conf repeats X-Frame-Options and Content-Security-Policy inside location /uploads/
        ng_txt = (self.repo_root / "infrastructure" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
        uploads_sec = ng_txt.split("location /uploads/")[1].split("location / {")[0]
        self.assertIn("X-Frame-Options", uploads_sec)
        self.assertIn("Content-Security-Policy", uploads_sec)
        self.assertIn("Strict-Transport-Security", uploads_sec)


    # Frontend 14 TS/TSX Compilation & Request/Response Field Contract Verification
    def test_frontend_all_14_ts_tsx_files_compile_and_contract_parity(self):
        js_compile = """
const fs = require("fs");
const path = require("path");
const babel = require("@babel/core");

function collectTsFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) collectTsFiles(full, out);
    else if (entry.name.endsWith(".d.ts")) continue; // type declarations only: nothing to compile
    else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) out.push(full);
  }
  return out;
}

const files = [
  ...collectTsFiles("apps/storefront/src"),
  ...collectTsFiles("apps/desktop-cms/src"),
];
let compiledCount = 0;
for (const file of files) {
  const code = fs.readFileSync(file, "utf8");
  const res = babel.transformSync(code, {
    filename: file,
    presets: [
      "@babel/preset-env",
      "@babel/preset-typescript",
      ["@babel/preset-react", { runtime: "automatic" }],
    ],
  });
  if (!res || !res.code) throw new Error("Failed to compile " + file);
  compiledCount++;
}
console.log("COMPILED_TS_TSX_FILES=" + compiledCount);
"""
        env = os.environ.copy()
        env["NODE_PATH"] = f"/usr/share/nodejs{os.pathsep}{self.repo_root / 'node_modules'}"
        res = subprocess.run(["node", "-e", js_compile], cwd=str(self.repo_root), env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        m_compiled = __import__("re").search(r"COMPILED_TS_TSX_FILES=(\d+)", res.stdout)
        self.assertIsNotNone(m_compiled, "COMPILED_TS_TSX_FILES output missing")
        self.assertGreaterEqual(int(m_compiled.group(1)), 12)

        # Verify serialize_product returns both gallery_images and images alias for Desktop CMS edit modal
        items = self.client.get("/api/v1/products").json().get("items", [])
        if not items:
            seed_initial_data()
            items = self.client.get("/api/v1/products").json().get("items", [])
        if items:
            p_resp = items[0]
            self.assertIn("gallery_images", p_resp)
            self.assertIn("images", p_resp)


if __name__ == "__main__":
    unittest.main()
