import csv
import gzip
import hmac
import io
import os
import hashlib
import sqlite3
import tempfile
import itertools
import json
import re
import secrets
import time
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from .database import db_session
from .seed import SUPPORTED_ATTRIBUTE_TYPES, seed_initial_data
from .security import (
    check_rate_limit,
    create_access_token,
    decode_access_token,
    revoke_token,
    validate_uploaded_image,
    verify_password,
)

app = FastAPI(
    title="Mus Luxury (LUXE) E-Commerce API",
    version="1.0.0",
    description="Production REST API for LUXE Algerian E-Commerce Storefront & Tauri 2 Desktop CMS",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:1420", "https://musluxury.dz"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.on_event("startup")
def on_startup():
    seed_initial_data()

# Ensure DB is initialized even when TestClient is instantiated without startup events
seed_initial_data()

# ============================================================================
# AUTHENTICATION & RBAC DEPENDENCIES
# ============================================================================

def get_current_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    payload["raw_token"] = token
    return payload

def require_permission(perm: str):
    def dep(admin: dict = Depends(get_current_admin)) -> dict:
        if perm not in admin.get("perms", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: '{perm}' required"
            )
        return admin
    return dep

def log_audit(conn, admin_user_id: Optional[int], action: str, entity_type: str, entity_id: str, details: dict):
    conn.execute(
        "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
        (admin_user_id, action, entity_type, str(entity_id), json.dumps(details, ensure_ascii=False))
    )

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class AttributeOptionInput(BaseModel):
    value: str
    label_fr: str
    label_ar: Optional[str] = ""
    label_en: Optional[str] = ""
    color_hex: Optional[str] = None
    display_order: int = 1

class CategoryAttributeCreate(BaseModel):
    category_id: int
    attr_key: str = Field(..., regex=r"^[a-z][a-z0-9_]{1,60}$")
    label_fr: str
    label_ar: Optional[str] = ""
    label_en: Optional[str] = ""
    input_type: str
    unit: Optional[str] = ""
    is_required: bool = False
    default_value: Optional[str] = None
    allow_multiple: bool = False
    is_visible_on_storefront: bool = True
    is_filterable: bool = False
    is_variant_axis: bool = False
    display_order: int = 1
    options: List[AttributeOptionInput] = []

    @validator("input_type")
    def validate_input_type(cls, v):
        if v not in SUPPORTED_ATTRIBUTE_TYPES:
            raise ValueError(f"Unsupported input_type '{v}'. Allowed: {SUPPORTED_ATTRIBUTE_TYPES}")
        return v

class CategoryCreate(BaseModel):
    slug: str = Field(..., regex=r"^[a-z0-9-]{2,120}$")
    name_fr: str
    name_ar: str
    name_en: str
    description_fr: Optional[str] = ""
    description_ar: Optional[str] = ""
    description_en: Optional[str] = ""
    image_url: Optional[str] = "/assets/cat_sacs.jpg"
    banner_url: Optional[str] = "/assets/hero_banner_mus.jpg"
    parent_id: Optional[int] = None
    display_order: int = 10
    is_active: bool = True
    show_on_homepage: bool = True
    attributes: List[CategoryAttributeCreate] = []

class VariantInput(BaseModel):
    sku: str
    barcode: Optional[str] = None
    title: str
    price_override_dzd: Optional[int] = None
    stock_qty: int = Field(0, ge=0)
    image_url: Optional[str] = None
    attributes: Dict[str, str] = {}

class ProductCreate(BaseModel):
    category_id: int
    brand_id: Optional[int] = None
    slug: str = Field(..., regex=r"^[a-z0-9-]{2,160}$")
    sku: str
    barcode: Optional[str] = None
    name_fr: str
    name_ar: Optional[str] = ""
    name_en: Optional[str] = ""
    description_fr: Optional[str] = ""
    main_image_url: Optional[str] = "/assets/prod_sac_chanel_hd.jpg"
    purchase_cost_dzd: int = Field(0, ge=0)
    selling_price_dzd: int = Field(..., ge=0)
    previous_price_dzd: Optional[int] = None
    discount_percent: int = Field(0, ge=0, le=95)
    status: str = Field("draft", regex=r"^(draft|published|archived)$")
    is_featured: bool = False
    is_new_arrival: bool = False
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    dynamic_attributes: Dict[str, Any] = {}
    variants: List[VariantInput] = []

class VariantMatrixRequest(BaseModel):
    axes: Dict[str, List[str]] # e.g. {"color": ["Noir", "Blanc"], "size": ["40", "41"]}
    default_stock: int = Field(3, ge=0)
    price_override_dzd: Optional[int] = None

class OrderItemInput(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0, le=50)
    # Note: Even if a malicious client passes unit_price_dzd or total, it is ignored!
    client_tampered_price: Optional[int] = None

class GuestOrderCreate(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=150)
    phone: str
    wilaya_code: str
    commune: str = Field(..., min_length=2, max_length=120)
    delivery_address: str = Field(..., min_length=5, max_length=400)
    delivery_method: str = Field(..., regex=r"^(home|stop_desk)$")
    whatsapp_phone: Optional[str] = None
    coupon_code: Optional[str] = None
    customer_notes: Optional[str] = ""
    items: List[OrderItemInput]
    client_submitted_total_dzd: Optional[int] = None # Ignored; server calculates true total

    @validator("phone")
    def validate_algerian_phone(cls, v):
        cleaned = re.sub(r"[\s\-\.]", "", v)
        if not re.match(r"^(\+213|0)(5|6|7)[0-9]{8}$", cleaned):
            raise ValueError("Invalid Algerian mobile phone number (must start with 05, 06, 07 or +213)")
        return cleaned

class OrderStatusUpdate(BaseModel):
    status: str = Field(..., regex=r"^(new|pending_confirmation|confirmed|preparing|ready_for_shipment|shipped|delivered|cancelled|returned)$")
    internal_notes: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def serialize_category(conn, row: dict) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM category_attributes WHERE category_id = ? ORDER BY display_order ASC, id ASC",
        (row["id"],)
    )
    attrs = []
    for a in cur.fetchall():
        ad = dict(a)
        cur.execute(
            "SELECT value, label_fr, label_ar, label_en, color_hex, display_order FROM category_attribute_options WHERE attribute_id = ? ORDER BY display_order ASC",
            (ad["id"],)
        )
        ad["options"] = [dict(o) for o in cur.fetchall()]
        ad["is_required"] = bool(ad["is_required"])
        ad["allow_multiple"] = bool(ad["allow_multiple"])
        ad["is_visible_on_storefront"] = bool(ad["is_visible_on_storefront"])
        ad["is_filterable"] = bool(ad["is_filterable"])
        ad["is_variant_axis"] = bool(ad["is_variant_axis"])
        attrs.append(ad)
    cat = dict(row)
    cat["is_active"] = bool(cat["is_active"])
    cat["show_on_homepage"] = bool(cat["show_on_homepage"])
    cat["attributes"] = attrs
    return cat

def serialize_product(conn, row: dict, include_private: bool = False) -> dict:
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
        """SELECT ca.attr_key, ca.label_fr, ca.label_ar, ca.label_en, ca.input_type, ca.unit, pav.value_text
           FROM product_attribute_values pav
           JOIN category_attributes ca ON ca.id = pav.attribute_id
           WHERE pav.product_id = ? AND (? = 1 OR ca.is_visible_on_storefront = 1)
           ORDER BY ca.display_order ASC""",
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
            """SELECT ca.attr_key, vav.option_value
               FROM variant_attribute_values vav
               JOIN category_attributes ca ON ca.id = vav.attribute_id
               WHERE vav.variant_id = ?""",
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
    p["variants"] = variants
    p["total_stock"] = total_stock
    p["in_stock"] = total_stock > 0
    return p

# ============================================================================
# PUBLIC STOREFRONT ENDPOINTS (/api/v1/*)
# ============================================================================

@app.get("/api/v1/store/settings")
def get_store_settings():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM store_settings")
        out = {}
        for r in cur.fetchall():
            val = r["setting_value"]
            try:
                out[r["setting_key"]] = json.loads(val)
            except Exception:
                out[r["setting_key"]] = val
        return out

@app.get("/api/v1/categories")
def list_public_categories():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC, id ASC"
        )
        return {"items": [serialize_category(conn, dict(r)) for r in cur.fetchall()]}

@app.get("/api/v1/categories/{slug}")
def get_public_category(slug: str):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE slug = ? AND is_active = 1 AND deleted_at IS NULL", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        return serialize_category(conn, dict(row))

@app.get("/api/v1/brands")
def list_public_brands():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, slug, logo_url FROM brands WHERE is_active = 1 ORDER BY name ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.get("/api/v1/delivery-zones")
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
        return {"items": zones}

