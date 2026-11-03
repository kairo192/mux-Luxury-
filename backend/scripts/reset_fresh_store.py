"""
Reset Database to Fresh, Clean State
Clears all products, categories, suppliers (fournisseurs), purchase orders,
inventory, orders, customers, cash movements, expenses, and accounting ledger.
Preserves:
- Admin user accounts & credentials
- Roles and permissions (RBAC)
- 69 Algerian Wilayas & delivery tariff rates
- Store settings & static pages
"""

import os
import sqlite3
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_path = os.environ.get("LUXE_SQLITE_PATH", os.path.join(backend_dir, "luxe_store.sqlite3"))

def reset_fresh_store(db_file=db_path):
    print(f"Connecting to database: {db_file}")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys = OFF;")

    tables_to_clear = [
        # Catalog & Attributes
        "variant_attribute_values",
        "product_attribute_values",
        "product_images",
        "product_variants",
        "products",
        "category_attribute_options",
        "category_attributes",
        "categories",
        "brands",
        # Suppliers & Purchasing
        "purchase_order_items",
        "purchase_orders",
        "suppliers",
        # Inventory Movements
        "inventory_movements",
        # Customer Orders
        "order_items",
        "orders",
        "customers",
        "coupons",
        # Financial Accounting & Treasury
        "expenses",
        "cash_movements",
        "accounting_ledger",
    ]

    for table in tables_to_clear:
        try:
            cur.execute(f"DELETE FROM {table};")
            # Reset SQLite autoincrement sequence
            cur.execute(f"DELETE FROM sqlite_sequence WHERE name = '{table}';")
            print(f" ✓ Cleared table: {table}")
        except sqlite3.OperationalError as e:
            print(f" - Notice for {table}: {e}")

    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    # Re-verify counts
    print("\n--- Current Table Row Counts ---")
    verification_tables = [
        "products", "categories", "suppliers", "purchase_orders",
        "orders", "customers", "cash_movements", "expenses", "accounting_ledger",
        "admin_users", "delivery_zones", "delivery_rates"
    ]
    for t in verification_tables:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt} rows")

    conn.close()
    print("\nDatabase has been successfully cleared to a fresh brand-new store!")

if __name__ == "__main__":
    reset_fresh_store()
