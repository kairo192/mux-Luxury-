import os
import sys
import json

os.environ["SECRET_KEY"] = "dev_secret_key_mus_luxury_2026_very_secure_long_string_1234567890"
os.environ["APP_ENV"] = "development"
os.environ["LUXE_DB_ENGINE"] = "sqlite"
os.environ["LUXE_SQLITE_PATH"] = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend\luxe_store.sqlite3"
sys.path.insert(0, r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend")

from app.database import db_session
from app.main import serialize_product

def serialize_products_batch(conn, product_rows, include_private=False):
    if not product_rows:
        return []
    
    cur = conn.cursor()
    products = [dict(r) for r in product_rows]
    pids = [p["id"] for p in products]
    bids = list({p["brand_id"] for p in products if p.get("brand_id")})
    cids = list({p["category_id"] for p in products if p.get("category_id")})

    if not include_private:
        for p in products:
            p.pop("purchase_cost_dzd", None)

    # 1. Fetch brands in single query
    brands_by_id = {}
    if bids:
        placeholders = ",".join("?" for _ in bids)
        cur.execute(f"SELECT id, name, slug, logo_url FROM brands WHERE id IN ({placeholders})", bids)
        for r in cur.fetchall():
            brands_by_id[r["id"]] = {"name": r["name"], "slug": r["slug"], "logo_url": r["logo_url"]}

    # 2. Fetch categories with attributes and options
    cats_by_id = {}
    if cids:
        placeholders = ",".join("?" for _ in cids)
        cur.execute(f"SELECT * FROM categories WHERE id IN ({placeholders})", cids)
        raw_cats = {r["id"]: dict(r) for r in cur.fetchall()}

        # Category attributes
        cur.execute(
            f"SELECT * FROM category_attributes WHERE category_id IN ({placeholders}) ORDER BY display_order ASC, id ASC",
            cids
        )
        cat_attrs = cur.fetchall()
        attr_ids = [a["id"] for a in cat_attrs]
        attrs_by_cat = {}
        for a in cat_attrs:
            ad = dict(a)
            ad["is_required"] = bool(ad["is_required"])
            ad["allow_multiple"] = bool(ad["allow_multiple"])
            ad["is_visible_on_storefront"] = bool(ad["is_visible_on_storefront"])
            ad["is_filterable"] = bool(ad["is_filterable"])
            ad["is_variant_axis"] = bool(ad["is_variant_axis"])
            ad["options"] = []
            attrs_by_cat.setdefault(ad["category_id"], []).append(ad)

        # Options for attributes
        if attr_ids:
            a_placeholders = ",".join("?" for _ in attr_ids)
            cur.execute(
                f"SELECT attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order FROM category_attribute_options WHERE attribute_id IN ({a_placeholders}) ORDER BY display_order ASC, id ASC",
                attr_ids
            )
            for opt in cur.fetchall():
                od = dict(opt)
                aid = od.pop("attribute_id")
                for cat_attr_list in attrs_by_cat.values():
                    for a in cat_attr_list:
                        if a["id"] == aid:
                            a["options"].append(od)

        for cid, cd in raw_cats.items():
            cats_by_id[cid] = {
                "id": cd["id"],
                "slug": cd["slug"],
                "name_fr": cd["name_fr"],
                "name_ar": cd["name_ar"],
                "name_en": cd["name_en"],
                "attributes": attrs_by_cat.get(cid, [])
            }

    # 3. Product attribute values in single query
    pav_by_pid = {}
    placeholders_p = ",".join("?" for _ in pids)
    cur.execute(
        f"""SELECT pav.product_id, ca.attr_key, pav.value_text
            FROM product_attribute_values pav
            JOIN category_attributes ca ON ca.id = pav.attribute_id
            WHERE pav.product_id IN ({placeholders_p}) AND (? = 1 OR ca.is_visible_on_storefront = 1)
            ORDER BY ca.display_order ASC""",
        [*pids, 1 if include_private else 0]
    )
    for r in cur.fetchall():
        pav_by_pid.setdefault(r["product_id"], {})[r["attr_key"]] = r["value_text"]

    # 4. Product variants in single query
    variants_by_pid = {}
    cur.execute(
        f"SELECT * FROM product_variants WHERE product_id IN ({placeholders_p}) AND (? = 1 OR is_active = 1) ORDER BY id ASC",
        [*pids, 1 if include_private else 0]
    )
    all_variants = [dict(v) for v in cur.fetchall()]
    var_ids = [v["id"] for v in all_variants]

    # 5. Variant attribute values in single query
    vav_by_vid = {}
    if var_ids:
        placeholders_v = ",".join("?" for _ in var_ids)
        cur.execute(
            f"""SELECT vav.variant_id, ca.attr_key, vav.option_value
                FROM variant_attribute_values vav
                JOIN category_attributes ca ON ca.id = vav.attribute_id
                WHERE vav.variant_id IN ({placeholders_v})""",
            var_ids
        )
        for r in cur.fetchall():
            vav_by_vid.setdefault(r["variant_id"], {})[r["attr_key"]] = r["option_value"]

    # 6. Product images in single query
    images_by_pid = {}
    cur.execute(
        f"SELECT id, product_id, variant_id, image_url, alt_text, display_order FROM product_images WHERE product_id IN ({placeholders_p}) ORDER BY display_order ASC, id ASC",
        pids
    )
    for img in cur.fetchall():
        images_by_pid.setdefault(img["product_id"], []).append(dict(img))

    # Assemble products
    out = []
    for p in products:
        pid = p["id"]
        p["brand"] = brands_by_id.get(p.get("brand_id"))
        p["category"] = cats_by_id.get(p.get("category_id"))
        p["attributes"] = pav_by_pid.get(pid, {})
        
        # Variants
        p_vars = [v for v in all_variants if v["product_id"] == pid]
        total_stock = 0
        for v in p_vars:
            v["attributes"] = vav_by_vid.get(v["id"], {})
            v["effective_price_dzd"] = v["price_override_dzd"] if v["price_override_dzd"] is not None else p["selling_price_dzd"]
            total_stock += v["stock_qty"]

        p["variants"] = p_vars
        p["total_stock"] = total_stock
        p["in_stock"] = total_stock > 0
        p["gallery_images"] = images_by_pid.get(pid, [])
        p["images"] = p["gallery_images"]
        out.append(p)

    return out

with db_session() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE status='published' AND deleted_at IS NULL")
    raw_rows = [dict(r) for r in cur.fetchall()]

    old_serialized = [serialize_product(conn, r) for r in raw_rows]
    new_serialized = serialize_products_batch(conn, raw_rows)

    diffs = 0
    for old, new in zip(old_serialized, new_serialized):
        old_json = json.dumps(old, sort_keys=True)
        new_json = json.dumps(new, sort_keys=True)
        if old_json != new_json:
            print("DIFF FOUND on product ID", old["id"])
            diffs += 1

    if diffs == 0:
        print("PERFECT 100% PARITY! serialize_products_batch produces identical output for all products!")
    else:
        print(f"FAILED with {diffs} diffs")

# Count queries with CountingConnection
from trace_queries import CountingConnection
with db_session() as conn:
    c_conn = CountingConnection(conn)
    cur = c_conn.cursor()
    cur.execute("SELECT * FROM products WHERE status='published' AND deleted_at IS NULL")
    raw = cur.fetchall()

    import trace_queries
    trace_queries.query_count = 0
    serialize_products_batch(c_conn, raw)
    print(f"BATCH TOTAL QUERIES: {trace_queries.query_count} (Reduced from 71 to {trace_queries.query_count}!)")