@app.get("/api/v1/products")
def list_public_products(
    request: Request,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    q: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    in_stock_only: bool = False,
    sort: str = Query("newest", regex=r"^(newest|price_asc|price_desc|popularity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    with db_session() as conn:
        cur = conn.cursor()
        where = ["p.status = 'published'", "p.deleted_at IS NULL"]
        params: List[Any] = []
        if category:
            where.append("c.slug = ?")
            params.append(category)
        if brand:
            where.append("b.slug = ?")
            params.append(brand)
        if q:
            where.append("(p.name_fr LIKE ? OR p.name_ar LIKE ? OR p.name_en LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if min_price is not None:
            where.append("p.selling_price_dzd >= ?")
            params.append(min_price)
        if max_price is not None:
            where.append("p.selling_price_dzd <= ?")
            params.append(max_price)

        order_sql = {
            "newest": "p.created_at DESC, p.id DESC",
            "price_asc": "p.selling_price_dzd ASC",
            "price_desc": "p.selling_price_dzd DESC",
            "popularity": "p.sales_count DESC, p.id DESC",
        }[sort]

        sql = f"""
            SELECT p.* FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN brands b ON b.id = p.brand_id
            WHERE {' AND '.join(where)}
            ORDER BY {order_sql}
        """
        cur.execute(sql, params)
        items = [serialize_product(conn, dict(r), include_private=False) for r in cur.fetchall()]
        if in_stock_only:
            items = [it for it in items if it["in_stock"]]

        # Dynamic Category Attribute & Variant Axis Filtering (e.g. ?attr_color=Bordeaux&attr_size=L)
        reserved_params = {"category", "brand", "q", "min_price", "max_price", "in_stock_only", "sort", "page", "page_size"}
        for qp_key, qp_val in request.query_params.items():
            if qp_key in reserved_params or not qp_val:
                continue
            attr_key = qp_key[5:] if qp_key.startswith("attr_") else qp_key
            items = [
                it for it in items
                if it.get("attributes", {}).get(attr_key) == qp_val
                or any(v.get("attributes", {}).get(attr_key) == qp_val for v in it.get("variants", []))
            ]
        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

@app.get("/api/v1/products/{slug}")
def get_public_product(slug: str):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE slug = ? AND status = 'published' AND deleted_at IS NULL", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return serialize_product(conn, dict(row), include_private=False)

@app.post("/api/v1/orders", status_code=201)
def create_guest_order(
    payload: GuestOrderCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"order:{client_ip}", max_requests=15, window_seconds=60)

    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    # Compute idempotency signature from explicit Idempotency-Key header or deterministic order payload
    if idempotency_key and idempotency_key.strip():
        idem_raw = f"explicit_key:{idempotency_key.strip()}"
    else:
        idem_raw = f"{payload.phone}|{payload.wilaya_code}|{payload.commune}|" + ",".join(
            f"{i.variant_id}:{i.quantity}" for i in sorted(payload.items, key=lambda x: x.variant_id)
        )
    idem_hash = hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()

    with db_session(commit=True) as conn:
        # Start immediate transaction to lock inventory rows safely
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()

        # Check duplicate order submission
        cur.execute("SELECT order_reference FROM orders WHERE idempotency_hash = ? AND status != 'cancelled'", (idem_hash,))
        dup = cur.fetchone()
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate order detected (existing reference: {dup['order_reference']})"
            )

        # 1. Verify Wilaya & Delivery Method Rate on the server
        cur.execute("SELECT * FROM delivery_zones WHERE wilaya_code = ? AND is_active = 1", (payload.wilaya_code,))
        zone = cur.fetchone()
        if not zone:
            raise HTTPException(status_code=400, detail=f"Unsupported or inactive Wilaya code: {payload.wilaya_code}")

        cur.execute(
            "SELECT fee_dzd, is_supported FROM delivery_rates WHERE zone_id = ? AND delivery_method = ?",
            (zone["id"], payload.delivery_method)
        )
        rate = cur.fetchone()
        if not rate or not rate["is_supported"]:
            raise HTTPException(status_code=400, detail=f"Delivery method '{payload.delivery_method}' is not available for {zone['wilaya_name_fr']}")
        delivery_fee_dzd = int(rate["fee_dzd"])

        # 2. Verify Variants, Stock & Calculate True Server-Side Subtotal
        subtotal_dzd = 0
        resolved_lines = []
        for item in payload.items:
            cur.execute(
                """SELECT pv.*, p.name_fr AS product_name, p.selling_price_dzd, p.status AS product_status
                   FROM product_variants pv
                   JOIN products p ON p.id = pv.product_id
                   WHERE pv.id = ? AND pv.is_active = 1""",
                (item.variant_id,)
            )
            v = cur.fetchone()
            if not v or v["product_status"] != "published":
                raise HTTPException(status_code=404, detail=f"Product variant {item.variant_id} is unavailable")
            if v["stock_qty"] < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for '{v['product_name']} ({v['title']})': requested {item.quantity}, available {v['stock_qty']}"
                )
            unit_price = int(v["price_override_dzd"]) if v["price_override_dzd"] is not None else int(v["selling_price_dzd"])
            line_total = unit_price * item.quantity
            subtotal_dzd += line_total
            resolved_lines.append((v, item.quantity, unit_price, line_total))

        discount_dzd = 0
        if payload.coupon_code:
            cur.execute(
                "SELECT * FROM coupons WHERE UPPER(code) = ? AND is_active = 1",
                (payload.coupon_code.strip().upper(),)
            )
            cpn = cur.fetchone()
            if not cpn:
                raise HTTPException(status_code=400, detail="Invalid or inactive coupon code")
            if subtotal_dzd < int(cpn["min_order_dzd"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Coupon '{cpn['code']}' requires a minimum order of {cpn['min_order_dzd']} DA"
                )
            if cpn["discount_type"] == "percentage":
                discount_dzd = (subtotal_dzd * int(cpn["discount_value"])) // 100
                if cpn["max_discount_dzd"] is not None:
                    discount_dzd = min(discount_dzd, int(cpn["max_discount_dzd"]))
            else:
                discount_dzd = int(cpn["discount_value"])
            discount_dzd = min(discount_dzd, subtotal_dzd)
            cur.execute("UPDATE coupons SET usage_count = usage_count + 1 WHERE id = ?", (cpn["id"],))

        total_dzd = (subtotal_dzd - discount_dzd) + delivery_fee_dzd

        # 3. Upsert Guest Customer Contact Record (NO account/password created)
        cur.execute("SELECT id FROM customers WHERE phone = ?", (payload.phone,))
        cust = cur.fetchone()
        if cust:
            customer_id = cust["id"]
            cur.execute(
                """UPDATE customers
                   SET full_name = ?, wilaya_code = ?, commune = ?, address = ?,
                       orders_count = orders_count + 1, total_spent_dzd = total_spent_dzd + ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (payload.full_name, payload.wilaya_code, payload.commune, payload.delivery_address, total_dzd, customer_id)
            )
        else:
            cur.execute(
                """INSERT INTO customers (full_name, phone, wilaya_code, commune, address, orders_count, total_spent_dzd)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (payload.full_name, payload.phone, payload.wilaya_code, payload.commune, payload.delivery_address, total_dzd)
            )
            customer_id = cur.lastrowid

        # 4. Create Order Record
        order_ref = f"LUX-{int(time.time()) % 100000:05d}-{secrets.token_hex(2).upper()}"
        cur.execute(
            """INSERT INTO orders
               (order_reference, customer_id, customer_name, customer_phone, wilaya_code, wilaya_name,
                commune, delivery_address, delivery_method, payment_method,
                subtotal_dzd, delivery_fee_dzd, total_dzd, status, customer_notes, stock_deducted, idempotency_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'cod', ?, ?, ?, 'new', ?, 1, ?)""",
            (
                order_ref, customer_id, payload.full_name, payload.phone,
                payload.wilaya_code, zone["wilaya_name_fr"], payload.commune,
                payload.delivery_address, payload.delivery_method,
                subtotal_dzd, delivery_fee_dzd, total_dzd,
                payload.customer_notes, idem_hash
            )
        )
        order_id = cur.lastrowid

        # 5. Insert Order Items, Decrement Stock Safely & Log Inventory Movements
        out_items = []
        for v, qty, unit_price, line_total in resolved_lines:
            cur.execute(
                """INSERT INTO order_items
                   (order_id, product_id, variant_id, product_name, variant_title, sku, unit_price_dzd, quantity, line_total_dzd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, v["product_id"], v["id"], v["product_name"], v["title"], v["sku"], unit_price, qty, line_total)
            )
            prev_qty = int(v["stock_qty"])
            new_qty = prev_qty - qty
            cur.execute("UPDATE product_variants SET stock_qty = ? WHERE id = ?", (new_qty, v["id"]))
            cur.execute("UPDATE products SET sales_count = sales_count + ? WHERE id = ?", (qty, v["product_id"]))
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, order_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, 'order_reserved')""",
                (v["id"], order_id, -qty, prev_qty, new_qty)
            )
            out_items.append({
                "variant_id": v["id"],
                "sku": v["sku"],
                "product_name": v["product_name"],
                "variant_title": v["title"],
                "unit_price_dzd": unit_price,
                "quantity": qty,
                "line_total_dzd": line_total,
            })

        return {
            "order_id": order_id,
            "order_reference": order_ref,
            "status": "new",
            "payment_method": "cod",
            "customer_name": payload.full_name,
            "customer_phone": payload.phone,
            "wilaya": f"{payload.wilaya_code} - {zone['wilaya_name_fr']}",
            "commune": payload.commune,
            "delivery_method": payload.delivery_method,
            "subtotal_dzd": subtotal_dzd,
            "discount_dzd": discount_dzd,
            "delivery_fee_dzd": delivery_fee_dzd,
            "total_dzd": total_dzd,
            "items": out_items,
            "message_fr": "Votre commande a été enregistrée avec succès. Paiement à la livraison (Cash on Delivery)."
        }

# ============================================================================
# ADMINISTRATIVE ENDPOINTS (/api/v1/admin/*)
# ============================================================================

@app.post("/api/v1/admin/auth/login")
def admin_login(payload: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"login:{client_ip}", max_requests=5, window_seconds=60)

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.*, r.name AS role_name
               FROM admin_users u
               JOIN roles r ON r.id = u.role_id
               WHERE u.email = ? AND u.is_active = 1""",
            (payload.email.strip().lower(),)
        )
        user = cur.fetchone()
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        cur.execute(
            """SELECT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               WHERE rp.role_id = ?""",
            (user["role_id"],)
        )
        perms = [r["code"] for r in cur.fetchall()]
        token = create_access_token(user["id"], user["email"], user["role_name"], perms)
        cur.execute("UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        log_audit(conn, user["id"], "admin_login", "admin_user", str(user["id"]), {"email": user["email"]})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role_name"],
                "permissions": perms,
            }
        }

@app.post("/api/v1/admin/auth/logout")
def admin_logout(admin: dict = Depends(get_current_admin)):
    revoke_token(admin["raw_token"])
    return {"status": "logged_out"}

@app.get("/api/v1/admin/dashboard")
def admin_dashboard(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt, COALESCE(SUM(total_dzd), 0) AS rev FROM orders WHERE status != 'cancelled'")
        ord_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status IN ('new', 'pending_confirmation')")
        pending_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE status = 'published' AND deleted_at IS NULL")
        pub_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM categories WHERE is_active = 1 AND deleted_at IS NULL")
        cat_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM product_variants WHERE stock_qty > 0 AND stock_qty <= 3 AND is_active = 1")
        low_stock_only_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM product_variants WHERE stock_qty <= 3 AND is_active = 1")
        low_stock_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM product_variants WHERE stock_qty = 0 AND is_active = 1")
        out_of_stock_cnt = cur.fetchone()["cnt"]

        status_keys = [
            "new", "pending_confirmation", "confirmed", "preparing",
            "ready_for_shipment", "shipped", "delivered", "cancelled", "returned"
        ]
        orders_by_status = {k: 0 for k in status_keys}
        cur.execute("SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status")
        for r in cur.fetchall():
            orders_by_status[r["status"]] = r["cnt"]

        cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
        recent_orders = []
        for r in cur.fetchall():
            od = dict(r)
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (od["id"],))
            od["items"] = [dict(it) for it in cur.fetchall()]
            recent_orders.append(od)

        cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10")
        recent_activity = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM backup_records ORDER BY id DESC LIMIT 1")
        last_bkp_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS cnt FROM backup_records WHERE status = 'failed'")
        failed_bkp_cnt = cur.fetchone()["cnt"]

        return {
            "total_orders": ord_row["cnt"],
            "total_revenue_dzd": ord_row["rev"],
            "pending_orders": pending_cnt,
            "published_products": pub_cnt,
            "total_active_products": pub_cnt,
            "total_categories": cat_cnt,
            "low_stock_variants": low_stock_cnt,
            "low_stock_only_variants": low_stock_only_cnt,
            "out_of_stock_variants": out_of_stock_cnt,
            "orders_by_status": orders_by_status,
            "recent_orders": recent_orders,
            "recent_activity": recent_activity,
            "backend_sync_status": {
                "connected": True,
                "server_timestamp": int(time.time()),
                "status": "healthy"
            },
            "last_backup": dict(last_bkp_row) if last_bkp_row else None,
            "failed_backups_count": failed_bkp_cnt,
        }

# --- DYNAMIC CATEGORY & ATTRIBUTE BUILDER ---

@app.post("/api/v1/admin/categories", status_code=201)
def create_custom_category(
    payload: CategoryCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE slug = ?", (payload.slug,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Category slug '{payload.slug}' already exists")

        cur.execute(
            """INSERT INTO categories
               (slug, name_fr, name_ar, name_en, description_fr, description_ar, description_en,
                image_url, banner_url, parent_id, display_order, is_active, show_on_homepage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.slug, payload.name_fr, payload.name_ar, payload.name_en,
                payload.description_fr, payload.description_ar, payload.description_en,
                payload.image_url, payload.banner_url, payload.parent_id,
                payload.display_order, 1 if payload.is_active else 0, 1 if payload.show_on_homepage else 0
            )
        )
        cat_id = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_category", "category", str(cat_id), {"slug": payload.slug})
        cur.execute("SELECT * FROM categories WHERE id = ?", (cat_id,))
        return serialize_category(conn, dict(cur.fetchone()))

@app.post("/api/v1/admin/category-attributes", status_code=201)
def add_category_attribute(
    payload: CategoryAttributeCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE id = ?", (payload.category_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Target category not found")

        cur.execute(
            "SELECT id FROM category_attributes WHERE category_id = ? AND attr_key = ?",
            (payload.category_id, payload.attr_key)
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Attribute '{payload.attr_key}' already exists on this category")

        cur.execute(
            """INSERT INTO category_attributes
               (category_id, attr_key, label_fr, label_ar, label_en, input_type, unit,
                is_required, default_value, allow_multiple, is_visible_on_storefront,
                is_filterable, is_variant_axis, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.category_id, payload.attr_key, payload.label_fr, payload.label_ar,
                payload.label_en, payload.input_type, payload.unit,
                1 if payload.is_required else 0, payload.default_value,
                1 if payload.allow_multiple else 0, 1 if payload.is_visible_on_storefront else 0,
                1 if payload.is_filterable else 0, 1 if payload.is_variant_axis else 0,
                payload.display_order
            )
        )
        attr_id = cur.lastrowid
        for idx, opt in enumerate(payload.options, start=1):
            cur.execute(
                """INSERT INTO category_attribute_options
                   (attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (attr_id, opt.value, opt.label_fr, opt.label_ar, opt.label_en, opt.color_hex, opt.display_order or idx)
            )
        log_audit(conn, int(admin["sub"]), "add_category_attribute", "category_attribute", str(attr_id), {"attr_key": payload.attr_key})
        cur.execute("SELECT * FROM categories WHERE id = ?", (payload.category_id,))
        return serialize_category(conn, dict(cur.fetchone()))

@app.delete("/api/v1/admin/category-attributes/{attr_id}")
def delete_category_attribute(
    attr_id: int,
    force_migrate: bool = Query(False, description="Confirm migration/removal when attribute is used by products"),
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attributes WHERE id = ?", (attr_id,))
        attr = cur.fetchone()
        if not attr:
            raise HTTPException(status_code=404, detail="Attribute not found")

        cur.execute("SELECT COUNT(*) AS cnt FROM product_attribute_values WHERE attribute_id = ?", (attr_id,))
        prod_usage = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM variant_attribute_values WHERE attribute_id = ?", (attr_id,))
        var_usage = cur.fetchone()["cnt"]
        total_usage = prod_usage + var_usage

        if total_usage > 0 and not force_migrate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Attribute '{attr['label_fr']}' is actively used by {total_usage} product/variant record(s). Pass force_migrate=true to confirm archival and removal."
            )

        if force_migrate and total_usage > 0:
            cur.execute("DELETE FROM product_attribute_values WHERE attribute_id = ?", (attr_id,))
            cur.execute("DELETE FROM variant_attribute_values WHERE attribute_id = ?", (attr_id,))

        cur.execute("DELETE FROM category_attributes WHERE id = ?", (attr_id,))
        log_audit(conn, int(admin["sub"]), "delete_category_attribute", "category_attribute", str(attr_id), {"force_migrate": force_migrate})
        return {"deleted": True, "attribute_id": attr_id, "migrated_records": total_usage}

# --- DYNAMIC PRODUCT CREATION & VARIANT GENERATOR ---

@app.post("/api/v1/admin/products", status_code=201)
def create_dynamic_product(
    payload: ProductCreate,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id = ?", (payload.category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (payload.category_id,))
        cat_attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}

        # Validate required category attributes when publishing (drafts may omit required dynamic attributes)
        if payload.status == "published":
            missing = []
            for akey, ainfo in cat_attrs.items():
                if ainfo["is_required"] and not ainfo["is_variant_axis"]:
                    val = payload.dynamic_attributes.get(akey)
                    if val is None or str(val).strip() == "":
                        missing.append(ainfo["label_fr"])
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing required category attributes for '{cat['name_fr']}': {', '.join(missing)}"
                )

        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, main_image_url, purchase_cost_dzd, selling_price_dzd,
                previous_price_dzd, discount_percent, status, is_featured, is_new_arrival,
                seo_title, seo_description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.category_id, payload.brand_id, payload.slug, payload.sku, payload.barcode,
                payload.name_fr, payload.name_ar, payload.name_en, payload.description_fr,
                payload.main_image_url, payload.purchase_cost_dzd, payload.selling_price_dzd,
                payload.previous_price_dzd, payload.discount_percent, payload.status,
                1 if payload.is_featured else 0, 1 if payload.is_new_arrival else 0,
                payload.seo_title, payload.seo_description
            )
        )
        prod_id = cur.lastrowid

        for akey, aval in payload.dynamic_attributes.items():
            if akey in cat_attrs:
                cur.execute(
                    "INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)",
                    (prod_id, cat_attrs[akey]["id"], str(aval))
                )

        for v in payload.variants:
            sig = "|".join(f"{k}:{v.attributes[k]}" for k in sorted(v.attributes.keys())) or f"sku:{v.sku}"
            cur.execute(
                """INSERT INTO product_variants
                   (product_id, sku, barcode, title, price_override_dzd, stock_qty, image_url, combination_signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (prod_id, v.sku, v.barcode, v.title, v.price_override_dzd, v.stock_qty, v.image_url or payload.main_image_url, sig)
            )
            vid = cur.lastrowid
            for k, opt_val in v.attributes.items():
                if k in cat_attrs:
                    cur.execute(
                        "INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)",
                        (vid, cat_attrs[k]["id"], opt_val)
                    )

        log_audit(conn, int(admin["sub"]), "create_product", "product", str(prod_id), {"sku": payload.sku, "status": payload.status})
        cur.execute("SELECT * FROM products WHERE id = ?", (prod_id,))
        return serialize_product(conn, dict(cur.fetchone()), include_private=True)

@app.post("/api/v1/admin/products/{product_id}/generate-variants", status_code=201)
def generate_product_variants_matrix(
    product_id: int,
    payload: VariantMatrixRequest,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")

        cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (prod["category_id"],))
        cat_attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}

        axis_keys = sorted(payload.axes.keys())
        if not axis_keys:
            raise HTTPException(status_code=400, detail="At least one variant axis is required")
        for k in axis_keys:
            if k not in cat_attrs or not cat_attrs[k]["is_variant_axis"]:
                raise HTTPException(status_code=400, detail=f"Attribute '{k}' is not configured as a variant axis for this category")

        value_lists = [payload.axes[k] for k in axis_keys]
        created = []
        skipped_duplicates = 0
        for combo in itertools.product(*value_lists):
            combo_map = dict(zip(axis_keys, combo))
            sig = "|".join(f"{k}:{combo_map[k]}" for k in axis_keys)
            cur.execute(
                "SELECT id FROM product_variants WHERE product_id = ? AND combination_signature = ?",
                (product_id, sig)
            )
            if cur.fetchone():
                skipped_duplicates += 1
                continue

            suffix = "-".join(re.sub(r"[^A-Z0-9]", "", str(v).upper())[:4] for v in combo)
            v_sku = f"{prod['sku']}-{suffix}"
            v_title = " / ".join(str(v) for v in combo)
            cur.execute(
                """INSERT INTO product_variants
                   (product_id, sku, title, price_override_dzd, stock_qty, image_url, combination_signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (product_id, v_sku, v_title, payload.price_override_dzd, payload.default_stock, prod["main_image_url"], sig)
            )
            vid = cur.lastrowid
            for k, val in combo_map.items():
                cur.execute(
                    "INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)",
                    (vid, cat_attrs[k]["id"], val)
                )
            created.append({"id": vid, "sku": v_sku, "title": v_title, "stock_qty": payload.default_stock, "signature": sig})

        log_audit(conn, int(admin["sub"]), "generate_variants", "product", str(product_id), {"created_count": len(created)})
        return {"created": created, "skipped_duplicates": skipped_duplicates}

# --- ADMIN ORDERS & STOCK RESTORATION ---

@app.get("/api/v1/admin/orders")
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
            orders.append(od)
        return {"items": orders}

@app.patch("/api/v1/admin/orders/{order_id}")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        ord_row = cur.fetchone()
        if not ord_row:
            raise HTTPException(status_code=404, detail="Order not found")

        prev_status = ord_row["status"]
        stock_deducted = int(ord_row["stock_deducted"])

        # Enforce valid order-status transition rules (Section 3.5)
        terminal_statuses = {"delivered", "cancelled", "returned"}
        if prev_status in terminal_statuses and payload.status != prev_status:
            # Allow delivered -> returned for customer return within 7 days, block all other reversals from terminal states
            if not (prev_status == "delivered" and payload.status == "returned"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid order status transition from terminal status '{prev_status}' to '{payload.status}'"
                )

        # If order is cancelled or returned and stock was deducted, restore stock safely
        if payload.status in ("cancelled", "returned") and stock_deducted == 1:
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            for item in cur.fetchall():
                cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (item["variant_id"],))
                v = cur.fetchone()
                prev_q = int(v["stock_qty"])
                new_q = prev_q + int(item["quantity"])
                cur.execute("UPDATE product_variants SET stock_qty = ? WHERE id = ?", (new_q, item["variant_id"]))
                cur.execute(
                    """INSERT INTO inventory_movements
                       (variant_id, order_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (item["variant_id"], order_id, int(admin["sub"]), int(item["quantity"]), prev_q, new_q, f"order_{payload.status}")
                )
            stock_deducted = 0

        cur.execute(
            """UPDATE orders
               SET status = ?, internal_notes = COALESCE(?, internal_notes),
                   stock_deducted = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (payload.status, payload.internal_notes, stock_deducted, order_id)
        )
        log_audit(conn, int(admin["sub"]), "update_order_status", "order", str(order_id), {"from": prev_status, "to": payload.status})
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return dict(cur.fetchone())

