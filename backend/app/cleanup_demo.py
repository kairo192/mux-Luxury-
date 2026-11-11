"""
Clean an OLD database (for example the one on the shop PC) of the example
content that older versions created in every new database:

  * 2 example banners ("Votre style, notre passion", "CHAUSSURES — Jusqu'à -20%")
  * 2 example promo codes (BIENVENUE10 −10 %, ALGERIE500 −500 DA), which were
    ACTIVE, so any customer typing them got a discount.

The same cleanup also runs by itself every time the backend starts; this
command lets you run it on demand and see exactly what it changes.

Usage (from the backend folder, with the same settings the PC normally uses):
    python -m app.cleanup_demo --dry-run     # only show what would change
    python -m app.cleanup_demo               # do it

Safe: only rows that still have ALL their original example values are
touched. A banner you edited is kept; a code customers already used stays on.
Example products / categories are only LISTED (they may be linked to orders):
delete them in the CMS, or use Sauvegardes → "Nouvelle base de données".
"""
from __future__ import annotations

import argparse
import json

from .database import db_session, init_db
from .seed import _LEGACY_DEMO_BANNERS, _LEGACY_DEMO_COUPONS

# Example brands from the old demo catalogue (used only to list leftovers).
_DEMO_BRAND_SLUGS = ("chanel-style", "emeraude-paris", "maison-or-alger")


def _report(cur) -> dict:
    banners = []
    for pos, title, link, img in _LEGACY_DEMO_BANNERS:
        cur.execute(
            "SELECT id, title_fr FROM banners WHERE position = ? AND title_fr = ? AND cta_link = ? AND image_url = ?",
            (pos, title, link, img),
        )
        banners += [dict(r) for r in cur.fetchall()]
    coupons = []
    for code, dtype, value, min_order in _LEGACY_DEMO_COUPONS:
        cur.execute(
            """SELECT code, usage_count FROM coupons
               WHERE code = ? AND discount_type = ? AND discount_value = ? AND min_order_dzd = ?
                 AND COALESCE(usage_count, 0) = 0 AND is_active = 1""",
            (code, dtype, value, min_order),
        )
        coupons += [dict(r) for r in cur.fetchall()]
    placeholders = ",".join("?" for _ in _DEMO_BRAND_SLUGS)
    cur.execute(
        f"""SELECT p.id, p.name_fr, p.status FROM products p JOIN brands b ON b.id = p.brand_id
            WHERE b.slug IN ({placeholders}) AND p.deleted_at IS NULL""",
        _DEMO_BRAND_SLUGS,
    )
    demo_products = [dict(r) for r in cur.fetchall()]
    return {
        "banners_to_delete": banners,
        "promo_codes_to_switch_off": coupons,
        "example_products_still_present (delete them in the CMS)": demo_products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="only show what would change")
    args = parser.parse_args()

    init_db()
    with db_session(commit=not args.dry_run) as conn:
        cur = conn.cursor()
        report = _report(cur)
        if not args.dry_run:
            # Run even if APP_ENV says development/test: the owner asked for it.
            for pos, title, link, img in _LEGACY_DEMO_BANNERS:
                cur.execute(
                    "DELETE FROM banners WHERE position = ? AND title_fr = ? AND cta_link = ? AND image_url = ?",
                    (pos, title, link, img),
                )
            for code, dtype, value, min_order in _LEGACY_DEMO_COUPONS:
                cur.execute(
                    """UPDATE coupons SET is_active = 0
                       WHERE code = ? AND discount_type = ? AND discount_value = ? AND min_order_dzd = ?
                         AND COALESCE(usage_count, 0) = 0 AND is_active = 1""",
                    (code, dtype, value, min_order),
                )
    report["mode"] = "dry-run (nothing changed)" if args.dry_run else "done"
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
