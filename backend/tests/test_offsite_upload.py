"""
infrastructure/backups/upload_to_offsite.sh: the off-site copy fits a FREE
plan (Backblaze B2 / Cloudflare R2, 10 GB) — standard storage class only, old
database copies deleted after OFFSITE_RETENTION_DAYS, the newest photo
archives always kept — and it fails loudly when misconfigured.

The script runs for real (bash + GNU date); rclone is replaced by a small
stand-in that stores "remote" files in a temporary folder.
"""
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infrastructure" / "backups" / "upload_to_offsite.sh"

FAKE_RCLONE = textwrap.dedent('''\
    #!{python}
    import os, shutil, sys
    from pathlib import Path
    root = Path(os.environ["FAKE_REMOTE_ROOT"])
    with open(root / "_calls.log", "a") as log:
        log.write(" ".join(sys.argv[1:]) + "\\n")
    args, it = [], iter(sys.argv[1:])
    for a in it:
        if a in ("--retries", "--low-level-retries", "--contimeout", "--timeout"):
            next(it)
        elif not a.startswith("-"):
            args.append(a)
    def local(remote):
        assert remote.startswith("offsite:"), remote
        return root / "store" / remote[len("offsite:"):]
    cmd = args[0]
    if cmd == "copyto":
        dst = local(args[2]); dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args[1], dst)
    elif cmd == "lsf":
        base = local(args[1])
        for p in sorted(base.rglob("*")):
            if p.is_file():
                print(p.relative_to(base).as_posix())
    elif cmd == "deletefile":
        local(args[1]).unlink()
    else:
        sys.exit("unexpected rclone command: " + cmd)
''')


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash"), "needs bash + GNU date")
class TestOffsiteUpload(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"; self.bin.mkdir()
        rclone = self.bin / "rclone"
        rclone.write_text(FAKE_RCLONE.format(python=sys.executable))
        rclone.chmod(0o755)
        self.remote = self.tmp / "remote"; (self.remote / "store").mkdir(parents=True)
        self.backups = self.tmp / "backups"; self.backups.mkdir()
        self.base = self.remote / "store" / "shop-backups" / "luxe" / "testhost"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("S3_", "OFFSITE_", "BACKUP_"))}
        env.update({
            "PATH": f"{self.bin}:{env.get('PATH', '/usr/bin:/bin')}",
            "FAKE_REMOTE_ROOT": str(self.remote), "HOSTNAME": "testhost", "BACKUP_DIR": str(self.backups),
            "S3_BACKUP_ENABLED": "true", "S3_ENDPOINT_URL": "https://s3.eu-central-003.backblazeb2.com",
            "S3_REGION": "eu-central-003", "S3_BUCKET_NAME": "shop-backups",
            "S3_ACCESS_KEY_ID": "key-id", "S3_SECRET_ACCESS_KEY": "secret-value",
        })
        env.update(extra)
        return env

    def _run(self, **extra):
        return subprocess.run(["bash", str(SCRIPT)], env=self._env(**extra), capture_output=True, text=True, timeout=60)

    def _put_remote(self, days_ago, name_pattern):
        t = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)
        p = self.base / t.strftime("%Y/%m/%d") / name_pattern.replace("TS", t.strftime("%Y%m%d_020000"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p.relative_to(self.base).as_posix()

    def _make_local_backup(self):
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
        names = [f"luxe_db_{ts}.sql.gz.enc", f"luxe_app_{ts}.json.gz.enc"]
        for n in names:
            (self.backups / n).write_text(n)
        (self.backups / f"luxe_backup_{ts}.sha256").write_text("".join(f"0000  {n}\n" for n in names))
        return names + [f"luxe_backup_{ts}.sha256"]

    def _remote_files(self):
        return sorted(p.relative_to(self.base).as_posix() for p in self.base.rglob("*") if p.is_file())

    def test_uploads_last_backup_and_keeps_storage_small(self):
        old_db = self._put_remote(60, "luxe_db_TS.sql.gz.enc")
        old_sha = self._put_remote(60, "luxe_backup_TS.sha256")
        recent_db = self._put_remote(5, "luxe_db_TS.sql.gz.enc")
        media = [self._put_remote(d, "luxe_media_TS.tar.gz.enc") for d in (400, 300, 200, 100, 2)]
        (self.base / "README.txt").write_text("not a backup")
        uploaded = self._make_local_backup()

        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = self._remote_files()
        for name in uploaded:
            self.assertTrue(any(f.endswith("/" + name) for f in files), name)
        self.assertNotIn(old_db, files)
        self.assertNotIn(old_sha, files)
        self.assertIn(recent_db, files)
        # newest 3 photo archives kept whatever their age (photos may not change for months)
        self.assertEqual([m for m in media if m in files], media[2:])
        self.assertIn("README.txt", files)
        calls = (self.remote / "_calls.log").read_text()
        self.assertNotIn("STANDARD_IA", calls)            # free plans cover the standard class only
        self.assertNotIn("secret-value", r.stdout + r.stderr)

    def test_retention_and_media_keep_follow_the_settings(self):
        db = self._put_remote(10, "luxe_db_TS.sql.gz.enc")
        media = [self._put_remote(d, "luxe_media_TS.tar.gz.enc") for d in (50, 3)]
        self._make_local_backup()
        r = self._run(OFFSITE_RETENTION_DAYS="7", BACKUP_MEDIA_KEEP="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = self._remote_files()
        self.assertNotIn(db, files)
        self.assertEqual([m for m in media if m in files], media[1:])

    def test_switched_off_does_nothing(self):
        self._make_local_backup()
        r = self._run(S3_BACKUP_ENABLED="false")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.remote / "_calls.log").exists())

    def test_missing_or_placeholder_key_fails_loudly(self):
        self._make_local_backup()
        for value in ("", "<FILL_IN_s3_key>"):
            with self.subTest(value=value):
                r = self._run(S3_ACCESS_KEY_ID=value)
                self.assertEqual(r.returncode, 2)
                self.assertIn("S3_ACCESS_KEY_ID", r.stderr)

    def test_failed_upload_fails_loudly(self):
        self._make_local_backup()
        (self.bin / "rclone").write_text("#!/bin/sh\nexit 1\n")
        r = self._run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no file uploaded", r.stderr)


if __name__ == "__main__":
    unittest.main()
