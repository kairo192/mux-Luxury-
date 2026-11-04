import re

main_path = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend\app\main.py"

with open(main_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add GZipMiddleware import and registration
old_cors_block = """app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)"""

new_cors_block = """from starlette.middleware.gzip import GZipMiddleware

# High-Performance HTTP Response Compression (brotli/gzip for JSON payloads > 1000 bytes)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "ETag", "Cache-Control"],
)"""

assert old_cors_block in code, "old_cors_block not found in main.py"
code = code.replace(old_cors_block, new_cors_block, 1)
print("1. Added GZipMiddleware and exposed cache headers.")

# 2. Add serialize_products_batch and update serialize_product
old_serialize_product = """def serialize_product(conn, row: dict, include_private: bool = False) -> dict:
    cur = conn.cursor()
    p = dict(row)
    if not include_private:
        p.pop("purchase_cost_dzd", None)

    cur.execute("SELECT name, slug, logo_url FROM brands WHERE id = ?", (p.get("brand_id"),))
    b = cur.fetchone()
    p["brand"] = dict(b) if b else None

    cur.execute("SELECT * FROM categories WHERE id = ?", (p["category_id"],))
    c = cur.fetchone()
    if c:
        cat_full = serialize_category(conn, dict(c))
        p["category"] = {
            "id": cat_full["id"],
            "slug": cat_full["slug"],
            "name_fr": cat_full["name_fr"],
            "name_ar": cat_full["name_ar"],
            "name_en": cat_full["name_en"],
            "attributes": cat_full["attributes"]
        }
    else:
        p["category"] = None

    cur.execute(
        \"\"\"SELECT ca.attr_key, ca.label_fr, ca.label_ar, ca.label_en, ca.input_type, ca.unit, pav.value_text
           FROM product_attribute_values pav
           JOIN category_attributes ca ON ca.id = pav.attribute_id
           WHERE pav.product_id = ? AND (? = 1 OR ca.is_visible_on_storefront = 1)
           ORDER BY ca.display_order ASC\"\"\",
        (p["id"], 1 if include_private else 0)
    )
    p["attributes"] = {r["attr_key"]: r["value_text"] for r in cur.fetchall()}

    cur.execute(
        "SELECT * FROM product_variants WHERE product_id = ? AND (? = 1 OR is_active = 1) ORDER BY id ASC",
        (p["id"], 1 if include_private else 0)
    )
    variants = []
    total_stock = 0
    for v in cur.fetchall():
        vd = dict(v)
        cur.execute(
            \"\"\"SELECT ca.attr_key, vav.option_value
               FROM variant_attribute_values vav
               JOIN category_attributes ca ON ca.id = vav.attribute_id
               WHERE vav.variant_id = ?\"\"\",
            (vd["id"],)
        )
        vd["attributes"] = {vr["attr_key"]: vr["option_value"] for vr in cur.fetchall()}
        vd["effective_price_dzd"] = vd["price_override_dzd"] if vd["price_override_dzd"] is not None else p["selling_price_dzd"]
        total_stock += vd["stock_qty"]
        variants.append(vd)

    cur.execute(
        "SELECT id, product_id, variant_id, image_url, alt_text, display_order FROM product_images WHERE product_id = ? ORDER BY display_order ASC, id ASC",
        (p["id"],)
    )
    p["gallery_images"] = [dict(img) for img in cur.fetchall()]
    p["images"] = p["gallery_images"]
    p["variants"] = variants
    p["total_stock"] = total_stock
    p["in_stock"] = total_stock > 0
    return p"""

new_serialize_product = """def serialize_products_batch(conn, product_rows: List[dict], include_private: bool = False) -> List[dict]:
    \"\"\"
    High-Performance Batch Product Serializer:
    Eliminates the N+1 query problem by fetching brands, categories, attribute values,
    variants, and images in 6 batched queries total instead of 12+ queries per product.
    \"\"\"
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

    # 1. Brands batch query
    brands_by_id = {}
    if bids:
        placeholders_b = ",".join("?" for _ in bids)
        cur.execute(f"SELECT id, name, slug, logo_url FROM brands WHERE id IN ({placeholders_b})", bids)
        for r in cur.fetchall():
            brands_by_id[r["id"]] = {"name": r["name"], "slug": r["slug"], "logo_url": r["logo_url"]}

    # 2. Categories with attributes & options batch query
    cats_by_id = {}
    if cids:
        placeholders_c = ",".join("?" for _ in cids)
        cur.execute(f"SELECT * FROM categories WHERE id IN ({placeholders_c})", cids)
        raw_cats = {r["id"]: dict(r) for r in cur.fetchall()}

        cur.execute(
            f"SELECT * FROM category_attributes WHERE category_id IN ({placeholders_c}) ORDER BY display_order ASC, id ASC",
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

        if attr_ids:
            placeholders_a = ",".join("?" for _ in attr_ids)
            cur.execute(
                f"SELECT attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order FROM category_attribute_options WHERE attribute_id IN ({placeholders_a}) ORDER BY display_order ASC, id ASC",
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

    # 3. Product attribute values batch query
    pav_by_pid = {}
    placeholders_p = ",".join("?" for _ in pids)
    cur.execute(
        f\"\"\"SELECT pav.product_id, ca.attr_key, pav.value_text
            FROM product_attribute_values pav
            JOIN category_attributes ca ON ca.id = pav.attribute_id
            WHERE pav.product_id IN ({placeholders_p}) AND (? = 1 OR ca.is_visible_on_storefront = 1)
            ORDER BY ca.display_order ASC\"\"\",
        [*pids, 1 if include_private else 0]
    )
    for r in cur.fetchall():
        pav_by_pid.setdefault(r["product_id"], {})[r["attr_key"]] = r["value_text"]

    # 4. Product variants batch query
    cur.execute(
        f"SELECT * FROM product_variants WHERE product_id IN ({placeholders_p}) AND (? = 1 OR is_active = 1) ORDER BY id ASC",
        [*pids, 1 if include_private else 0]
    )
    all_variants = [dict(v) for v in cur.fetchall()]
    var_ids = [v["id"] for v in all_variants]

    # 5. Variant attribute values batch query
    vav_by_vid = {}
    if var_ids:
        placeholders_v = ",".join("?" for _ in var_ids)
        cur.execute(
            f\"\"\"SELECT vav.variant_id, ca.attr_key, vav.option_value
                FROM variant_attribute_values vav
                JOIN category_attributes ca ON ca.id = vav.attribute_id
                WHERE vav.variant_id IN ({placeholders_v})\"\"\",
            var_ids
        )
        for r in cur.fetchall():
            vav_by_vid.setdefault(r["variant_id"], {})[r["attr_key"]] = r["option_value"]

    # 6. Product images batch query
    images_by_pid = {}
    cur.execute(
        f"SELECT id, product_id, variant_id, image_url, alt_text, display_order FROM product_images WHERE product_id IN ({placeholders_p}) ORDER BY display_order ASC, id ASC",
        pids
    )
    for img in cur.fetchall():
        images_by_pid.setdefault(img["product_id"], []).append(dict(img))

    # Assemble output products
    out = []
    for p in products:
        pid = p["id"]
        p["brand"] = brands_by_id.get(p.get("brand_id"))
        p["category"] = cats_by_id.get(p.get("category_id"))
        p["attributes"] = pav_by_pid.get(pid, {})

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

def serialize_product(conn, row: dict, include_private: bool = False) -> dict:
    res = serialize_products_batch(conn, [row], include_private=include_private)
    return res[0] if res else dict(row)"""

assert old_serialize_product in code, "old_serialize_product not found in main.py"
code = code.replace(old_serialize_product, new_serialize_product, 1)
print("2. Replaced serialize_product with serialize_products_batch (N+1 eliminated).")

# 3. Update list_delivery_zones with batch rate loading, ETag and Cache-Control
old_delivery_zones = """@app.get("/api/v1/delivery-zones")
def list_delivery_zones():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM delivery_zones WHERE is_active = 1 ORDER BY CAST(wilaya_code AS INTEGER) ASC")
        zones = []
        for z in cur.fetchall():
            zd = dict(z)
            zd["communes"] = json.loads(zd.pop("communes_json"))
            cur.execute("SELECT delivery_method, fee_dzd, estimated_days, is_supported FROM delivery_rates WHERE zone_id = ?", (zd["id"],))
            zd["rates"] = {r["delivery_method"]: dict(r) for r in cur.fetchall()}
            zones.append(zd)
        return {"items": zones}"""

new_delivery_zones = """@app.get("/api/v1/delivery-zones")
def list_delivery_zones(response: Response, request: Request):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM delivery_zones WHERE is_active = 1 ORDER BY CAST(wilaya_code AS INTEGER) ASC")
        zones = [dict(z) for z in cur.fetchall()]
        if zones:
            zids = [z["id"] for z in zones]
            placeholders = ",".join("?" for _ in zids)
            cur.execute(
                f"SELECT zone_id, delivery_method, fee_dzd, estimated_days, is_supported FROM delivery_rates WHERE zone_id IN ({placeholders})",
                zids
            )
            rates_by_zone = {}
            for r in cur.fetchall():
                rd = dict(r)
                zid = rd.pop("zone_id")
                rates_by_zone.setdefault(zid, {})[rd["delivery_method"]] = rd
            for zd in zones:
                zd["communes"] = json.loads(zd.pop("communes_json"))
                zd["rates"] = rates_by_zone.get(zd["id"], {})

        payload = {"items": zones}
        etag = f'"{hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"'
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
        return payload"""

assert old_delivery_zones in code, "old_delivery_zones not found in main.py"
code = code.replace(old_delivery_zones, new_delivery_zones, 1)
print("3. Optimized list_delivery_zones (2 queries instead of 70, ETag + 304).")

# 4. Update list_public_categories with Cache-Control and ETag
old_categories = """@app.get("/api/v1/categories")
def list_public_categories():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC, id ASC"
        )
        return {"items": [serialize_category(conn, dict(r)) for r in cur.fetchall()]}"""

new_categories = """@app.get("/api/v1/categories")
def list_public_categories(response: Response, request: Request):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC, id ASC"
        )
        cats = [serialize_category(conn, dict(r)) for r in cur.fetchall()]
        payload = {"items": cats}
        etag = f'"{hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"'
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
        return payload"""

assert old_categories in code, "old_categories not found in main.py"
code = code.replace(old_categories, new_categories, 1)
print("4. Optimized list_public_categories with ETag + Cache-Control.")

# 5. Update list_public_products with serialize_products_batch and ETag
old_public_products = """        if not in_stock_only and not dynamic_attr_filters:
            count_sql = f\"\"\"
                SELECT COUNT(*) AS cnt FROM products p
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN brands b ON b.id = p.brand_id
                WHERE {' AND '.join(where)}
            \"\"\"
            cur.execute(count_sql, params)
            total = int(cur.fetchone()["cnt"])
            paged_sql = sql + " LIMIT ? OFFSET ?"
            cur.execute(paged_sql, [*params, page_size, start])
            page_items = [serialize_product(conn, dict(r), include_private=False) for r in cur.fetchall()]
            return {
                "items": page_items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        cur.execute(sql, params)
        items = [serialize_product(conn, dict(r), include_private=False) for r in cur.fetchall()]"""

new_public_products = """        if not in_stock_only and not dynamic_attr_filters:
            count_sql = f\"\"\"
                SELECT COUNT(*) AS cnt FROM products p
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN brands b ON b.id = p.brand_id
                WHERE {' AND '.join(where)}
            \"\"\"
            cur.execute(count_sql, params)
            total = int(cur.fetchone()["cnt"])
            paged_sql = sql + " LIMIT ? OFFSET ?"
            cur.execute(paged_sql, [*params, page_size, start])
            page_items = serialize_products_batch(conn, cur.fetchall(), include_private=False)
            payload = {
                "items": page_items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
            etag = f'"{hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"'
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
            return payload

        cur.execute(sql, params)
        items = serialize_products_batch(conn, cur.fetchall(), include_private=False)"""

assert old_public_products in code, "old_public_products not found in main.py"
code = code.replace(old_public_products, new_public_products, 1)

# Ensure response: Response is in list_public_products signature
old_sig = """@app.get("/api/v1/products")
def list_public_products(
    request: Request,"""

new_sig = """@app.get("/api/v1/products")
def list_public_products(
    request: Request,
    response: Response,"""

assert old_sig in code, "old_sig not found in main.py"
code = code.replace(old_sig, new_sig, 1)
print("5. Optimized list_public_products with batch eager-loading & ETag.")

# 6. Update admin_list_products with serialize_products_batch
old_admin_prod_call = """        paged_rows = [serialize_product(conn, dict(r), include_private=True) for r in cur.fetchall()]"""
new_admin_prod_call = """        paged_rows = serialize_products_batch(conn, cur.fetchall(), include_private=True)"""
assert old_admin_prod_call in code, "old_admin_prod_call not found in main.py"
code = code.replace(old_admin_prod_call, new_admin_prod_call, 1)
print("6. Optimized admin_list_products with batch eager-loading.")

# 7. Update list_admin_orders with batch order_items and phone risk cache
old_admin_orders = """@app.get("/api/v1/admin/orders")
def list_admin_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status_filter,))
        else:
            cur.execute("SELECT * FROM orders ORDER BY id DESC")
        orders = []
        for r in cur.fetchall():
            od = dict(r)
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (od["id"],))
            od["items"] = [dict(it) for it in cur.fetchall()]
            od["cod_risk"] = compute_customer_cod_risk(conn, od["customer_phone"])
            od["whatsapp_actions"] = {
                "confirmation_call_url": build_customer_order_whatsapp_message(od, "confirmation_call")["wa_me_customer_url"],
                "shipped_notice_url": build_customer_order_whatsapp_message(od, "shipped_notice")["wa_me_customer_url"],
                "no_answer_followup_url": build_customer_order_whatsapp_message(od, "no_answer_followup")["wa_me_customer_url"],
                "delivery_arrived_url": build_customer_order_whatsapp_message(od, "delivery_arrived")["wa_me_customer_url"],
            }
            orders.append(od)
        return {"items": orders}"""

new_admin_orders = """@app.get("/api/v1/admin/orders")
def list_admin_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status_filter, limit))
        else:
            cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        raw_orders = cur.fetchall()
        orders = [dict(r) for r in raw_orders]
        if orders:
            oids = [o["id"] for o in orders]
            placeholders = ",".join("?" for _ in oids)
            cur.execute(f"SELECT * FROM order_items WHERE order_id IN ({placeholders})", oids)
            items_by_oid = {}
            for it in cur.fetchall():
                items_by_oid.setdefault(it["order_id"], []).append(dict(it))

            phone_risk_cache = {}
            for od in orders:
                od["items"] = items_by_oid.get(od["id"], [])
                phone = od["customer_phone"]
                if phone not in phone_risk_cache:
                    phone_risk_cache[phone] = compute_customer_cod_risk(conn, phone)
                od["cod_risk"] = phone_risk_cache[phone]
                od["whatsapp_actions"] = {
                    "confirmation_call_url": build_customer_order_whatsapp_message(od, "confirmation_call")["wa_me_customer_url"],
                    "shipped_notice_url": build_customer_order_whatsapp_message(od, "shipped_notice")["wa_me_customer_url"],
                    "no_answer_followup_url": build_customer_order_whatsapp_message(od, "no_answer_followup")["wa_me_customer_url"],
                    "delivery_arrived_url": build_customer_order_whatsapp_message(od, "delivery_arrived")["wa_me_customer_url"],
                }
        return {"items": orders}"""

assert old_admin_orders in code, "old_admin_orders not found in main.py"
code = code.replace(old_admin_orders, new_admin_orders, 1)
print("7. Optimized list_admin_orders with batch eager-loading and memoized risk scoring.")

with open(main_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(code)

print("Saved all backend optimizations to main.py successfully!")

