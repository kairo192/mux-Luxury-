"""Languages of the desktop CMS (French, English, Arabic).

- every message the server can send to people has its three versions;
- the server answers in the language the CMS asks for (X-Luxe-Lang), and
  leaves other clients (the online shop) untouched;
- every text key the CMS uses exists in the three languages;
- every audited action and item type has a name in the three languages."""
import ast
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from fastapi.testclient import TestClient

from app.i18n_messages import MESSAGES, localize, request_lang
from app.main import app
from app.routers.reports import _AUDIT_ACTION_FR, _AUDIT_ENTITY_FR
from app.security import reset_rate_limits
from app.seed import seed_initial_data

BACKEND = Path(__file__).resolve().parents[1]
CMS_SRC = BACKEND.parent / "apps" / "desktop-cms" / "src"
PLACEHOLDER = re.compile(r"\{\d+\}")


def _template(node):
    """Text of a string / f-string, with {0}, {1}… for the values put in."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts, n = [], 0
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v.value)
            else:
                parts.append("{%d}" % n)
                n += 1
        return "".join(parts)
    return None


def _server_messages():
    """Every literal HTTPException detail and BackupError message in the code."""
    found = set()
    for f in (BACKEND / "app").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            name = getattr(n.func, "id", getattr(n.func, "attr", ""))
            if name == "HTTPException":
                for kw in n.keywords:
                    if kw.arg == "detail":
                        t = _template(kw.value)
                        if t is not None:
                            found.add(t)
            elif name == "BackupError" and n.args:
                t = _template(n.args[0])
                if t is not None:
                    found.add(t)
    return found


def _area_entries(name):
    """{key: [fr, en, ar]} of a CMS area dictionary (src/i18n/areas/<name>.ts)."""
    text = (CMS_SRC / "i18n" / "areas" / f"{name}.ts").read_text(encoding="utf-8")
    return {m.group(1): json.loads("[" + m.group(2) + "]") for m in re.finditer(r'^  "([^"]+)": \[(.*)\],$', text, re.M)}


def _cms_dictionaries():
    """Keys of the CMS in each language: translations.ts blocks + area files."""
    text = (CMS_SRC / "i18n" / "translations.ts").read_text(encoding="utf-8")
    langs = {}
    for lang in ("fr", "en", "ar"):
        i = text.index(f"const {lang}: Dict = {{")
        j = text.index("\n};", i)
        langs[lang] = set(re.findall(r'^\s*"([^"]+)":', text[i:j], re.M))
    for f in (CMS_SRC / "i18n" / "areas").glob("*.ts"):
        if f.stem in ("define", "index"):
            continue
        area = re.search(r'defineArea\("([^"]+)"', f.read_text(encoding="utf-8")).group(1)
        for key, triple in _area_entries(f.stem).items():
            for lang, value in zip(("fr", "en", "ar"), triple):
                if value:
                    langs[lang].add(f"{area}.{key}")
    return langs


class TestServerMessages(unittest.TestCase):
    def test_every_server_message_has_three_languages(self):
        known = {src for src, *_ in MESSAGES}
        missing = sorted(_server_messages() - known)
        self.assertEqual(missing, [], "add these messages to app/i18n_messages.py (fr / en / ar)")
        for src, fr, en, ar in MESSAGES:
            ph = set(PLACEHOLDER.findall(src))
            for text in (fr or src, en, ar):
                self.assertTrue(text and text.strip(), src)
                self.assertLessEqual(set(PLACEHOLDER.findall(text)), ph, f"unknown value in: {text}")
            self.assertRegex(ar, r"[؀-ۿ]", f"Arabic version is not Arabic: {ar}")

    def test_values_are_carried_over(self):
        text, known = localize("Stock insuffisant pour 'Sac (Noir / M)' : demandé 3, disponible 1", "en")
        self.assertTrue(known)
        self.assertEqual(text, "Not enough stock for 'Sac (Noir / M)': 3 asked, 1 available")
        self.assertEqual(localize("Produit introuvable", "ar"), ("المنتج غير موجود", True))
        self.assertEqual(localize("Invalid email or password", "fr")[0], "Adresse e-mail ou mot de passe incorrect.")
        self.assertEqual(localize("not a known message", "ar"), ("not a known message", False))
        self.assertEqual(request_lang("AR"), "ar")
        self.assertIsNone(request_lang("de"))
        self.assertIsNone(request_lang(None))


class TestApiLanguage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_initial_data()
        cls.client = TestClient(app)
        reset_rate_limits()
        login = cls.client.post("/api/v1/admin/auth/login",
                                json={"email": "admin@mus-luxury.com", "password": "MusLuxury2026!"})
        assert login.status_code == 200, login.text
        cls.auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _missing_customer(self, lang=None):
        headers = dict(self.auth)
        if lang:
            headers["X-Luxe-Lang"] = lang
        return self.client.get("/api/v1/admin/customers/987654321", headers=headers)

    def test_errors_follow_the_cms_language(self):
        r = self._missing_customer("ar")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"detail": "الزبون غير موجود", "human": True})
        self.assertEqual(self._missing_customer("en").json()["detail"], "Customer not found")
        self.assertEqual(self._missing_customer("fr").json()["detail"], "Client introuvable")

    def test_other_clients_get_the_original_answer(self):
        r = self._missing_customer()
        self.assertEqual(r.json(), {"detail": "Client introuvable"})
        r = self.client.get("/api/v1/admin/customers/987654321",
                            headers={**self.auth, "Accept-Language": "en-US,en;q=0.9"})
        self.assertEqual(r.json(), {"detail": "Client introuvable"})

    def test_sign_in_error_in_arabic(self):
        reset_rate_limits()
        r = self.client.post("/api/v1/admin/auth/login", headers={"X-Luxe-Lang": "ar"},
                             json={"email": "admin@mus-luxury.com", "password": "wrong-password-123"})
        self.assertEqual(r.status_code, 401)
        self.assertRegex(r.json()["detail"], r"[؀-ۿ]")
        self.assertTrue(r.json()["human"])

    def test_backup_warnings_follow_the_cms_language(self):
        r = self.client.get("/api/v1/admin/system/database", headers={**self.auth, "X-Luxe-Lang": "en"})
        self.assertEqual(r.status_code, 200, r.text)
        for w in r.json()["warnings"]:
            self.assertNotRegex(w, r"[éèàùç]", f"still French: {w}")

    def test_cors_allows_the_language_header(self):
        r = self.client.options("/api/v1/admin/products", headers={
            "Origin": "http://localhost:1420", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-luxe-lang"})
        self.assertIn("x-luxe-lang", r.headers.get("access-control-allow-headers", "").lower())


class TestCmsDictionaries(unittest.TestCase):
    def test_every_key_used_by_the_cms_exists_in_three_languages(self):
        langs = _cms_dictionaries()
        used = set()
        for f in CMS_SRC.rglob("*.ts*"):
            if "i18n" in f.parts:
                continue
            for m in re.finditer(r'\b(?:t|tr|trText)\(\s*"([a-z0-9_]+\.[A-Za-z0-9_.]+)"', f.read_text(encoding="utf-8")):
                used.add(m.group(1))
        self.assertGreater(len(used), 900)
        for lang in ("fr", "en", "ar"):
            self.assertEqual(sorted(used - langs[lang]), [], f"keys missing in {lang}")

    def test_three_languages_have_the_same_keys(self):
        langs = _cms_dictionaries()
        self.assertEqual(sorted(langs["fr"] - langs["en"]), [])
        self.assertEqual(sorted(langs["fr"] - langs["ar"]), [])

    def test_arabic_texts_are_in_arabic(self):
        for f in (CMS_SRC / "i18n" / "areas").glob("*.ts"):
            if f.stem in ("define", "index"):
                continue
            for key, (fr, en, ar) in _area_entries(f.stem).items():
                latin_only = re.fullmatch(r"[\W\d_A-Za-z{}]*", ar) is not None
                if latin_only and fr != ar:  # brand names, sizes, codes may stay as they are
                    self.assertEqual(ar, en, f"{f.stem}.{key}: Arabic text missing ({ar})")

    def test_every_audit_name_has_three_languages(self):
        actions, entities = _area_entries("audit_action"), _area_entries("audit_entity")
        self.assertEqual(sorted(set(_AUDIT_ACTION_FR) - set(actions)), [])
        self.assertEqual(sorted(set(_AUDIT_ENTITY_FR) - set(entities)), [])
        for code, (fr, en, ar) in {**actions, **entities}.items():
            self.assertRegex(ar, r"[؀-ۿ]", code)


if __name__ == "__main__":
    unittest.main()
