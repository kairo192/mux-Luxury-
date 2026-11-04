import os
import sys

# Set security environment before imports
os.environ["SECRET_KEY"] = "dev_secret_key_mus_luxury_2026_very_secure_long_string_1234567890"
os.environ["CMS_HMAC_SIGNING_SECRET"] = "dev_hmac_signing_secret_mus_luxury_2026_long_key_1234567890"
os.environ["APP_ENV"] = "development"
os.environ["LUXE_DB_ENGINE"] = "sqlite"

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ["LUXE_SQLITE_PATH"] = os.path.join(backend_dir, "luxe_store.sqlite3")
sys.path.insert(0, backend_dir)

from app.database import db_session, init_db
from app.seed import seed_initial_data

with db_session(commit=True) as conn:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE deleted_at IS NULL")
    prod_cnt = cur.fetchone()["cnt"]
    if prod_cnt == 0:
        print("Restoring full demo catalog...")
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("DELETE FROM role_permissions")
        cur.execute("DELETE FROM permissions")
        cur.execute("DELETE FROM roles")
        cur.execute("DELETE FROM admin_recovery_codes")
        cur.execute("DELETE FROM admin_users")
        cur.execute("DELETE FROM category_attribute_options")
        cur.execute("DELETE FROM category_attributes")
        cur.execute("DELETE FROM categories")
        cur.execute("DELETE FROM brands")
        cur.execute("DELETE FROM product_attribute_values")
        cur.execute("DELETE FROM variant_attribute_values")
        cur.execute("DELETE FROM product_variants")
        cur.execute("DELETE FROM product_images")
        cur.execute("DELETE FROM products")
        cur.execute("DELETE FROM delivery_rates")
        cur.execute("DELETE FROM delivery_zones")
        cur.execute("DELETE FROM store_settings")
        cur.execute("DELETE FROM coupons")
        cur.execute("DELETE FROM banners")
        cur.execute("DELETE FROM homepage_sections")
        cur.execute("DELETE FROM static_pages")
        cur.execute("PRAGMA foreign_keys = ON")

seed_initial_data()

with db_session() as conn:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products WHERE deleted_at IS NULL")
    p_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL")
    c_cnt = cur.fetchone()[0]
    print(f"Database ready: {p_cnt} active products, {c_cnt} active categories.")
