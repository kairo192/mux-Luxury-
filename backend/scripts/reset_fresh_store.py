"""
Empty the store ("nouvelle base de données") from the command line.

Same operation as the CMS button (Sauvegardes & Sécurité → Nouvelle base de
données), on SQLite (PC) and PostgreSQL (VPS):
  * takes a full safety backup first,
  * erases catalog, stock, orders, customers, POS sales, cash, expenses,
    suppliers, coupons, banners and history in ONE transaction,
  * keeps staff accounts + roles, POS devices, the 69 wilayas and delivery
    tariffs, legal pages (and store settings unless --wipe-settings).

Usage:
    cd backend && python scripts/reset_fresh_store.py --yes [--wipe-settings]
    # VPS:  docker exec luxe_api python scripts/reset_fresh_store.py --yes
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.backup_cli import main  # noqa: E402

if __name__ == "__main__":
    if "--yes" not in sys.argv:
        print("This empties the store (a safety backup is taken first). Re-run with --yes to confirm.")
        sys.exit(1)
    extra = ["--wipe-settings"] if "--wipe-settings" in sys.argv else []
    sys.exit(main(["reset", "--yes", *extra]))
