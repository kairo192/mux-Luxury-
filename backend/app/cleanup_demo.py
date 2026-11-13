"""
Operator command: check / run the one-time removal of the example content
that older versions put in every new database (2 example banners, and the
example promo codes BIENVENUE10 / ALGERIE500 which were ACTIVE).

You normally never need it: the removal runs by itself once, at the first
API start after the update is deployed (the deploy script backs up the
database first), and is written to CMS → Journal d'audit.

On the server (VPS):
    docker compose exec api python -m app.cleanup_demo --dry-run   # report only
    docker compose exec api python -m app.cleanup_demo             # run now

Only rows that still have ALL their original example values are touched: a
banner the owner edited is kept, a code customers already used stays on.
Example products are only LISTED (they may be linked to orders); the owner
deletes them in the CMS.
"""
from __future__ import annotations

import argparse
import json

from .database import db_session, init_db
from .seed import find_legacy_demo_content, remove_legacy_demo_content

# Brands of the old example catalogue (only used to list leftover products).
_DEMO_BRAND_SLUGS = ("chanel-style", "emeraude-paris", "maison-or-alger")


def _demo_products(cur) -> list:
    placeholders = ",".join("?" for _ in _DEMO_BRAND_SLUGS)
    cur.execute(
        f"""SELECT p.id, p.name_fr, p.status FROM products p JOIN brands b ON b.id = p.brand_id
            WHERE b.slug IN ({placeholders}) AND p.deleted_at IS NULL ORDER BY p.id""",
        _DEMO_BRAND_SLUGS,
    )
    return [{"id": r["id"], "name_fr": r["name_fr"], "status": r["status"]} for r in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    args = parser.parse_args()

    init_db()
    with db_session(commit=not args.dry_run) as conn:
        cur = conn.cursor()
        found = find_legacy_demo_content(cur) if args.dry_run else remove_legacy_demo_content(cur, force=True)
        report = {
            "mode": "dry-run: nothing changed" if args.dry_run else "done (written to the audit log)",
            "example_banners": [b["title_fr"] for b in found["banners"]],
            "example_promo_codes": [c["code"] for c in found["coupons"]],
            "example_products_to_delete_in_cms": _demo_products(cur),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
