"""
The API is split into app/routers/<area>.py (see docs/architecture/SYSTEM_ARCHITECTURE.md §2b).
These checks keep that layout from drifting back into one big file or into a tangle.
"""
import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
ROUTERS = sorted(p for p in (APP / "routers").glob("*.py") if p.name != "__init__.py")


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            yield node


class TestBackendLayout(unittest.TestCase):
    def test_every_router_is_included_by_main(self):
        main = (APP / "main.py").read_text(encoding="utf-8")
        for r in ROUTERS:
            self.assertIn(f"app.include_router({r.stem}.router)", main, r.name)

    def test_routers_never_import_each_other(self):
        names = {r.stem for r in ROUTERS}
        for r in ROUTERS:
            for imp in _imports(r):
                target = (imp.module or "").split(".")
                bad = (imp.level == 1) or (imp.level == 2 and target[:1] == ["routers"]) \
                    or (imp.level == 1 and target[0] in names)
                # level 1 inside routers/ means "a sibling router" (e.g. a forgotten `from .whatsapp`
                # that should be `from ..whatsapp`): it fails at run time, not at import time.
                self.assertFalse(bad, f"{r.name}:{imp.lineno} imports {'.' * imp.level}{imp.module}")

    def test_main_stays_the_app_assembly(self):
        lines = len((APP / "main.py").read_text(encoding="utf-8").splitlines())
        self.assertLess(lines, 400, "new endpoints belong in app/routers/, not in main.py")
        self.assertNotIn("@app.get(", (APP / "main.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
