filepath = 'backend/app/main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update CategoryAttributeCreate category_id to Optional[int] = None
c = c.replace(
    'class CategoryAttributeCreate(BaseModel):\n    category_id: int',
    'class CategoryAttributeCreate(BaseModel):\n    category_id: Optional[int] = None'
)

# 2. In add_category_attribute, check if not payload.category_id
old_add_attr = '''@app.post("/api/v1/admin/category-attributes", status_code=201)
def add_category_attribute(
    payload: CategoryAttributeCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:'''

new_add_attr = '''@app.post("/api/v1/admin/category-attributes", status_code=201)
def add_category_attribute(
    payload: CategoryAttributeCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    if not payload.category_id:
        raise HTTPException(status_code=400, detail="category_id is required")
    with db_session(commit=True) as conn:'''

c = c.replace(old_add_attr, new_add_attr)

# 3. In create_custom_category, insert payload.attributes atomically
old_create_cat = '''        cat_id = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_category", "category", str(cat_id), {"slug": payload.slug})
        cur.execute("SELECT * FROM categories WHERE id = ?", (cat_id,))
        return serialize_category(conn, dict(cur.fetchone()))'''

new_create_cat = '''        cat_id = cur.lastrowid
        # Insert any attributes passed directly in the CategoryCreate payload
        for idx, attr_payload in enumerate(payload.attributes or [], start=1):
            cur.execute(
                """INSERT INTO category_attributes
                   (category_id, attr_key, label_fr, label_ar, label_en, input_type, unit,
                    is_required, default_value, allow_multiple, is_visible_on_storefront,
                    is_filterable, is_variant_axis, display_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cat_id, attr_payload.attr_key, attr_payload.label_fr,
                    attr_payload.label_ar or attr_payload.label_fr,
                    attr_payload.label_en or attr_payload.label_fr,
                    attr_payload.input_type, attr_payload.unit or "",
                    1 if attr_payload.is_required else 0, attr_payload.default_value,
                    1 if attr_payload.allow_multiple else 0,
                    1 if attr_payload.is_visible_on_storefront else 0,
                    1 if attr_payload.is_filterable else 0,
                    1 if attr_payload.is_variant_axis else 0,
                    attr_payload.display_order or idx
                )
            )
            attr_id = cur.lastrowid
            for o_idx, opt in enumerate(attr_payload.options or [], start=1):
                cur.execute(
                    """INSERT INTO category_attribute_options
                       (attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (attr_id, opt.value, opt.label_fr or opt.value, opt.label_ar or opt.value, opt.label_en or opt.value, opt.color_hex, opt.display_order or o_idx)
                )
        log_audit(conn, int(admin["sub"]), "create_category", "category", str(cat_id), {"slug": payload.slug})
        cur.execute("SELECT * FROM categories WHERE id = ?", (cat_id,))
        return serialize_category(conn, dict(cur.fetchone()))'''

c = c.replace(old_create_cat, new_create_cat)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated backend/app/main.py category attributes handling.')