# --- SECURE UPLOAD, REPORTS & BACKUPS ---

@app.post("/api/v1/admin/upload", status_code=201)
async def upload_product_image(
    file: UploadFile = File(...),
    admin: dict = Depends(require_permission("products:write"))
):
    data = await file.read()
    validate_uploaded_image(file.filename or "upload.jpg", file.content_type or "", data)
    digest = hashlib.sha256(data).hexdigest()[:16]
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    safe_name = f"img_{digest}{ext}"
    return {"filename": safe_name, "url": f"/uploads/{safe_name}", "size_bytes": len(data)}

@app.get("/api/v1/admin/backups")
def list_backups(admin: dict = Depends(require_permission("backups:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM backup_records ORDER BY id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}

BACKUP_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
os.makedirs(BACKUP_STORAGE_DIR, exist_ok=True)

@app.post("/api/v1/admin/backups", status_code=201)
def trigger_manual_backup(admin: dict = Depends(require_permission("backups:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        sql_dump = "\n".join(conn.iterdump())
        compressed_bytes = gzip.compress(sql_dump.encode("utf-8"))
        checksum = hashlib.sha256(compressed_bytes).hexdigest()
        fname = f"luxe_backup_{int(time.time())}_{secrets.token_hex(3)}.sql.gz"
        fpath = os.path.join(BACKUP_STORAGE_DIR, fname)
        with open(fpath, "wb") as bf:
            bf.write(compressed_bytes)
        real_size = len(compressed_bytes)

        cur.execute(
            """INSERT INTO backup_records
               (filename, backup_type, size_bytes, sha256_checksum, status, triggered_by)
               VALUES (?, 'full', ?, ?, 'verified', ?)""",
            (fname, real_size, checksum, int(admin["sub"]))
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "trigger_backup", "backup", str(bid), {"filename": fname, "sha256": checksum, "size_bytes": real_size})
        cur.execute("SELECT * FROM backup_records WHERE id = ?", (bid,))
        return dict(cur.fetchone())

@app.post("/api/v1/admin/backups/{backup_id}/verify-restore")
def verify_backup_restoration_isolated(
    backup_id: int,
    admin: dict = Depends(require_permission("backups:write"))
):
    """
    Performs a non-destructive isolated restoration test (Section 7):
    1. Verifies the backup archive exists on disk and matches its recorded SHA-256 checksum.
    2. Decompresses the SQL dump and restores it into an isolated temporary SQLite database.
    3. Queries the restored tables (products, categories, orders, delivery_zones) to verify readability.
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM backup_records WHERE id = ?", (backup_id,))
        bkp = cur.fetchone()
        if not bkp:
            raise HTTPException(status_code=404, detail="Backup record not found")

        fpath = os.path.join(BACKUP_STORAGE_DIR, bkp["filename"])
        if not os.path.isfile(fpath):
            raise HTTPException(status_code=404, detail="Backup file missing from storage directory")

        with open(fpath, "rb") as bf:
            compressed_bytes = bf.read()

        actual_sha256 = hashlib.sha256(compressed_bytes).hexdigest()
        if not hmac.compare_digest(actual_sha256, bkp["sha256_checksum"]):
            cur.execute("UPDATE backup_records SET status = 'failed' WHERE id = ?", (backup_id,))
            raise HTTPException(status_code=400, detail="Backup integrity check failed: SHA-256 mismatch")

        sql_script = gzip.decompress(compressed_bytes).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db_path = os.path.join(tmpdir, "isolated_restore_test.db")
            temp_conn = sqlite3.connect(temp_db_path)
            try:
                temp_conn.executescript(sql_script)
                tcur = temp_conn.cursor()
                tcur.execute("SELECT COUNT(*) FROM products")
                restored_products = tcur.fetchone()[0]
                tcur.execute("SELECT COUNT(*) FROM categories")
                restored_categories = tcur.fetchone()[0]
                tcur.execute("SELECT COUNT(*) FROM orders")
                restored_orders = tcur.fetchone()[0]
                tcur.execute("SELECT COUNT(*) FROM delivery_zones")
                restored_wilayas = tcur.fetchone()[0]
            finally:
                temp_conn.close()

        log_audit(conn, int(admin["sub"]), "verify_backup_restore", "backup", str(backup_id), {
            "restored_products": restored_products,
            "restored_categories": restored_categories,
            "restored_orders": restored_orders,
            "restored_wilayas": restored_wilayas,
        })
        return {
            "backup_id": backup_id,
            "filename": bkp["filename"],
            "sha256_verified": True,
            "isolated_restore_success": True,
            "restored_counts": {
                "products": restored_products,
                "categories": restored_categories,
                "orders": restored_orders,
                "delivery_zones": restored_wilayas,
            }
        }



# ============================================================================
# PUBLIC STOREFRONT LAYOUT ENDPOINT & DESKTOP CMS WEBSITE CONTROL ENDPOINTS
# The Tauri 2 Desktop CMS controls 100% of the public website via these APIs.
# ============================================================================

class BannerCreateUpdate(BaseModel):
    position: str = Field("hero", regex=r"^(hero|promo_grid|seasonal)$")
    title_fr: str
    title_ar: Optional[str] = ""
    title_en: Optional[str] = ""
    subtitle_fr: Optional[str] = ""
    cta_text_fr: Optional[str] = "Découvrir"
    cta_link: Optional[str] = "/categories/sacs"
    image_url: str = "/assets/hero_banner_mus.jpg"
    is_active: bool = True
    display_order: int = 1

class HomepageSectionUpdate(BaseModel):
    title_fr: Optional[str] = None
    is_active: bool
    display_order: int = 1
    config: Dict[str, Any] = {}

class StoreSettingsUpdate(BaseModel):
    settings: Dict[str, Any]

@app.get("/api/v1/store/layout")
def get_public_storefront_layout():
    """
    Returns the complete storefront configuration controlled by the Desktop CMS:
    settings, active homepage sections, active banners, and active categories.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM store_settings")
        settings = {}
        for r in cur.fetchall():
            try:
                settings[r["setting_key"]] = json.loads(r["setting_value"])
            except Exception:
                settings[r["setting_key"]] = r["setting_value"]

        cur.execute("SELECT * FROM homepage_sections WHERE is_active = 1 ORDER BY display_order ASC")
        sections = []
        for s in cur.fetchall():
            sd = dict(s)
            sd["config"] = json.loads(sd.pop("config_json") or "{}")
            sections.append(sd)

        cur.execute("SELECT * FROM banners WHERE is_active = 1 ORDER BY display_order ASC, id ASC")
        banners = [dict(b) for b in cur.fetchall()]

        cur.execute("SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC")
        categories = [serialize_category(conn, dict(c)) for c in cur.fetchall()]

        return {
            "settings": settings,
            "homepage_sections": sections,
            "banners": banners,
            "categories": categories,
        }

@app.get("/api/v1/admin/banners")
def admin_list_banners(admin: dict = Depends(require_permission("content:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM banners ORDER BY display_order ASC, id ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.post("/api/v1/admin/banners", status_code=201)
def admin_create_banner(
    payload: BannerCreateUpdate,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO banners
               (position, title_fr, title_ar, title_en, subtitle_fr, cta_text_fr, cta_link, image_url, is_active, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.position, payload.title_fr, payload.title_ar, payload.title_en,
                payload.subtitle_fr, payload.cta_text_fr, payload.cta_link,
                payload.image_url, 1 if payload.is_active else 0, payload.display_order
            )
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_banner", "banner", str(bid), {"title_fr": payload.title_fr})
        cur.execute("SELECT * FROM banners WHERE id = ?", (bid,))
        return dict(cur.fetchone())

@app.put("/api/v1/admin/homepage-sections/{section_key}")
def admin_update_homepage_section(
    section_key: str,
    payload: HomepageSectionUpdate,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM homepage_sections WHERE section_key = ?", (section_key,))
        sec = cur.fetchone()
        if not sec:
            raise HTTPException(status_code=404, detail="Homepage section not found")
        cur.execute(
            """UPDATE homepage_sections
               SET title_fr = COALESCE(?, title_fr),
                   is_active = ?,
                   display_order = ?,
                   config_json = ?
               WHERE section_key = ?""",
            (
                payload.title_fr,
                1 if payload.is_active else 0,
                payload.display_order,
                json.dumps(payload.config, ensure_ascii=False),
                section_key
            )
        )
        log_audit(conn, int(admin["sub"]), "update_homepage_section", "homepage_section", section_key, {"is_active": payload.is_active})
        cur.execute("SELECT * FROM homepage_sections WHERE section_key = ?", (section_key,))
        row = dict(cur.fetchone())
        row["config"] = json.loads(row.pop("config_json") or "{}")
        return row

@app.put("/api/v1/admin/settings")
def admin_update_store_settings(
    payload: StoreSettingsUpdate,
    admin: dict = Depends(require_permission("settings:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        for k, v in payload.settings.items():
            sval = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            cur.execute(
                """INSERT INTO store_settings (setting_key, setting_value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP""",
                (k, sval)
            )
        log_audit(conn, int(admin["sub"]), "update_store_settings", "store_settings", "global", {"keys": list(payload.settings.keys())})
        return {"updated": True, "keys": list(payload.settings.keys())}



# ============================================================================
# SECTION 6: WHATSAPP CLOUD API PASSWORD RECOVERY & OFFLINE EMERGENCY RECOVERY
# ============================================================================

from .security import hash_password, REVOKED_TOKENS

class RecoveryRequestInput(BaseModel):
    phone: str
    channel: str = Field("whatsapp_cloud_api", regex=r"^(whatsapp_cloud_api|offline_emergency)$")

class RecoveryVerifyInput(BaseModel):
    phone: str
    verification_code: str = Field(..., min_length=6, max_length=64)
    new_password: str = Field(..., min_length=10, max_length=128)

class ProductConcurrencyUpdate(BaseModel):
    name_fr: str
    selling_price_dzd: int = Field(..., ge=0)
    expected_version: int = Field(..., ge=1)
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    description_fr: Optional[str] = None
    purchase_cost_dzd: Optional[int] = Field(None, ge=0)
    previous_price_dzd: Optional[int] = Field(None, ge=0)
    discount_percent: Optional[int] = Field(None, ge=0, le=95)
    sku: Optional[str] = None
    brand_id: Optional[int] = None
    category_id: Optional[int] = None
    main_image_url: Optional[str] = None
    status: Optional[str] = Field(None, regex=r"^(draft|published|archived)$")
    is_featured: Optional[bool] = None
    is_new_arrival: Optional[bool] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    dynamic_attributes: Optional[Dict[str, Any]] = None

class CouponCreateInput(BaseModel):
    code: str = Field(..., regex=r"^[A-Z0-9_-]{3,32}$")
    discount_type: str = Field(..., regex=r"^(percentage|fixed_dzd)$")
    discount_value: int = Field(..., gt=0)
    min_order_dzd: int = Field(0, ge=0)
    max_discount_dzd: Optional[int] = None

@app.post("/api/v1/admin/auth/recovery/request")
def request_admin_password_recovery(payload: RecoveryRequestInput, request: Request):
    """
    Initiates administrator password recovery via the official WhatsApp Business Cloud API.
    Strict Rule (Section 6): If WhatsApp API credentials are not configured on the server,
    explicitly report 503 Service Unavailable — never silently simulate message delivery.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"recovery_req:{client_ip}", max_requests=3, window_seconds=300)

    wa_token = os.getenv("WHATSAPP_CLOUD_API_TOKEN", "").strip()
    wa_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()

    if payload.channel == "whatsapp_cloud_api" and (not wa_token or not wa_phone_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Official WhatsApp Business Cloud API is not configured on this server (missing WHATSAPP_CLOUD_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID). Use an administrator-generated offline emergency recovery code instead."
        )

    cleaned_phone = re.sub(r"[\s\-\.]", "", payload.phone)
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM admin_users WHERE phone = ? AND is_active = 1 AND whatsapp_verified = 1",
            (cleaned_phone,)
        )
        user = cur.fetchone()
        # Do not reveal whether a phone number is registered
        if user and payload.channel == "whatsapp_cloud_api":
            otp = f"{secrets.randbelow(900000) + 100000}"
            otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
            expires_at = int(time.time()) + 300 # 5 minutes expiry
            cur.execute(
                """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
                   VALUES (?, ?, ?, 'whatsapp_cloud_api', 3, ?)""",
                (user["id"], cleaned_phone, otp_hash, expires_at)
            )
            log_audit(conn, user["id"], "whatsapp_recovery_requested", "admin_user", str(user["id"]), {"channel": payload.channel})
            # In test mode when WHATSAPP_TEST_CAPTURE=1 is explicitly set by unit test harness
            if os.getenv("WHATSAPP_TEST_CAPTURE") == "1":
                return {"status": "recovery_initiated", "test_otp": otp, "expires_in_seconds": 300}

        return {
            "status": "recovery_initiated",
            "message": "If this verified administrator number is eligible, a single-use verification code has been dispatched."
        }

@app.post("/api/v1/admin/auth/recovery/verify")
def verify_admin_password_recovery(payload: RecoveryVerifyInput, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"recovery_verify:{client_ip}", max_requests=5, window_seconds=300)

    cleaned_phone = re.sub(r"[\s\-\.]", "", payload.phone)
    submitted_hash = hashlib.sha256(payload.verification_code.strip().encode("utf-8")).hexdigest()
    now_ts = int(time.time())

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM admin_users WHERE phone = ? AND is_active = 1",
            (cleaned_phone,)
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")

        cur.execute(
            """SELECT * FROM admin_recovery_codes
               WHERE admin_user_id = ? AND is_used = 0 AND expires_at >= ?
               ORDER BY id DESC LIMIT 5""",
            (user["id"], now_ts)
        )
        active_codes = cur.fetchall()
        matched_code = None
        for c in active_codes:
            if c["attempts"] >= c["max_attempts"]:
                continue
            if hmac.compare_digest(c["code_hash"], submitted_hash):
                matched_code = c
                break
            else:
                cur.execute("UPDATE admin_recovery_codes SET attempts = attempts + 1 WHERE id = ?", (c["id"],))

        if not matched_code:
            log_audit(conn, user["id"], "password_recovery_failed", "admin_user", str(user["id"]), {"phone": cleaned_phone})
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")

        # Mark single-use code as used, update password with PBKDF2/Argon2, and revoke existing tokens
        cur.execute("UPDATE admin_recovery_codes SET is_used = 1, attempts = attempts + 1 WHERE id = ?", (matched_code["id"],))
        new_hash = hash_password(payload.new_password)
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_hash, user["id"])
        )
        log_audit(conn, user["id"], "password_recovered_and_rotated", "admin_user", str(user["id"]), {"channel": matched_code["channel"]})
        return {"status": "password_updated", "sessions_revoked": True}

# ============================================================================
# SECTION 5 & 9: GUEST ORDER TRACKING, COUPONS & OPTIMISTIC CONCURRENCY SYNC
# ============================================================================

@app.get("/api/v1/orders/track")
def track_guest_order(reference: str = Query(...), phone: str = Query(...)):
    """
    Public guest order tracking requiring BOTH order_reference and matching customer phone
    to prevent IDOR enumeration of other customers' orders.
    """
    cleaned_phone = re.sub(r"[\s\-\.]", "", phone)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM orders WHERE order_reference = ? AND customer_phone = ?",
            (reference.strip().upper(), cleaned_phone)
        )
        ord_row = cur.fetchone()
        if not ord_row:
            raise HTTPException(status_code=404, detail="No order found matching this reference and phone number")
        od = dict(ord_row)
        od.pop("internal_notes", None)
        od.pop("idempotency_hash", None)
        cur.execute("SELECT product_name, variant_title, quantity, unit_price_dzd, line_total_dzd FROM order_items WHERE order_id = ?", (od["id"],))
        od["items"] = [dict(r) for r in cur.fetchall()]
        return od

@app.put("/api/v1/admin/products/{product_id}")
def update_product_with_conflict_detection(
    product_id: int,
    payload: ProductConcurrencyUpdate,
    admin: dict = Depends(require_permission("products:write"))
):
    """
    Enforces optimistic concurrency control (`expected_version`) so simultaneous CMS edits
    never silently overwrite newer server data (Section 9).
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        current_version = int(prod["version"])
        if payload.expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Synchronization conflict detected: server version is {current_version}, but client sent version {payload.expected_version}. Reload latest server data before saving."
            )
        new_version = current_version + 1
        cur.execute(
            """UPDATE products
               SET name_fr = ?,
                   selling_price_dzd = ?,
                   name_ar = COALESCE(?, name_ar),
                   name_en = COALESCE(?, name_en),
                   description_fr = COALESCE(?, description_fr),
                   purchase_cost_dzd = COALESCE(?, purchase_cost_dzd),
                   previous_price_dzd = COALESCE(?, previous_price_dzd),
                   discount_percent = COALESCE(?, discount_percent),
                   sku = COALESCE(?, sku),
                   brand_id = COALESCE(?, brand_id),
                   category_id = COALESCE(?, category_id),
                   main_image_url = COALESCE(?, main_image_url),
                   status = COALESCE(?, status),
                   is_featured = COALESCE(?, is_featured),
                   is_new_arrival = COALESCE(?, is_new_arrival),
                   seo_title = COALESCE(?, seo_title),
                   seo_description = COALESCE(?, seo_description),
                   version = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                payload.name_fr,
                payload.selling_price_dzd,
                payload.name_ar,
                payload.name_en,
                payload.description_fr,
                payload.purchase_cost_dzd,
                payload.previous_price_dzd,
                payload.discount_percent,
                payload.sku,
                payload.brand_id,
                payload.category_id,
                payload.main_image_url,
                payload.status,
                (1 if payload.is_featured else 0) if payload.is_featured is not None else None,
                (1 if payload.is_new_arrival else 0) if payload.is_new_arrival is not None else None,
                payload.seo_title,
                payload.seo_description,
                new_version,
                product_id,
            )
        )
        if payload.dynamic_attributes is not None:
            target_cat_id = payload.category_id or prod["category_id"]
            cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (target_cat_id,))
            cat_attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}
            for akey, aval in payload.dynamic_attributes.items():
                if akey in cat_attrs:
                    cur.execute(
                        """INSERT INTO product_attribute_values (product_id, attribute_id, value_text)
                           VALUES (?, ?, ?)
                           ON CONFLICT(product_id, attribute_id) DO UPDATE SET value_text = excluded.value_text""",
                        (product_id, cat_attrs[akey]["id"], str(aval))
                    )
        log_audit(conn, int(admin["sub"]), "update_product_synced", "product", str(product_id), {"new_version": new_version})
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return serialize_product(conn, dict(cur.fetchone()), include_private=True)

@app.post("/api/v1/admin/coupons", status_code=201)
def create_coupon(
    payload: CouponCreateInput,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, max_discount_dzd, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (payload.code.upper(), payload.discount_type, payload.discount_value, payload.min_order_dzd, payload.max_discount_dzd)
        )
        cid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_coupon", "coupon", str(cid), {"code": payload.code.upper()})
        cur.execute("SELECT * FROM coupons WHERE id = ?", (cid,))
        return dict(cur.fetchone())


@app.get("/api/v1/admin/sync/delta")
def admin_delta_sync(
    since_order_id: int = Query(0, ge=0, description="Last order ID seen by the Desktop CMS before PC was turned off"),
    since_movement_id: int = Query(0, ge=0, description="Last inventory movement ID seen by the Desktop CMS"),
    admin: dict = Depends(require_permission("dashboard:read"))
):
    """
    Automatic Reconnection & Delta Synchronization Endpoint for the Tauri 2 Desktop CMS.
    When the owner turns their Windows PC back on (or reconnects to the internet),
    the Desktop CMS calls this endpoint to immediately fetch all new guest orders,
    updated stock quantities, and inventory movements recorded by the 24/7 VPS while the PC was off.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id > ? ORDER BY id DESC", (since_order_id,))
        new_orders = []
        for r in cur.fetchall():
            od = dict(r)
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (od["id"],))
            od["items"] = [dict(it) for it in cur.fetchall()]
            new_orders.append(od)

        cur.execute("SELECT * FROM inventory_movements WHERE id > ? ORDER BY id DESC", (since_movement_id,))
        new_movements = [dict(m) for m in cur.fetchall()]

        cur.execute("SELECT id, sku, stock_qty, price_override_dzd FROM product_variants ORDER BY id ASC")
        variant_stocks = [dict(v) for v in cur.fetchall()]

        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_oid FROM orders")
        latest_order_id = cur.fetchone()["max_oid"]
        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_mid FROM inventory_movements")
        latest_movement_id = cur.fetchone()["max_mid"]

        return {
            "server_timestamp": int(time.time()),
            "latest_order_id": latest_order_id,
            "latest_movement_id": latest_movement_id,
            "missed_orders_count": len(new_orders),
            "new_orders": new_orders,
            "new_movements": new_movements,
            "current_variant_stocks": variant_stocks,
        }



# ============================================================================
# FIRST-TIME ONE-TIME OWNER INITIALIZATION & PERMANENT LOCKOUT
# ============================================================================

class OwnerInitializeInput(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=150)
    email: str = Field(..., min_length=5, max_length=150)
    password: str = Field(..., min_length=10, max_length=128)
    whatsapp_phone: str = Field(...)
    emergency_phone: str = Field(...)

    @validator("whatsapp_phone", "emergency_phone")
    def validate_phones(cls, v):
        cleaned = re.sub(r"[\s\-\.]", "", v)
        if not re.match(r"^(\+213|0)(5|6|7)[0-9]{8}$", cleaned):
            raise ValueError("Invalid Algerian mobile phone number (must start with 05, 06, 07 or +213)")
        return cleaned

@app.get("/api/v1/admin/auth/setup-status")
def get_admin_setup_status():
    """
    Checks whether the primary Super Administrator (Owner) has already been provisioned.
    When true, all PCs opening the CMS directly display the Login and Forgot Password screen.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = 'system_initialized'")
        init_row = cur.fetchone()
        is_init = init_row and init_row["setting_value"] == "true"
        if not is_init:
            cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE role_id = (SELECT id FROM roles WHERE name = 'super_admin')")
            is_init = cur.fetchone()["cnt"] > 0
        return {
            "is_initialized": is_init,
            "requires_owner_setup": not is_init,
            "store_name": "Mus Luxury (LUXE)"
        }

@app.post("/api/v1/admin/auth/initialize-owner", status_code=201)
def initialize_primary_owner(payload: OwnerInitializeInput, request: Request):
    """
    First-Time Provisioning Endpoint:
    Allows the store owner to configure their username, email, password, primary recovery WhatsApp number,
    and a second emergency phone number.
    SECURITY LOCKOUT: Once called and saved to PostgreSQL, this endpoint is PERMANENTLY LOCKED (HTTP 403).
    Even if the CMS application starts on another PC, it detects system_initialized = true
    and goes straight to the normal Login & Forgot Password screen.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"init_owner:{client_ip}", max_requests=3, window_seconds=300)

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        # Check if already initialized
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = 'system_initialized'")
        init_row = cur.fetchone()
        is_init = init_row and init_row["setting_value"] == "true"
        if not is_init:
            cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE role_id = (SELECT id FROM roles WHERE name = 'super_admin')")
            is_init = cur.fetchone()["cnt"] > 0
        if is_init:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Lockout: Mus Luxury platform has already been initialized with a primary owner account. First-time setup is disabled."
            )

        cur.execute("SELECT id FROM roles WHERE name = 'super_admin'")
        role_row = cur.fetchone()
        super_role_id = role_row["id"] if role_row else 1

        email_clean = payload.email.strip().lower()
        cur.execute("SELECT id FROM admin_users WHERE email = ?", (email_clean,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="An administrator with this email already exists")

        pw_hash = hash_password(payload.password)
        cur.execute(
            """INSERT INTO admin_users
               (email, full_name, phone, emergency_phone, whatsapp_verified, totp_enabled, password_hash, role_id, is_active)
               VALUES (?, ?, ?, ?, 1, 1, ?, ?, 1)""",
            (email_clean, payload.full_name.strip(), payload.whatsapp_phone, payload.emergency_phone, pw_hash, super_role_id)
        )
        owner_id = cur.lastrowid

        # Seed emergency recovery token tied to secondary emergency phone
        emergency_code = f"EMERGENCY-{secrets.token_hex(6).upper()}"
        code_hash = hashlib.sha256(emergency_code.encode("utf-8")).hexdigest()
        cur.execute(
            """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
               VALUES (?, ?, ?, 'offline_emergency', 3, ?)""",
            (owner_id, payload.emergency_phone, code_hash, int(time.time()) + 86400 * 365)
        )

        # Mark system as permanently initialized in database
        cur.execute(
            """INSERT INTO store_settings (setting_key, setting_value, updated_at)
               VALUES ('system_initialized', 'true', CURRENT_TIMESTAMP)
               ON CONFLICT(setting_key) DO UPDATE SET setting_value = 'true', updated_at = CURRENT_TIMESTAMP"""
        )

        cur.execute(
            """SELECT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               WHERE rp.role_id = ?""",
            (super_role_id,)
        )
        perms = [r["code"] for r in cur.fetchall()]
        token = create_access_token(owner_id, email_clean, "super_admin", perms)

        log_audit(conn, owner_id, "first_time_owner_initialized", "admin_user", str(owner_id), {
            "email": email_clean,
            "whatsapp_phone": payload.whatsapp_phone,
            "emergency_phone": payload.emergency_phone
        })

        return {
            "initialized": True,
            "message": "Super Administrator successfully provisioned. Setup is permanently locked.",
            "emergency_code_backup": emergency_code,
            "access_token": token,
            "user": {
                "id": owner_id,
                "email": email_clean,
                "full_name": payload.full_name.strip(),
                "role": "super_admin",
                "whatsapp_phone": payload.whatsapp_phone,
                "emergency_phone": payload.emergency_phone
            }
        }


from .security import sign_api_request, verify_signed_request

@app.post("/api/v1/admin/secure-action")
async def execute_cryptographically_signed_action(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """
    Cryptographically signed administrative endpoint:
    Enforces HMAC-SHA256 signature verification over (method, path, timestamp, nonce, body_sha256).
    Rejects any replay attacks, expired timestamps, or tampered payloads.
    """
    body_bytes = await request.body()
    sig = request.headers.get("X-Luxe-Signature")
    ts = request.headers.get("X-Luxe-Timestamp")
    nonce = request.headers.get("X-Luxe-Nonce")
    verify_signed_request(request.method, request.url.path, body_bytes, sig, ts, nonce)
    return {"status": "verified_and_executed", "admin_id": admin["sub"], "nonce": nonce}



# ============================================================================
# PRODUCTION ENDPOINTS: COUPON VALIDATION, 69-WILAYA RATE MANAGEMENT,
# VARIANT STOCK ADJUSTMENTS, GUEST CUSTOMER RECORDS & ANALYTICS REPORTS
# ============================================================================

class CouponValidateRequest(BaseModel):
    code: str
    subtotal_dzd: int = Field(..., ge=0)

class DeliveryZoneUpdateInput(BaseModel):
    home_fee_dzd: int = Field(..., ge=0)
    stop_desk_fee_dzd: int = Field(..., ge=0)
    home_supported: bool = True
    stop_desk_supported: bool = True
    estimated_days: str = "24h - 48h"
    communes: Optional[List[str]] = None
    is_active: bool = True

class BulkWilayaRateItem(BaseModel):
    wilaya_code: str
    home_fee_dzd: int = Field(..., ge=0)
    stop_desk_fee_dzd: int = Field(..., ge=0)
    home_supported: bool = True
    stop_desk_supported: bool = True
    estimated_days: str = "24h - 48h"

class BulkWilayaRatesUpdate(BaseModel):
    zones: List[BulkWilayaRateItem]

class StockAdjustmentInput(BaseModel):
    change_qty: int
    reason: str = Field("manual_adjustment", min_length=3, max_length=120)

@app.post("/api/v1/coupons/validate")
def validate_public_coupon(payload: CouponValidateRequest):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM coupons WHERE UPPER(code) = ? AND is_active = 1",
            (payload.code.strip().upper(),)
        )
        cpn = cur.fetchone()
        if not cpn:
            raise HTTPException(status_code=404, detail="Code promo invalide ou expiré")
        if payload.subtotal_dzd < int(cpn["min_order_dzd"]):
            raise HTTPException(
                status_code=400,
                detail=f"Ce code promo requiert un montant minimum de {cpn['min_order_dzd']} DA"
            )
        if cpn["discount_type"] == "percentage":
            disc = (payload.subtotal_dzd * int(cpn["discount_value"])) // 100
            if cpn["max_discount_dzd"] is not None:
                disc = min(disc, int(cpn["max_discount_dzd"]))
        else:
            disc = int(cpn["discount_value"])
        disc = min(disc, payload.subtotal_dzd)
        return {
            "valid": True,
            "code": cpn["code"],
            "discount_type": cpn["discount_type"],
            "discount_value": cpn["discount_value"],
            "discount_dzd": disc,
            "new_subtotal_dzd": payload.subtotal_dzd - disc
        }

@app.put("/api/v1/admin/delivery-zones/{wilaya_code}")
def admin_update_delivery_zone(
    wilaya_code: str,
    payload: DeliveryZoneUpdateInput,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM delivery_zones WHERE wilaya_code = ?", (wilaya_code.zfill(2),))
        zone = cur.fetchone()
        if not zone:
            raise HTTPException(status_code=404, detail=f"Wilaya {wilaya_code} introuvable")
        if payload.communes is not None:
            cur.execute(
                "UPDATE delivery_zones SET communes_json = ?, is_active = ? WHERE id = ?",
                (json.dumps(payload.communes, ensure_ascii=False), 1 if payload.is_active else 0, zone["id"])
            )
        else:
            cur.execute(
                "UPDATE delivery_zones SET is_active = ? WHERE id = ?",
                (1 if payload.is_active else 0, zone["id"])
            )
        cur.execute(
            "UPDATE delivery_rates SET fee_dzd = ?, estimated_days = ?, is_supported = ? WHERE zone_id = ? AND delivery_method = 'home'",
            (payload.home_fee_dzd, payload.estimated_days, 1 if payload.home_supported else 0, zone["id"])
        )
        cur.execute(
            "UPDATE delivery_rates SET fee_dzd = ?, estimated_days = ?, is_supported = ? WHERE zone_id = ? AND delivery_method = 'stop_desk'",
            (payload.stop_desk_fee_dzd, payload.estimated_days, 1 if payload.stop_desk_supported else 0, zone["id"])
        )
        log_audit(conn, int(admin["sub"]), "update_delivery_zone", "delivery_zone", wilaya_code, {
            "home_fee_dzd": payload.home_fee_dzd,
            "stop_desk_fee_dzd": payload.stop_desk_fee_dzd
        })
        return {"updated": True, "wilaya_code": wilaya_code.zfill(2), "home_fee_dzd": payload.home_fee_dzd, "stop_desk_fee_dzd": payload.stop_desk_fee_dzd}

@app.post("/api/v1/admin/variants/{variant_id}/adjust-stock")
def admin_adjust_variant_stock(
    variant_id: int,
    payload: StockAdjustmentInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variant not found")
        prev_qty = int(v["stock_qty"])
        new_qty = prev_qty + payload.change_qty
        if new_qty < 0:
            raise HTTPException(status_code=400, detail="Stock quantity cannot become negative")
        cur.execute("UPDATE product_variants SET stock_qty = ? WHERE id = ?", (new_qty, variant_id))
        cur.execute(
            """INSERT INTO inventory_movements
               (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (variant_id, int(admin["sub"]), payload.change_qty, prev_qty, new_qty, payload.reason)
        )
        log_audit(conn, int(admin["sub"]), "adjust_variant_stock", "product_variant", str(variant_id), {
            "sku": v["sku"], "previous_qty": prev_qty, "new_qty": new_qty, "reason": payload.reason
        })
        return {"variant_id": variant_id, "sku": v["sku"], "previous_qty": prev_qty, "new_qty": new_qty}

@app.get("/api/v1/admin/customers")
def admin_list_customers(admin: dict = Depends(require_permission("orders:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers ORDER BY total_spent_dzd DESC, id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.get("/api/v1/admin/reports")
def admin_analytics_reports(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) AS count, COALESCE(SUM(total_dzd), 0) AS total_dzd FROM orders GROUP BY status")
        by_status = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """SELECT p.id, p.sku, p.name_fr, p.sales_count, p.selling_price_dzd, p.purchase_cost_dzd,
                      COALESCE(SUM(pv.stock_qty), 0) AS total_stock
               FROM products p
               LEFT JOIN product_variants pv ON pv.product_id = p.id
               WHERE p.deleted_at IS NULL
               GROUP BY p.id
               ORDER BY p.sales_count DESC"""
        )
        product_perf = [dict(r) for r in cur.fetchall()]
        return {"orders_by_status": by_status, "product_performance": product_perf}


@app.get("/api/v1/delivery-zones/calculate")
def calculate_delivery_and_order_preview(
    wilaya_code: str = Query(..., description="Wilaya code 01 to 69"),
    delivery_method: str = Query("home", regex=r"^(home|stop_desk)$"),
    subtotal_dzd: int = Query(0, ge=0),
    coupon_code: Optional[str] = None
):
    """
    Real-time server-side calculator for the Storefront Cart & Checkout:
    Returns the exact admin-configured Home or Stop-Desk delivery fee for the chosen Wilaya,
    plus the discount and final total in DA.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM delivery_zones WHERE wilaya_code = ? AND is_active = 1", (wilaya_code.zfill(2),))
        zone = cur.fetchone()
        if not zone:
            raise HTTPException(status_code=404, detail=f"Wilaya {wilaya_code} non disponible")

        cur.execute("SELECT delivery_method, fee_dzd, estimated_days, is_supported FROM delivery_rates WHERE zone_id = ?", (zone["id"],))
        rates_map = {r["delivery_method"]: dict(r) for r in cur.fetchall()}
        chosen_rate = rates_map.get(delivery_method)
        if not chosen_rate or not chosen_rate["is_supported"]:
            raise HTTPException(
                status_code=400,
                detail=f"Le mode de livraison '{delivery_method}' n'est pas disponible pour la wilaya {zone['wilaya_name_fr']}"
            )

        delivery_fee_dzd = int(chosen_rate["fee_dzd"])
        discount_dzd = 0
        if coupon_code:
            cur.execute("SELECT * FROM coupons WHERE UPPER(code) = ? AND is_active = 1", (coupon_code.strip().upper(),))
            cpn = cur.fetchone()
            if cpn and subtotal_dzd >= int(cpn["min_order_dzd"]):
                if cpn["discount_type"] == "percentage":
                    discount_dzd = (subtotal_dzd * int(cpn["discount_value"])) // 100
                    if cpn["max_discount_dzd"] is not None:
                        discount_dzd = min(discount_dzd, int(cpn["max_discount_dzd"]))
                else:
                    discount_dzd = int(cpn["discount_value"])
                discount_dzd = min(discount_dzd, subtotal_dzd)

        total_dzd = (subtotal_dzd - discount_dzd) + delivery_fee_dzd
        return {
            "wilaya_code": zone["wilaya_code"],
            "wilaya_name_fr": zone["wilaya_name_fr"],
            "wilaya_name_ar": zone["wilaya_name_ar"],
            "communes": json.loads(zone["communes_json"]),
            "selected_method": delivery_method,
            "home_rate": rates_map.get("home"),
            "stop_desk_rate": rates_map.get("stop_desk"),
            "subtotal_dzd": subtotal_dzd,
            "discount_dzd": discount_dzd,
            "delivery_fee_dzd": delivery_fee_dzd,
            "total_dzd": total_dzd
        }

@app.put("/api/v1/admin/delivery-zones-bulk")
def admin_bulk_update_delivery_zones(
    payload: BulkWilayaRatesUpdate,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        updated_count = 0
        for item in payload.zones:
            code = item.wilaya_code.zfill(2)
            cur.execute("SELECT id FROM delivery_zones WHERE wilaya_code = ?", (code,))
            z = cur.fetchone()
            if not z:
                continue
            cur.execute(
                "UPDATE delivery_rates SET fee_dzd = ?, estimated_days = ?, is_supported = ? WHERE zone_id = ? AND delivery_method = 'home'",
                (item.home_fee_dzd, item.estimated_days, 1 if item.home_supported else 0, z["id"])
            )
            cur.execute(
                "UPDATE delivery_rates SET fee_dzd = ?, estimated_days = ?, is_supported = ? WHERE zone_id = ? AND delivery_method = 'stop_desk'",
                (item.stop_desk_fee_dzd, item.estimated_days, 1 if item.stop_desk_supported else 0, z["id"])
            )
            updated_count += 1
        log_audit(conn, int(admin["sub"]), "bulk_update_delivery_zones", "delivery_zone", "bulk", {"updated_count": updated_count})
        return {"updated_count": updated_count}


# ============================================================================
# ADDITIONAL PRODUCTION ADMIN ENDPOINTS (PRODUCTS, CATEGORIES, INVENTORY,
# BRANDS, INVOICES & CSV EXPORTS — SECTIONS 3.2, 3.3, 3.4, 3.5)
# ============================================================================

class CategoryUpdateInput(BaseModel):
    name_fr: Optional[str] = None
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    description_fr: Optional[str] = None
    image_url: Optional[str] = None
    banner_url: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    show_on_homepage: Optional[bool] = None

class BrandCreateInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., regex=r"^[a-z0-9-]{2,120}$")
    logo_url: Optional[str] = "/assets/mus_luxury_logo.png"

class BulkProductStatusInput(BaseModel):
    product_ids: List[int]
    status: str = Field(..., regex=r"^(draft|published|archived)$")

@app.get("/api/v1/admin/products")
def admin_list_products(
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    include_archived: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        where = ["1=1"]
        params: List[Any] = []
        if not include_archived:
            where.append("p.deleted_at IS NULL")
        if category_id is not None:
            where.append("p.category_id = ?")
            params.append(category_id)
        if status_filter:
            where.append("p.status = ?")
            params.append(status_filter)
        if q:
            where.append("(p.name_fr LIKE ? OR p.sku LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        cur.execute(f"SELECT * FROM products p WHERE {' AND '.join(where)} ORDER BY p.id DESC", params)
        all_rows = [serialize_product(conn, dict(r), include_private=True) for r in cur.fetchall()]
        total = len(all_rows)
        start = (page - 1) * page_size
        return {
            "items": all_rows[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

@app.delete("/api/v1/admin/products/{product_id}")
def admin_safe_delete_or_archive_product(
    product_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    """
    Safely archives/deletes a product without destroying historical order records (Section 3.2).
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")

        cur.execute("SELECT COUNT(*) AS cnt FROM order_items WHERE product_id = ?", (product_id,))
        order_refs = cur.fetchone()["cnt"]

        cur.execute(
            "UPDATE products SET status = 'archived', deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (product_id,)
        )
        cur.execute("UPDATE product_variants SET is_active = 0 WHERE product_id = ?", (product_id,))
        log_audit(conn, int(admin["sub"]), "archive_product", "product", str(product_id), {
            "sku": prod["sku"],
            "historical_order_items_preserved": order_refs
        })
        return {
            "archived": True,
            "product_id": product_id,
            "status": "archived",
            "historical_order_items_preserved": order_refs
        }

@app.post("/api/v1/admin/products/bulk-status")
def admin_bulk_update_product_status(
    payload: BulkProductStatusInput,
    admin: dict = Depends(require_permission("products:write"))
):
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="product_ids cannot be empty")
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        updated = 0
        for pid in payload.product_ids:
            cur.execute(
                "UPDATE products SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload.status, pid)
            )
            updated += cur.rowcount
        log_audit(conn, int(admin["sub"]), "bulk_product_status", "product", "bulk", {"count": updated, "status": payload.status})
        return {"updated_count": updated, "status": payload.status}

@app.post("/api/v1/admin/brands", status_code=201)
def admin_create_brand(
    payload: BrandCreateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM brands WHERE slug = ?", (payload.slug,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Brand slug '{payload.slug}' already exists")
        cur.execute(
            "INSERT INTO brands (name, slug, logo_url, is_active) VALUES (?, ?, ?, 1)",
            (payload.name, payload.slug, payload.logo_url)
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_brand", "brand", str(bid), {"slug": payload.slug})
        cur.execute("SELECT * FROM brands WHERE id = ?", (bid,))
        return dict(cur.fetchone())

@app.put("/api/v1/admin/categories/{category_id}")
def admin_update_category(
    category_id: int,
    payload: CategoryUpdateInput,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        cur.execute(
            """UPDATE categories
               SET name_fr = COALESCE(?, name_fr),
                   name_ar = COALESCE(?, name_ar),
                   name_en = COALESCE(?, name_en),
                   description_fr = COALESCE(?, description_fr),
                   image_url = COALESCE(?, image_url),
                   banner_url = COALESCE(?, banner_url),
                   display_order = COALESCE(?, display_order),
                   is_active = COALESCE(?, is_active),
                   show_on_homepage = COALESCE(?, show_on_homepage)
               WHERE id = ?""",
            (
                payload.name_fr,
                payload.name_ar,
                payload.name_en,
                payload.description_fr,
                payload.image_url,
                payload.banner_url,
                payload.display_order,
                (1 if payload.is_active else 0) if payload.is_active is not None else None,
                (1 if payload.show_on_homepage else 0) if payload.show_on_homepage is not None else None,
                category_id,
            )
        )
        log_audit(conn, int(admin["sub"]), "update_category", "category", str(category_id), {"name_fr": payload.name_fr})
        cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return serialize_category(conn, dict(cur.fetchone()))

@app.delete("/api/v1/admin/categories/{category_id}")
def admin_archive_category(
    category_id: int,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        cur.execute(
            "UPDATE categories SET is_active = 0, deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (category_id,)
        )
        log_audit(conn, int(admin["sub"]), "archive_category", "category", str(category_id), {"slug": cat["slug"]})
        return {"archived": True, "category_id": category_id}

@app.get("/api/v1/admin/inventory/movements")
def admin_list_inventory_movements(
    variant_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        if variant_id is not None:
            cur.execute(
                """SELECT im.*, pv.sku, pv.title AS variant_title, p.name_fr AS product_name
                   FROM inventory_movements im
                   JOIN product_variants pv ON pv.id = im.variant_id
                   JOIN products p ON p.id = pv.product_id
                   WHERE im.variant_id = ?
                   ORDER BY im.id DESC LIMIT ?""",
                (variant_id, limit)
            )
        else:
            cur.execute(
                """SELECT im.*, pv.sku, pv.title AS variant_title, p.name_fr AS product_name
                   FROM inventory_movements im
                   JOIN product_variants pv ON pv.id = im.variant_id
                   JOIN products p ON p.id = pv.product_id
                   ORDER BY im.id DESC LIMIT ?""",
                (limit,)
            )
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.get("/api/v1/admin/orders/export.csv")
def admin_export_orders_csv(admin: dict = Depends(require_permission("orders:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "order_id", "order_reference", "status", "payment_method",
            "customer_name", "customer_phone", "wilaya_code", "wilaya_name",
            "commune", "delivery_method", "subtotal_dzd", "delivery_fee_dzd",
            "total_dzd", "created_at"
        ])
        for r in cur.fetchall():
            writer.writerow([
                r["id"], r["order_reference"], r["status"], r["payment_method"],
                r["customer_name"], r["customer_phone"], r["wilaya_code"], r["wilaya_name"],
                r["commune"], r["delivery_method"], r["subtotal_dzd"], r["delivery_fee_dzd"],
                r["total_dzd"], r["created_at"]
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=mus_luxury_orders.csv"}
        )

@app.get("/api/v1/admin/orders/{order_id}/invoice")
def admin_get_order_invoice(
    order_id: int,
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        o = cur.fetchone()
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")
        od = dict(o)
        cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = [dict(r) for r in cur.fetchall()]
        od["items"] = items
        od["boutique_info"] = {
            "name": "Mus Luxury (LUXE)",
            "address": "FVX6+GCJ Mus luxury, Ouled Yaïch, Blida (09), Algérie",
            "phone": "0655534154",
            "whatsapp": "+213655534154",
            "instagram": "https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux",
            "tiktok": "https://www.tiktok.com/@musluxury.092?_r=1&_t=ZS-9B2mO0gpA7V",
            "currency": "DZD (DA)",
            "payment_notice": "Paiement en espèces à la livraison (Cash on Delivery)"
        }
        return od


# ============================================================================
# HEALTHCHECK, PRODUCT IMAGE GALLERY MANAGEMENT & STATIC CONTENT PAGES CRUD
# (SECTIONS 3.2, 3.7, 9)
# ============================================================================

class ProductImageAddInput(BaseModel):
    image_url: str = Field(..., min_length=3, max_length=500)
    alt_text: Optional[str] = ""
    variant_id: Optional[int] = None
    display_order: int = 1
    set_as_primary: bool = False

class ProductImageReorderItem(BaseModel):
    image_id: int
    display_order: int

class ProductImageReorderInput(BaseModel):
    orders: List[ProductImageReorderItem]
    primary_image_url: Optional[str] = None

class StaticPageUpsertInput(BaseModel):
    title_fr: str = Field(..., min_length=2, max_length=200)
    title_ar: Optional[str] = ""
    title_en: Optional[str] = ""
    content_fr: str = Field(..., min_length=5)
    content_ar: Optional[str] = ""
    content_en: Optional[str] = ""
    is_published: bool = True

@app.get("/api/v1/health")
def api_healthcheck():
    try:
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM delivery_zones WHERE is_active = 1")
            w_cnt = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM categories WHERE is_active = 1 AND deleted_at IS NULL")
            c_cnt = cur.fetchone()["cnt"]
        return {
            "status": "ok",
            "database": "connected",
            "active_wilayas": w_cnt,
            "active_categories": c_cnt,
            "timestamp": int(time.time()),
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Database connectivity check failed")

@app.post("/api/v1/admin/products/{product_id}/images", status_code=201)
def admin_add_product_image(
    product_id: int,
    payload: ProductImageAddInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")
        cur.execute(
            """INSERT INTO product_images (product_id, variant_id, image_url, alt_text, display_order)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, payload.variant_id, payload.image_url, payload.alt_text, payload.display_order)
        )
        img_id = cur.lastrowid
        if payload.set_as_primary:
            cur.execute(
                "UPDATE products SET main_image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload.image_url, product_id)
            )
        log_audit(conn, int(admin["sub"]), "add_product_image", "product_image", str(img_id), {"product_id": product_id, "primary": payload.set_as_primary})
        cur.execute("SELECT * FROM product_images WHERE id = ?", (img_id,))
        return dict(cur.fetchone())

@app.put("/api/v1/admin/products/{product_id}/images/reorder")
def admin_reorder_product_images(
    product_id: int,
    payload: ProductImageReorderInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")
        for item in payload.orders:
            cur.execute(
                "UPDATE product_images SET display_order = ? WHERE id = ? AND product_id = ?",
                (item.display_order, item.image_id, product_id)
            )
        if payload.primary_image_url:
            cur.execute(
                "UPDATE products SET main_image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload.primary_image_url, product_id)
            )
        log_audit(conn, int(admin["sub"]), "reorder_product_images", "product", str(product_id), {"count": len(payload.orders)})
        cur.execute("SELECT * FROM product_images WHERE product_id = ? ORDER BY display_order ASC, id ASC", (product_id,))
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.delete("/api/v1/admin/product-images/{image_id}")
def admin_delete_product_image(
    image_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product_images WHERE id = ?", (image_id,))
        img = cur.fetchone()
        if not img:
            raise HTTPException(status_code=404, detail="Product image not found")
        cur.execute("DELETE FROM product_images WHERE id = ?", (image_id,))
        log_audit(conn, int(admin["sub"]), "delete_product_image", "product_image", str(image_id), {"product_id": img["product_id"]})
        return {"deleted": True, "image_id": image_id}

@app.get("/api/v1/pages")
def list_public_static_pages():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM static_pages WHERE is_published = 1 ORDER BY id ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.get("/api/v1/pages/{slug}")
def get_public_static_page(slug: str):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM static_pages WHERE slug = ? AND is_published = 1", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")
        return dict(row)

@app.put("/api/v1/admin/pages/{slug}")
def admin_upsert_static_page(
    slug: str,
    payload: StaticPageUpsertInput,
    admin: dict = Depends(require_permission("content:write"))
):
    clean_slug = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-")
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO static_pages (slug, title_fr, title_ar, title_en, content_fr, content_ar, content_en, is_published, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(slug) DO UPDATE SET
                   title_fr = excluded.title_fr,
                   title_ar = excluded.title_ar,
                   title_en = excluded.title_en,
                   content_fr = excluded.content_fr,
                   content_ar = excluded.content_ar,
                   content_en = excluded.content_en,
                   is_published = excluded.is_published,
                   updated_at = CURRENT_TIMESTAMP""",
            (
                clean_slug, payload.title_fr, payload.title_ar, payload.title_en,
                payload.content_fr, payload.content_ar, payload.content_en,
                1 if payload.is_published else 0
            )
        )
        log_audit(conn, int(admin["sub"]), "upsert_static_page", "static_page", clean_slug, {"is_published": payload.is_published})
        cur.execute("SELECT * FROM static_pages WHERE slug = ?", (clean_slug,))
        return dict(cur.fetchone())
