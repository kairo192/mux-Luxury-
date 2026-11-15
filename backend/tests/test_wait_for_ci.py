"""
The deploy waits for the CI run of the commit (infrastructure/scripts/wait-for-ci.sh).
A deploy started before CI has even begun must wait, not stop at once (v1.0.0 did).
A fake `gh` replays the CI run states the GitHub API returns, one call after another.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infrastructure" / "scripts" / "wait-for-ci.sh"

FAKE_GH = r"""#!/usr/bin/env bash
# Each call prints the next answer file (the last one repeats).
n=$(cat "$STATE/n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$STATE/n"
f="$STATE/answer$n"; [ -f "$f" ] || f=$(ls "$STATE"/answer* | sort -V | tail -1)
cat "$f"
"""


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class TestWaitForCi(unittest.TestCase):
    def _run(self, *answers, **env_extra):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"; bin_dir.mkdir()
            (bin_dir / "gh").write_text(FAKE_GH, newline="\n")
            for i, a in enumerate(answers, 1):
                (Path(tmp) / f"answer{i}").write_text(a, newline="\n")
            env = dict(os.environ, STATE=tmp.replace("\\", "/"), GITHUB_REPOSITORY="o/r", GH_TOKEN="x",
                       WAIT_INTERVAL="0", **env_extra)
            cmd = f'export PATH="$(cygpath -u "{bin_dir}" 2>/dev/null || echo "{bin_dir}"):$PATH"; ' \
                  f'chmod +x "$(command -v gh)"; bash "$0" abc123'
            r = subprocess.run(["bash", "-c", cmd, str(SCRIPT).replace("\\", "/")], env=env,
                               capture_output=True, text=True, timeout=60)
            calls = int((Path(tmp) / "n").read_text()) if (Path(tmp) / "n").exists() else 0
            return r, calls

    def test_waits_while_ci_has_not_started_then_passes(self):
        r, calls = self._run("", "in_progress -\n", "completed success\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, 3)

    def test_a_failed_ci_blocks_the_deploy(self):
        r, _ = self._run("completed failure\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("without passing", r.stdout)

    def test_a_rerun_that_passed_is_enough(self):
        r, _ = self._run("completed failure\ncompleted success\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_ci_run_at_all_stops_after_the_grace_period(self):
        r, _ = self._run("", NO_RUN_GRACE="0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("No CI run found", r.stdout)


if __name__ == "__main__":
    unittest.main()
