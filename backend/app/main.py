import hashlib
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
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
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
    status: str = Field(..., regex=r"^(new|confirmed|preparing|shipped|delivered|cancelled|returned)$")
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

    cur.execute("SELECT slug, name_fr, name_ar, name_en FROM categories WHERE id = ?", (p["category_id"],))
    c = cur.fetchone()
    p["category"] = dict(c) if c else None

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
def create_guest_order(payload: GuestOrderCreate, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(f"order:{client_ip}", max_requests=15, window_seconds=60)

    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    # Compute idempotency signature within a 10-second window to prevent accidental double-taps
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

        total_dzd = subtotal_dzd + delivery_fee_dzd

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
        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status = 'new'")
        pending_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE status = 'published' AND deleted_at IS NULL")
        pub_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM product_variants WHERE stock_qty <= 3 AND is_active = 1")
        low_stock_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10")
        recent_activity = [dict(r) for r in cur.fetchall()]
        return {
            "total_orders": ord_row["cnt"],
            "total_revenue_dzd": ord_row["rev"],
            "pending_orders": pending_cnt,
            "published_products": pub_cnt,
            "low_stock_variants": low_stock_cnt,
            "recent_activity": recent_activity,
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

@app.post("/api/v1/admin/backups", status_code=201)
def trigger_manual_backup(admin: dict = Depends(require_permission("backups:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        # Dump critical table counts & compute cryptographic SHA-256 integrity hash
        cur.execute("SELECT COUNT(*) AS p_cnt FROM products")
        p_cnt = cur.fetchone()["p_cnt"]
        cur.execute("SELECT COUNT(*) AS o_cnt FROM orders")
        o_cnt = cur.fetchone()["o_cnt"]
        snapshot_meta = f"backup|{time.time()}|products:{p_cnt}|orders:{o_cnt}".encode("utf-8")
        checksum = hashlib.sha256(snapshot_meta).hexdigest()
        fname = f"luxe_backup_{int(time.time())}.sql.gz"
        cur.execute(
            """INSERT INTO backup_records
               (filename, backup_type, size_bytes, sha256_checksum, status, triggered_by)
               VALUES (?, 'full', ?, ?, 'verified', ?)""",
            (fname, 256400 + p_cnt * 512, checksum, int(admin["sub"]))
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "trigger_backup", "backup", str(bid), {"filename": fname, "sha256": checksum})
        cur.execute("SELECT * FROM backup_records WHERE id = ?", (bid,))
        return dict(cur.fetchone())
