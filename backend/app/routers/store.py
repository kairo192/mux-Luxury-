"""Boutique articles ("Shop items" screen of the CMS).

A quick way for the owner to put the articles of the physical shop into the
system: name, category, price, colours / sizes with their quantities, and a
barcode for each colour / size (scanned from the label the article already
has, or created here) so the till rings up the exact variant and the stock of
each one is right. Labels are then printed for every piece.

Everything is stored in the SAME products / variants / stock tables as the
Products screen: the till, stock reports, physical counts, purchases and the
Products screen all see these articles. Only `products.sales_channel` says
where an article is sold:
    all   — online shop and boutique (the default for the Products screen)
    store — boutique only: sold at the till, hidden from the online shop.
"""
import re
import unicodedata
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..common import _boutique_info_from_settings
from ..database import db_session
from ..deps import log_audit, require_any_permission, require_permission
from ..catalog_rules import (
    _barcode_in_use,
    _generate_internal_ean13,
    auto_variant_sku,
    build_variant_signature,
    detect_symbology,
    ensure_variant_attribute_options,
    load_category_attributes_with_options,
    replace_variant_attribute_values,
    validate_barcode,
    validate_variant_attributes,
)

router = APIRouter()

SINGLE_TITLE = "Unique"
STORE_RECEIPT = "store_receipt"


class StoreVariantIn(BaseModel):
    # Colour / size… of the category (variant axes). Empty = one single article.
    attributes: Dict[str, str] = {}
    # Free name when the category has no colour / size (e.g. "Modèle A").
    title: Optional[str] = Field(None, max_length=180)
    quantity: int = Field(0, ge=0, le=100000)
    # Scanned from the article; empty = a shop barcode is created.
    barcode: Optional[str] = Field(None, max_length=64)
    # Only when this colour / size has its own price.
    price_dzd: Optional[int] = Field(None, ge=0)


class StoreQuickAddIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=220)
    category_id: int
    price_dzd: int = Field(..., ge=0)
    cost_dzd: int = Field(0, ge=0)
    image_url: Optional[str] = Field(None, max_length=500)
    sold_online: bool = False
    variants: List[StoreVariantIn] = Field(default_factory=list, max_items=200)


class StoreAddVariantsIn(BaseModel):
    variants: List[StoreVariantIn] = Field(..., min_items=1, max_items=200)


class StoreReceiveIn(BaseModel):
    quantity: int = Field(..., ge=1, le=100000)


class StoreProductEditIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=220)
    price_dzd: Optional[int] = Field(None, ge=0)
    cost_dzd: Optional[int] = Field(None, ge=0)
    sold_online: Optional[bool] = None


# ----------------------------------------------------------------- helpers

def _slug_base(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:120]
    return s if len(s) >= 2 else "article"


def _free_slug(cur, name: str) -> str:
    base = _slug_base(name)
    slug, n = base, 2
    while True:
        cur.execute("SELECT 1 FROM products WHERE slug = ?", (slug,))
        if not cur.fetchone():
            return slug
        slug, n = f"{base}-{n}", n + 1


def _free_product_sku(cur) -> str:
    cur.execute("SELECT COALESCE(MAX(id), 0) AS m FROM products")
    n = int(cur.fetchone()["m"] or 0) + 1
    while True:
        sku = f"MAG-{n:05d}"
        cur.execute("SELECT 1 FROM products WHERE sku = ?", (sku,))
        if not cur.fetchone():
            return sku
        n += 1


def _free_variant_sku(cur, base: str) -> str:
    sku, n = base, 2
    while True:
        cur.execute("SELECT 1 FROM product_variants WHERE sku = ?", (sku,))
        if not cur.fetchone():
            return sku
        sku, n = f"{base}-{n}", n + 1


def _option_label(cur, attribute_id: int, value: str) -> str:
    """The French name of an option ("Noir" for the value "noir"), else the value."""
    cur.execute("SELECT label_fr FROM category_attribute_options WHERE attribute_id = ? AND value = ?", (attribute_id, value))
    row = cur.fetchone()
    return (str(row["label_fr"]).strip() if row and row["label_fr"] else "") or value


