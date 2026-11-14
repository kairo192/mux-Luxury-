"""Write docs/api/openapi.json and docs/api/ENDPOINTS.md from the running app's routes.

    cd backend && python3 scripts/generate_api_docs.py          # write the files
    cd backend && python3 scripts/generate_api_docs.py --check  # exit 1 if they are out of date

tests/test_api_docs.py runs the check, so the API docs always match the code.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DOCS = BACKEND.parent / "docs" / "api"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _p = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _p
os.environ.setdefault("SECRET_KEY", "docs_generation_only_ephemeral_secret_key_0123456789abcdef0123")


def _access(route) -> str:
    """Who may call the route: public, any staff login, or the permission(s) it requires."""
    from app.deps import get_current_admin
    needs = []
    for d in getattr(route, "dependant", None).dependencies if hasattr(route, "dependant") else []:
        call = d.call
        if call is get_current_admin:
            needs.append("staff login")
            continue
        cells = [c.cell_contents for c in (getattr(call, "__closure__", None) or [])]
        for v in cells:
            if isinstance(v, str):
                needs.append(f"`{v}`")
            elif isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v):
                needs.append(" or ".join(f"`{x}`" for x in v))
    return ", ".join(dict.fromkeys(needs)) or "public"


def build():
    from app.main import app
    spec = json.dumps(app.openapi(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    rows = {}
    for r in app.routes:
        if not hasattr(r, "endpoint") or not getattr(r, "methods", None):
            continue
        mod = r.endpoint.__module__.replace("app.routers.", "routers/").replace("app.", "")
        if mod in ("fastapi.applications",):
            continue
        for m in sorted(r.methods - {"HEAD"}):
            rows.setdefault(mod, []).append((r.path, m, _access(r), r.endpoint.__name__))
    total = sum(len(v) for v in rows.values())
    md = ["# API endpoints (generated)", "",
          "Generated from the code by `backend/scripts/generate_api_docs.py`; a test fails when it is out of date,",
          "so do not edit by hand. Request and response shapes: `openapi.json` (same folder). What the main",
          "endpoints do, with examples: `API_INVENTORY.md` and `API_CONTRACT.md`.", "",
          f"{total} endpoints. *Access*: public, any staff login, or the permission a staff role must have.", ""]
    for mod in sorted(rows, key=lambda m: (not m.startswith("routers/public"), m)):
        md += [f"## `backend/app/{mod}.py`", "", "| Method | Path | Access | Function |", "|---|---|---|---|"]
        md += [f"| {m} | `{p}` | {a} | `{fn}` |" for p, m, a, fn in rows[mod]] + [""]
    return {"openapi.json": spec, "ENDPOINTS.md": "\n".join(md)}


def main(check: bool) -> int:
    stale = []
    for name, text in build().items():
        path = DOCS / name
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            DOCS.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if stale:
        print("out of date:", ", ".join(f"docs/api/{n}" for n in stale), "— run: cd backend && python3 scripts/generate_api_docs.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
