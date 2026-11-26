"""The one-time cleanup of migrations/versions/006: characteristics stop being
required, and the old fixed marketing suggestions go — except a value that a
product uses. Colours / sizes (variant axes) are not touched."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("LUXE_DB_ENGINE") != "postgres":
    os.environ.setdefault("LUXE_DB_ENGINE", "sqlite")
    if not os.environ.get("LUXE_SQLITE_PATH"):
        _fd, _path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(_fd)
        os.environ["LUXE_SQLITE_PATH"] = _path
os.environ.setdefault("SECRET_KEY", "test_only_ephemeral_secret_key_for_unit_test_suite_2026_0123456789")

from app.database import db_session
from app.seed import seed_initial_data

SQL = (Path(__file__).resolve().parents[1] / "migrations" / "versions" / "006_free_product_characteristics.sql").read_text(encoding="utf-8")


class TestFreeCharacteristicsMigration(unittest.TestCase):
    def test_old_fixed_values_go_used_ones_stay(self):
        seed_initial_data()
        sfx = uuid.uuid4().hex[:6]
        with db_session(commit=True) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO categories (slug, name_fr, name_ar, name_en) VALUES (?, ?, '', '')", (f"old-preset-{sfx}", "Ancien modèle"))
            cat = cur.lastrowid
            cur.execute("""INSERT INTO category_attributes (category_id, attr_key, label_fr, input_type, is_required, is_variant_axis)
                           VALUES (?, 'material', 'Matière', 'single_select', 1, 0)""", (cat,))
            mat = cur.lastrowid
            cur.execute("""INSERT INTO category_attributes (category_id, attr_key, label_fr, input_type, is_required, is_variant_axis)
                           VALUES (?, 'color', 'Couleur', 'color', 1, 1)""", (cat,))
            col = cur.lastrowid
            for attr, value in ((mat, "100% Coton Pima Péruvien"), (mat, "Cuir d'agneau matelassé"), (mat, "Lin de ma tante"),
                                (col, "Noir Profond")):
                cur.execute("INSERT INTO category_attribute_options (attribute_id, value, label_fr) VALUES (?, ?, ?)", (attr, value, value))
            cur.execute("""INSERT INTO products (category_id, slug, sku, name_fr, selling_price_dzd)
                           VALUES (?, ?, ?, 'Veste', 100)""", (cat, f"veste-{sfx}", f"VESTE-{sfx}"))
            cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)",
                        (cur.lastrowid, mat, "Cuir d'agneau matelassé"))
        with db_session(commit=True) as conn:
            # exactly as app.migration_runner applies a file (one script, no placeholders:
            # "100% Coton" must not be read as a parameter on PostgreSQL)
            conn.executescript(SQL)
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT attribute_id, value FROM category_attribute_options WHERE attribute_id IN (?, ?) ORDER BY value", (mat, col))
            left = [(r["attribute_id"], r["value"]) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) AS n FROM category_attributes WHERE is_required <> 0")
            required = cur.fetchone()["n"]
        self.assertEqual(left, [(mat, "Cuir d'agneau matelassé"), (mat, "Lin de ma tante"), (col, "Noir Profond")])
        self.assertEqual(required, 0)


if __name__ == "__main__":
    unittest.main()