def _add_variants(conn, admin_id: int, product: dict, variants: List[StoreVariantIn]) -> List[int]:
    """Creates colours / sizes of a product with their stock and barcode, in
    the caller's transaction. Refuses (409 / 422) before writing anything
    wrong: duplicates in the list or already on the product, a barcode that is
    invalid or already on another article."""
    cur = conn.cursor()
    cat_attrs = load_category_attributes_with_options(conn, product["category_id"])
    cur.execute("SELECT combination_signature, title FROM product_variants WHERE product_id = ?", (product["id"],))
    existing = cur.fetchall()
    taken_sigs = {r["combination_signature"] for r in existing}
    taken_titles = {str(r["title"]).strip().lower() for r in existing}

    prepared = []
    seen_sigs, seen_codes = set(), set()
    for v in variants:
        attrs = validate_variant_attributes(cat_attrs, v.attributes, allow_custom_values=True)
        if attrs:
            title = " / ".join(_option_label(cur, cat_attrs[k]["id"], attrs[k]) for k in sorted(attrs))
            sig = build_variant_signature(attrs)
        else:
            title = (v.title or "").strip() or SINGLE_TITLE
            sig = None
        key = sig or f"title:{title.lower()}"
        if key in seen_sigs or (sig and sig in taken_sigs) or (not sig and title.lower() in taken_titles):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"« {title} » existe déjà pour cet article")
        seen_sigs.add(key)
        code = (v.barcode or "").strip()
        if code:
            check = validate_barcode(code)
            if not check["valid"]:
                raise HTTPException(status_code=422, detail=f"Code-barres invalide: {check['reason']}")
            code = check["normalized"]
            if code in seen_codes:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Le code-barres '{code}' apparaît deux fois")
            conflict = _barcode_in_use(conn, code)
            if conflict:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Code-barres déjà utilisé par {conflict}")
            seen_codes.add(code)
        prepared.append((v, attrs, title, sig, code))

    created = []
    for i, (v, attrs, title, sig, code) in enumerate(prepared, start=1):
        if attrs:
            ensure_variant_attribute_options(conn, cat_attrs, attrs)
            sku = auto_variant_sku(conn, product["sku"], attrs, sig)
        else:
            sku = _free_variant_sku(cur, f"{product['sku']}-{i if len(prepared) > 1 else 'U'}")
            sig = build_variant_signature({}, sku)
        barcode = code or _generate_internal_ean13(conn)
        price = v.price_dzd if v.price_dzd is not None and v.price_dzd != int(product["selling_price_dzd"]) else None
        cur.execute(
            """INSERT INTO product_variants
               (product_id, sku, barcode, title, price_override_dzd, stock_qty, image_url,
                purchase_cost_dzd, low_stock_threshold, is_active, combination_signature)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 2, 1, ?)""",
            (product["id"], sku, barcode, title, price, v.quantity, sig),
        )
        vid = cur.lastrowid
        if attrs:
            replace_variant_attribute_values(conn, vid, cat_attrs, attrs)
        if v.quantity > 0:
            cur.execute(
                """INSERT INTO inventory_movements (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, 0, ?, 'variant_created')""",
                (vid, admin_id, v.quantity, v.quantity),
            )
        created.append(vid)
    return created


def _items(conn, product_ids: List[int]) -> List[dict]:
    """Articles with their colours / sizes, in the order of `product_ids`."""
    if not product_ids:
        return []
    cur = conn.cursor()
    marks = ",".join("?" for _ in product_ids)
    cur.execute(
        f"""SELECT p.id, p.sku, p.name_fr, p.name_ar, p.name_en, p.selling_price_dzd, p.purchase_cost_dzd,
                   p.main_image_url, p.status, COALESCE(p.sales_channel, 'all') AS sales_channel, p.category_id,
                   c.name_fr AS category_fr, c.name_ar AS category_ar, c.name_en AS category_en, p.updated_at
            FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id IN ({marks})""",
        product_ids,
    )
    products = {r["id"]: dict(r) for r in cur.fetchall()}
    cur.execute(
        f"""SELECT id, product_id, sku, barcode, title, price_override_dzd, stock_qty, is_active, low_stock_threshold
            FROM product_variants WHERE product_id IN ({marks}) ORDER BY id""",
        product_ids,
    )
    variants: Dict[int, List[dict]] = {}
    for r in cur.fetchall():
        v = dict(r)
        p = products.get(v["product_id"])
        if not p:
            continue
        v["price_dzd"] = int(v["price_override_dzd"]) if v["price_override_dzd"] is not None else int(p["selling_price_dzd"])
        v["symbology"] = detect_symbology(v["barcode"]) if v["barcode"] else None
        v["is_active"] = bool(v["is_active"])
        variants.setdefault(v["product_id"], []).append(v)
    out = []
    for pid in product_ids:
        p = products.get(pid)
        if not p:
            continue
        vs = variants.get(pid, [])
        active = [v for v in vs if v["is_active"]]
        p["variants"] = vs
        p["total_stock"] = sum(int(v["stock_qty"] or 0) for v in active)
        p["missing_barcodes"] = sum(1 for v in active if not v["barcode"])
        p["sold_online"] = p["sales_channel"] != "store"
        out.append(p)
    return out


def _load_product(cur, product_id: int) -> dict:
    cur.execute("SELECT * FROM products WHERE id = ? AND deleted_at IS NULL", (product_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return dict(row)


def _set_channel(cur, product: dict, sold_online: bool) -> None:
    """Boutique-only makes the article sellable at the till right away."""
    if sold_online:
        cur.execute("UPDATE products SET sales_channel = 'all', updated_at = CURRENT_TIMESTAMP, version = version + 1 WHERE id = ?",
                    (product["id"],))
    else:
        new_status = "published" if product["status"] == "draft" else product["status"]
        cur.execute("UPDATE products SET sales_channel = 'store', status = ?, updated_at = CURRENT_TIMESTAMP, version = version + 1 WHERE id = ?",
                    (new_status, product["id"]))


# ----------------------------------------------------------------- endpoints

@router.get("/api/v1/admin/store/items")
def store_items(
    q: Optional[str] = Query(None, max_length=120),
    show: str = Query("all", regex=r"^(all|store|online|no_barcode|low)$"),
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(require_any_permission(["products:write", "inventory:write"])),
):
    """Articles (newest first), searched by name, reference or barcode."""
    with db_session() as conn:
        cur = conn.cursor()
        where = ["p.deleted_at IS NULL", "p.status <> 'archived'"]
        params: list = []
        term = (q or "").strip()
        if term:
            like = f"%{term}%"
            where.append("""(p.name_fr LIKE ? OR p.name_ar LIKE ? OR p.name_en LIKE ? OR p.sku LIKE ? OR p.barcode = ?
                             OR EXISTS (SELECT 1 FROM product_variants v WHERE v.product_id = p.id
                                        AND (v.barcode = ? OR v.sku LIKE ?)))""")
            params += [like, like, like, like, term, term, like]
        if show == "store":
            where.append("COALESCE(p.sales_channel, 'all') = 'store'")
        elif show == "online":
            where.append("COALESCE(p.sales_channel, 'all') <> 'store'")
        elif show == "no_barcode":
            where.append("EXISTS (SELECT 1 FROM product_variants v WHERE v.product_id = p.id AND v.is_active = 1 AND (v.barcode IS NULL OR TRIM(v.barcode) = ''))")
        elif show == "low":
            where.append("EXISTS (SELECT 1 FROM product_variants v WHERE v.product_id = p.id AND v.is_active = 1 AND v.stock_qty <= v.low_stock_threshold)")
        cond = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) AS n FROM products p WHERE {cond}", params)
        total = int(cur.fetchone()["n"])
        cur.execute(f"SELECT p.id FROM products p WHERE {cond} ORDER BY p.id DESC LIMIT ? OFFSET ?", params + [limit, offset])
        ids = [r["id"] for r in cur.fetchall()]
        cur.execute("""SELECT COUNT(*) AS n FROM product_variants v JOIN products p ON p.id = v.product_id
                       WHERE p.deleted_at IS NULL AND p.status <> 'archived' AND v.is_active = 1
                         AND (v.barcode IS NULL OR TRIM(v.barcode) = '')""")
        missing = int(cur.fetchone()["n"])
        return {
            "items": _items(conn, ids),
            "total": total,
            "missing_barcodes": missing,
            "store_name": _boutique_info_from_settings(conn)["name"],
        }


@router.post("/api/v1/admin/store/items", status_code=201)
def store_quick_add(payload: StoreQuickAddIn, admin: dict = Depends(require_permission("products:write"))):
    """One article with its colours / sizes, quantities and barcodes, in one go."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE id = ? AND deleted_at IS NULL", (payload.category_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Donnez un nom à l'article")
        variants = payload.variants or [StoreVariantIn()]
        sku = _free_product_sku(cur)
        cur.execute(
            """INSERT INTO products
               (category_id, slug, sku, name_fr, name_ar, name_en, description_fr, description_ar, description_en,
                main_image_url, purchase_cost_dzd, selling_price_dzd, status, sales_channel)
               VALUES (?, ?, ?, ?, '', '', '', '', '', ?, ?, ?, 'published', ?)""",
            (payload.category_id, _free_slug(cur, name), sku, name, (payload.image_url or "").strip() or None,
             payload.cost_dzd, payload.price_dzd, "all" if payload.sold_online else "store"),
        )
        pid = cur.lastrowid
        product = _load_product(cur, pid)
        created = _add_variants(conn, int(admin["sub"]), product, variants)
        log_audit(conn, int(admin["sub"]), "store_quick_add", "product", str(pid), {
            "sku": sku, "variants": len(created), "pieces": sum(v.quantity for v in variants),
            "sold_online": payload.sold_online,
        })
        return _items(conn, [pid])[0]


@router.post("/api/v1/admin/store/items/{product_id}/variants", status_code=201)
def store_add_variants(product_id: int, payload: StoreAddVariantsIn, admin: dict = Depends(require_permission("products:write"))):
    """New colours / sizes for an article already in the shop."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        product = _load_product(cur, product_id)
        created = _add_variants(conn, int(admin["sub"]), product, payload.variants)
        cur.execute("UPDATE products SET updated_at = CURRENT_TIMESTAMP, version = version + 1 WHERE id = ?", (product_id,))
        log_audit(conn, int(admin["sub"]), "store_add_variants", "product", str(product_id), {"variants": len(created)})
        return _items(conn, [product_id])[0]


@router.put("/api/v1/admin/store/items/{product_id}")
def store_edit(product_id: int, payload: StoreProductEditIn, admin: dict = Depends(require_permission("products:write"))):
    """Name, price, cost and where it is sold — the rest stays in the Products screen."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        product = _load_product(cur, product_id)
        sets, params = [], []
        if payload.name is not None and payload.name.strip():
            sets.append("name_fr = ?"); params.append(payload.name.strip())
        if payload.price_dzd is not None:
            sets.append("selling_price_dzd = ?"); params.append(payload.price_dzd)
        if payload.cost_dzd is not None:
            sets.append("purchase_cost_dzd = ?"); params.append(payload.cost_dzd)
        if sets:
            cur.execute(f"UPDATE products SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP, version = version + 1 WHERE id = ?",
                        params + [product_id])
        if payload.sold_online is not None:
            _set_channel(cur, product, payload.sold_online)
        log_audit(conn, int(admin["sub"]), "store_edit_item", "product", str(product_id), {
            "fields": [s.split(" =")[0] for s in sets] + (["sales_channel"] if payload.sold_online is not None else []),
        })
        return _items(conn, [product_id])[0]


@router.post("/api/v1/admin/store/variants/{variant_id}/receive")
def store_receive(variant_id: int, payload: StoreReceiveIn,
                  admin: dict = Depends(require_any_permission(["products:write", "inventory:write"]))):
    """New pieces of a colour / size arrived in the shop."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("""SELECT v.id, v.sku, v.stock_qty, v.product_id FROM product_variants v
                       JOIN products p ON p.id = v.product_id WHERE v.id = ? AND p.deleted_at IS NULL""", (variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variante introuvable")
        cur.execute("UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ?", (payload.quantity, variant_id))
        cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (variant_id,))
        new_qty = int(cur.fetchone()["stock_qty"])
        cur.execute(
            """INSERT INTO inventory_movements (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (variant_id, int(admin["sub"]), payload.quantity, new_qty - payload.quantity, new_qty, STORE_RECEIPT),
        )
        log_audit(conn, int(admin["sub"]), "store_receive", "product_variant", str(variant_id), {
            "sku": v["sku"], "quantity": payload.quantity, "new_qty": new_qty,
        })
        return {"variant_id": variant_id, "previous_qty": new_qty - payload.quantity, "new_qty": new_qty,
                "item": _items(conn, [v["product_id"]])[0]}


@router.post("/api/v1/admin/store/items/{product_id}/barcodes")
def store_generate_barcodes(product_id: int, admin: dict = Depends(require_permission("products:write"))):
    """A shop barcode for every colour / size of the article that has none."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        _load_product(cur, product_id)
        n = _fill_missing_barcodes(conn, "AND v.product_id = ?", [product_id])
        if n:
            log_audit(conn, int(admin["sub"]), "store_generate_barcodes", "product", str(product_id), {"generated": n})
        return {"generated": n, "item": _items(conn, [product_id])[0]}


@router.post("/api/v1/admin/store/barcodes/missing")
def store_generate_all_missing(admin: dict = Depends(require_permission("products:write"))):
    """A shop barcode for every article of the shop that has none."""
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        n = _fill_missing_barcodes(conn, "", [])
        if n:
            log_audit(conn, int(admin["sub"]), "store_generate_barcodes", "product", "*", {"generated": n})
        return {"generated": n}


def _fill_missing_barcodes(conn, extra: str, params: list) -> int:
    cur = conn.cursor()
    cur.execute(
        f"""SELECT v.id FROM product_variants v JOIN products p ON p.id = v.product_id
            WHERE p.deleted_at IS NULL AND p.status <> 'archived' AND v.is_active = 1
              AND (v.barcode IS NULL OR TRIM(v.barcode) = '') {extra} ORDER BY v.id""",
        params,
    )
    ids = [r["id"] for r in cur.fetchall()]
    for vid in ids:
        cur.execute("UPDATE product_variants SET barcode = ? WHERE id = ?", (_generate_internal_ean13(conn), vid))
    return len(ids)
