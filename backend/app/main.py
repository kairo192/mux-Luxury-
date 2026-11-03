from . import config
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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from .database import db_session
from .seed import SUPPORTED_ATTRIBUTE_TYPES, seed_initial_data
from .security import (
    check_rate_limit,
    get_real_client_ip,
    create_access_token,
    decode_access_token,
    decrypt_backup_bytes,
    encrypt_backup_bytes,
    hash_password as _hash_pw_init,
    revoke_token,
    validate_uploaded_image,
    verify_password,
)

_DUMMY_PASSWORD_HASH = _hash_pw_init("luxe_constant_time_dummy_mitigation_2026!")
_ENABLE_PUBLIC_DOCS = (not config.is_production()) or (os.getenv("ENABLE_API_DOCS", "").strip() == "1") 

app = FastAPI(
    title="Mus Luxury (LUXE) E-Commerce API",
    version="1.0.0",
    description="Production REST API for LUXE Algerian E-Commerce Storefront & Tauri 2 Desktop CMS",
    docs_url="/api/v1/docs" if _ENABLE_PUBLIC_DOCS else None,
    openapi_url="/api/v1/openapi.json" if _ENABLE_PUBLIC_DOCS else None,
)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
    "https://musluxury.dz",
    "https://www.musluxury.dz",
]
_EXTRA_CORS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
ALLOWED_CORS_ORIGINS = list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + _EXTRA_CORS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_ns = time.perf_counter_ns()
    incoming_req_id = (request.headers.get("X-Request-ID") or "").strip()
    if incoming_req_id and re.match(r"^[a-zA-Z0-9_\-]{6,64}$", incoming_req_id):
        req_id = incoming_req_id
    else:
        req_id = f"req_{secrets.token_hex(6)}"

    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.url.path.startswith("/api/v1/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
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
    uid = int(payload.get("sub") or 0)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", (f"session_revoked_ns:{uid}",))
        rev_row = cur.fetchone()
        if rev_row and int(payload.get("iat_ns") or 0) < int(rev_row["setting_value"] or 0):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token")
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

    @validator("full_name", "commune", "delivery_address", "customer_notes", pre=True, always=True)
    def reject_xss_and_html_tags(cls, v):
        if v is None:
            return ""
        s = str(v).strip()
        if re.search(r"(<\s*/?\s*(script|iframe|svg|img|object|embed|link|style|meta)|javascript\s*:|on\w+\s*=)", s, re.IGNORECASE):
            raise ValueError("HTML or script injection characters are not permitted")
        if "<" in s or ">" in s:
            raise ValueError("Angle brackets (< >) are not permitted in order contact fields")
        return s

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
    p["images"] = p["gallery_images"]
    p["variants"] = variants
    p["total_stock"] = total_stock
    p["in_stock"] = total_stock > 0
    return p

# ============================================================================
# PUBLIC STOREFRONT ENDPOINTS (/api/v1/*)
# ============================================================================

_INTERNAL_SETTING_KEYS = {"system_initialized"}

def _is_protected_setting_key(key: str) -> bool:
    k = (key or "").strip().lower()
    return k in _INTERNAL_SETTING_KEYS or k.startswith("system_") or k.startswith("internal_") or k.startswith("session_revoked_ns:")

def _ensure_safe_url_or_text(val: str, field_name: str = "value") -> str:
    s = str(val or "").strip()
    if re.search(r"(<\s*/?\s*(script|iframe|svg|object|embed)|javascript\s*:|vbscript\s*:|data\s*:\s*text/html|on\w+\s*=)", s, re.IGNORECASE):
        raise HTTPException(status_code=422, detail=f"Dangerous script or URI scheme blocked in {field_name}")
    return s

@app.get("/api/v1/store/settings")
def get_store_settings():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM store_settings")
        out = {}
        for r in cur.fetchall():
            if _is_protected_setting_key(r["setting_key"]):
                continue
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
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    in_stock_only: bool = False,
    sort: str = Query("newest", regex=r"^(newest|price_asc|price_desc|popularity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    with db_session() as conn:
        cur = conn.cursor()
        where = ["p.status = 'published'", "p.deleted_at IS NULL", "c.is_active = 1", "c.deleted_at IS NULL"]
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
        reserved_params = {"category", "brand", "q", "min_price", "max_price", "in_stock_only", "sort", "page", "page_size"}
        dynamic_attr_filters = {
            (k[5:] if k.startswith("attr_") else k): v
            for k, v in request.query_params.items()
            if k not in reserved_params and v
        }
        start = (page - 1) * page_size
        if not in_stock_only and not dynamic_attr_filters:
            count_sql = f"""
                SELECT COUNT(*) AS cnt FROM products p
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN brands b ON b.id = p.brand_id
                WHERE {' AND '.join(where)}
            """
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
        items = [serialize_product(conn, dict(r), include_private=False) for r in cur.fetchall()]
        if in_stock_only:
            items = [it for it in items if it["in_stock"]]

        for attr_key, qp_val in dynamic_attr_filters.items():
            items = [
                it for it in items
                if it.get("attributes", {}).get(attr_key) == qp_val
                or any(v.get("attributes", {}).get(attr_key) == qp_val for v in it.get("variants", []))
            ]
        total = len(items)
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
        cur.execute(
            """SELECT p.* FROM products p
               JOIN categories c ON c.id = p.category_id
               WHERE p.slug = ? AND p.status = 'published' AND p.deleted_at IS NULL
                 AND c.is_active = 1 AND c.deleted_at IS NULL""",
            (slug,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return serialize_product(conn, dict(row), include_private=False)

def compute_customer_cod_risk(conn, raw_phone: str) -> dict:
    """
    Anti-Retour COD Scoring Engine:
    Calculates delivered vs returned/cancelled ratios for an Algerian customer phone number
    and checks `customer_phone_blacklist` to flag repeat non-pickup buyers before order confirmation.
    """
    from .whatsapp import normalize_algerian_phone as _norm_phone
    e164_p, local_p, _ = _norm_phone(raw_phone)
    cur = conn.cursor()
    cur.execute(
        """SELECT
               COUNT(*) AS total_orders,
               COALESCE(SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END), 0) AS delivered_count,
               COALESCE(SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END), 0) AS returned_count,
               COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_count
           FROM orders
           WHERE customer_phone IN (?, ?, ?)""",
        (raw_phone, e164_p, local_p)
    )
    stats = cur.fetchone()
    total_ord = int(stats["total_orders"] or 0)
    deliv = int(stats["delivered_count"] or 0)
    ret = int(stats["returned_count"] or 0)
    canc = int(stats["cancelled_count"] or 0)

    denom = deliv + ret
    return_rate_pct = round((ret / denom) * 100, 1) if denom > 0 else (100.0 if ret > 0 else 0.0)

    cur.execute(
        "SELECT * FROM customer_phone_blacklist WHERE (phone_e164 = ? OR phone_local = ?) AND is_blocked = 1",
        (e164_p, local_p)
    )
    bl = cur.fetchone()
    is_blacklisted = bool(bl)
    blacklist_reason = bl["reason"] if bl else None

    if is_blacklisted:
        risk_level = "blacklisted"
        badge_fr = f"⛔ NUMÉRO BLOQUÉ (Liste Noire COD : {blacklist_reason})"
    elif ret >= 2 or (ret >= 1 and return_rate_pct >= 50.0):
        risk_level = "high_risk"
        badge_fr = f"⚠️ RISQUE RETOUR ÉLEVÉ ({ret} retour(s) / {deliv} livré(s) • {return_rate_pct}% retours)"
    elif ret == 1 or canc >= 2:
        risk_level = "medium_risk"
        badge_fr = f"⚡ Vigilance COD ({ret} retour, {canc} annulée(s), {deliv} livrée(s))"
    elif deliv >= 2 and ret == 0:
        risk_level = "trusted"
        badge_fr = f"✓ Client Fiable Vérifié ({deliv} livrée(s) • 0% retour)"
    else:
        risk_level = "normal"
        badge_fr = f"Client COD ({deliv} livrée(s) / {ret} retour)"

    return {
        "phone_e164": e164_p,
        "phone_local": local_p,
        "total_orders": total_ord,
        "delivered_count": deliv,
        "returned_count": ret,
        "cancelled_count": canc,
        "return_rate_percent": return_rate_pct,
        "is_blacklisted": is_blacklisted,
        "blacklist_reason": blacklist_reason,
        "risk_level": risk_level,
        "warning_badge_fr": badge_fr,
    }

@app.post("/api/v1/orders", status_code=201)
def create_guest_order(
    payload: GuestOrderCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"order:{client_ip}", max_requests=15, window_seconds=60)

    # Anti-Retour COD: Block orders from phones on the active COD Blacklist
    from .whatsapp import normalize_algerian_phone as _norm_phone
    e164_chk, local_chk, _ = _norm_phone(payload.phone)
    with db_session() as chk_conn:
        chk_cur = chk_conn.cursor()
        chk_cur.execute(
            "SELECT * FROM customer_phone_blacklist WHERE (phone_e164 = ? OR phone_local = ?) AND is_blocked = 1",
            (e164_chk, local_chk)
        )
        bl_row = chk_cur.fetchone()
        if bl_row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Commande refusée (Protection Anti-Retour COD) : Ce numéro ({local_chk}) ne peut pas passer de commande automatique. Contactez le service client Mus Luxury sur WhatsApp au 0655534154."
            )

    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    # Compute idempotency signature from explicit Idempotency-Key header or deterministic order payload (M-10)
    has_explicit_idem_key = bool(idempotency_key and idempotency_key.strip())
    if has_explicit_idem_key:
        idem_raw = f"explicit_key:{idempotency_key.strip()}"
    else:
        idem_raw = f"{payload.phone}|{payload.wilaya_code}|{payload.commune}|" + ",".join(
            f"{i.variant_id}:{i.quantity}" for i in sorted(payload.items, key=lambda x: x.variant_id)
        )
    idem_hash = hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()
    cutoff_utc = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()

        # Check duplicate order submission (explicit keys permanent; payload-derived keys scoped to 10-minute window)
        if has_explicit_idem_key:
            cur.execute("SELECT order_reference FROM orders WHERE idempotency_hash = ? AND status != 'cancelled'", (idem_hash,))
        else:
            cur.execute(
                "SELECT order_reference FROM orders WHERE idempotency_hash = ? AND status != 'cancelled' AND created_at >= ?",
                (idem_hash, cutoff_utc),
            )
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

        # 2. Consolidate duplicate variant_ids, Verify Variants & Stock, and Calculate True Server-Side Subtotal
        consolidated_items: List[OrderItemInput] = []
        merged_qty_by_vid: Dict[int, int] = {}
        for raw_item in payload.items:
            merged_qty_by_vid[raw_item.variant_id] = merged_qty_by_vid.get(raw_item.variant_id, 0) + int(raw_item.quantity)
        for vid, total_q in merged_qty_by_vid.items():
            if total_q > 50:
                raise HTTPException(status_code=422, detail=f"Maximum quantity per variant is 50 (requested {total_q})")
            consolidated_items.append(OrderItemInput(variant_id=vid, quantity=total_q))

        subtotal_dzd = 0
        resolved_lines = []
        for item in consolidated_items:
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
            if dict(cpn).get("usage_limit") is not None and int(cpn["usage_count"]) >= int(dict(cpn)["usage_limit"]):
                raise HTTPException(status_code=400, detail=f"Coupon '{cpn['code']}' has reached its maximum usage limit")
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
            cur.execute(
                "UPDATE coupons SET usage_count = usage_count + 1 WHERE id = ? AND is_active = 1 AND (usage_limit IS NULL OR usage_count < usage_limit)",
                (cpn["id"],),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=400, detail=f"Coupon '{cpn['code']}' has reached its maximum usage limit")

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

        # 4. Create Order Record (M-11: 32-bit random hex suffix + retry on reference collision)
        order_ref = ""
        order_id = None
        for _attempt in range(3):
            order_ref = f"LUX-{int(time.time()) % 100000:05d}-{secrets.token_hex(4).upper()}"
            try:
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
                        payload.customer_notes, idem_hash,
                    ),
                )
                order_id = cur.lastrowid
                break
            except Exception as exc:
                if _attempt == 2:
                    raise

        # 5. Insert Order Items, Decrement Stock Safely & Log Inventory Movements
        out_items = []
        for v, qty, unit_price, line_total in resolved_lines:
            cur.execute(
                """INSERT INTO order_items
                   (order_id, product_id, variant_id, product_name, variant_title, sku, unit_price_dzd, quantity, line_total_dzd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, v["product_id"], v["id"], v["product_name"], v["title"], v["sku"], unit_price, qty, line_total)
            )
            cur.execute(
                "UPDATE product_variants SET stock_qty = stock_qty - ? WHERE id = ? AND is_active = 1 AND stock_qty >= ?",
                (qty, v["id"], qty)
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for '{v['product_name']} ({v['title']})'"
                )
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (v["id"],))
            new_qty = int(cur.fetchone()["stock_qty"])
            prev_qty = new_qty + qty
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
            "whatsapp_confirmation_url": build_customer_order_whatsapp_message(
                {
                    "order_reference": order_ref,
                    "customer_name": payload.full_name,
                    "customer_phone": payload.phone,
                    "wilaya_code": payload.wilaya_code,
                    "wilaya_name": zone["wilaya_name_fr"],
                    "commune": payload.commune,
                    "delivery_method": payload.delivery_method,
                    "total_dzd": total_dzd,
                },
                "confirmation_call",
            )["wa_me_boutique_url"],
            "customer_whatsapp_url": build_customer_order_whatsapp_message(
                {
                    "order_reference": order_ref,
                    "customer_name": payload.full_name,
                    "customer_phone": payload.phone,
                    "wilaya_code": payload.wilaya_code,
                    "wilaya_name": zone["wilaya_name_fr"],
                    "commune": payload.commune,
                    "delivery_method": payload.delivery_method,
                    "total_dzd": total_dzd,
                },
                "confirmation_call",
            )["wa_me_customer_url"],
            "items": out_items,
            "message_fr": "Votre commande a été enregistrée avec succès. Paiement à la livraison (Cash on Delivery)."
        }

# ============================================================================
# ADMINISTRATIVE ENDPOINTS (/api/v1/admin/*)
# ============================================================================

@app.post("/api/v1/admin/auth/login")
def admin_login(payload: LoginRequest, request: Request):
    client_ip = get_real_client_ip(request)
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
        candidate_hash = user["password_hash"] if user else _DUMMY_PASSWORD_HASH
        pw_ok = verify_password(payload.password, candidate_hash)
        if not user or not pw_ok:
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

        cur.execute("SELECT id, slug, sku FROM products WHERE slug = ? OR sku = ?", (payload.slug, payload.sku))
        existing_prod = cur.fetchone()
        if existing_prod:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with slug '{payload.slug}' or SKU '{payload.sku}' already exists"
            )
        for v in payload.variants:
            cur.execute("SELECT id FROM product_variants WHERE sku = ?", (v.sku,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Variant SKU '{v.sku}' already exists"
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
            cur.execute("SELECT id FROM product_variants WHERE sku = ?", (v_sku,))
            if cur.fetchone():
                disambig = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:4].upper()
                v_sku = f"{v_sku}-{disambig}"
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
            od["cod_risk"] = compute_customer_cod_risk(conn, od["customer_phone"])
            od["whatsapp_actions"] = {
                "confirmation_call_url": build_customer_order_whatsapp_message(od, "confirmation_call")["wa_me_customer_url"],
                "shipped_notice_url": build_customer_order_whatsapp_message(od, "shipped_notice")["wa_me_customer_url"],
                "no_answer_followup_url": build_customer_order_whatsapp_message(od, "no_answer_followup")["wa_me_customer_url"],
                "delivery_arrived_url": build_customer_order_whatsapp_message(od, "delivery_arrived")["wa_me_customer_url"],
            }
            orders.append(od)
        return {"items": orders}

@app.patch("/api/v1/admin/orders/{order_id}")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
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

        # If order is cancelled or returned and stock was deducted, restore stock atomically (H-2 & M-14)
        if payload.status in ("cancelled", "returned") and stock_deducted == 1:
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            for item in cur.fetchall():
                qty_restore = int(item["quantity"])
                cur.execute(
                    "UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ?",
                    (qty_restore, item["variant_id"]),
                )
                if cur.rowcount == 0:
                    # M-14: Variant row was deleted; skip gracefully without raising TypeError (500)
                    continue
                cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (item["variant_id"],))
                v = cur.fetchone()
                if not v:
                    continue
                new_q = int(v["stock_qty"])
                prev_q = new_q - qty_restore
                cur.execute(
                    "UPDATE products SET sales_count = CASE WHEN sales_count >= ? THEN sales_count - ? ELSE 0 END WHERE id = ?",
                    (int(item["quantity"]), int(item["quantity"]), item["product_id"])
                )
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

def _resolve_writable_dir(env_key: str, local_subdir: str) -> str:
    local_default = os.path.join(os.path.dirname(os.path.dirname(__file__)), local_subdir)
    candidate = os.getenv(env_key, local_default)
    try:
        os.makedirs(candidate, exist_ok=True)
        if os.access(candidate, os.W_OK):
            return candidate
    except OSError:
        pass
    os.makedirs(local_default, exist_ok=True)
    return local_default

UPLOAD_STORAGE_DIR = _resolve_writable_dir("UPLOAD_DIR", "uploads")
BACKUP_STORAGE_DIR = _resolve_writable_dir("BACKUP_DIR", "backups")

MAX_UPLOAD_IMAGE_BYTES = 5 * 1024 * 1024

@app.post("/api/v1/admin/upload", status_code=201)
async def upload_product_image(
    file: UploadFile = File(...),
    admin: dict = Depends(require_permission("products:write"))
):
    data = await file.read(MAX_UPLOAD_IMAGE_BYTES + 1)
    if len(data) > MAX_UPLOAD_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds maximum allowed size of 5 MB")
    validate_uploaded_image(file.filename or "upload.jpg", file.content_type or "", data)
    digest = hashlib.sha256(data).hexdigest()[:16]
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    safe_name = f"img_{digest}{ext}"
    dest_path = os.path.join(UPLOAD_STORAGE_DIR, safe_name)
    with open(dest_path, "wb") as uf:
        uf.write(data)
    return {"filename": safe_name, "url": f"/uploads/{safe_name}", "size_bytes": len(data)}

@app.get("/uploads/{filename}")
def serve_uploaded_image(filename: str):
    if not re.match(r"^img_[a-f0-9]{16}\.(jpg|png|webp)$", filename):
        raise HTTPException(status_code=400, detail="Invalid media filename")
    fpath = os.path.join(UPLOAD_STORAGE_DIR, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Uploaded media file not found")
    ext = os.path.splitext(filename)[1].lower()
    mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(ext, "application/octet-stream")
    with open(fpath, "rb") as f:
        raw = f.read()
    return Response(
        content=raw,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=2592000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )

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
        sql_dump = "\n".join(conn.iterdump())
        compressed_bytes = gzip.compress(sql_dump.encode("utf-8"))
        encrypted_bytes = encrypt_backup_bytes(compressed_bytes)
        checksum = hashlib.sha256(encrypted_bytes).hexdigest()
        fname = f"luxe_backup_{int(time.time())}_{secrets.token_hex(3)}.sql.gz"
        fpath = os.path.join(BACKUP_STORAGE_DIR, fname)
        with open(fpath, "wb") as bf:
            bf.write(encrypted_bytes)
        real_size = len(encrypted_bytes)

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

        raw_fname = str(bkp["filename"] or "")
        if not raw_fname or os.path.basename(raw_fname) != raw_fname:
            raise HTTPException(status_code=400, detail="Invalid backup filename")
        fpath = os.path.abspath(os.path.join(BACKUP_STORAGE_DIR, raw_fname))
        if not fpath.startswith(os.path.abspath(BACKUP_STORAGE_DIR) + os.sep):
            raise HTTPException(status_code=400, detail="Backup path traversal blocked")
        if not os.path.isfile(fpath):
            raise HTTPException(status_code=404, detail="Backup file missing from storage directory")

        with open(fpath, "rb") as bf:
            stored_bytes = bf.read()

        actual_sha256 = hashlib.sha256(stored_bytes).hexdigest()
        if not hmac.compare_digest(actual_sha256, bkp["sha256_checksum"]):
            cur.execute("UPDATE backup_records SET status = 'failed' WHERE id = ?", (backup_id,))
            raise HTTPException(status_code=400, detail="Backup integrity check failed: SHA-256 mismatch")

        try:
            compressed_bytes = decrypt_backup_bytes(stored_bytes)
            sql_script = gzip.decompress(compressed_bytes).decode("utf-8")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Backup decryption or decompression failed: {exc}")
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
            if _is_protected_setting_key(r["setting_key"]):
                continue
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
    _ensure_safe_url_or_text(payload.title_fr, "title_fr")
    _ensure_safe_url_or_text(payload.cta_link or "", "cta_link")
    _ensure_safe_url_or_text(payload.image_url or "", "image_url")
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

@app.delete("/api/v1/admin/banners/{banner_id}")
def admin_delete_banner(
    banner_id: int,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM banners WHERE id = ?", (banner_id,))
        b = cur.fetchone()
        if not b:
            raise HTTPException(status_code=404, detail="Banner not found")
        cur.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
        log_audit(conn, int(admin["sub"]), "delete_banner", "banner", str(banner_id), {"title_fr": b["title_fr"]})
        return {"deleted": True, "banner_id": banner_id}

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
    for k, v in payload.settings.items():
        if _is_protected_setting_key(k):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Protected system setting '{k}' cannot be modified via store settings API"
            )
        _ensure_safe_url_or_text(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v), k)
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

from .security import hash_password, REVOKED_TOKENS, revoke_all_user_sessions

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
    usage_limit: Optional[int] = Field(None, ge=1)

from .whatsapp import (
    build_customer_order_whatsapp_message,
    dispatch_customer_whatsapp_order_update,
    list_recent_whatsapp_outbox,
    normalize_algerian_phone,
    get_whatsapp_config,
    dispatch_whatsapp_recovery_otp,
    verify_whatsapp_webhook_signature,
)

@app.get("/api/v1/admin/auth/recovery/status")
def get_admin_recovery_status():
    """
    Returns WhatsApp Business Cloud API readiness and recovery channels status
    without exposing any secret tokens.
    """
    cfg = get_whatsapp_config()
    return {
        "whatsapp_cloud_api_configured": cfg["is_configured"],
        "sandbox_mode": cfg["sandbox_mode"],
        "api_version": cfg["api_version"],
        "template_name": cfg["template_name"],
        "offline_emergency_enabled": True,
        "supported_channels": ["whatsapp_cloud_api", "offline_emergency"],
        "boutique_whatsapp_e164": "+213655534154",
        "boutique_whatsapp_local": "0655534154",
    }

@app.post("/api/v1/admin/auth/recovery/request")
def request_admin_password_recovery(payload: RecoveryRequestInput, request: Request):
    """
    Initiates administrator password recovery via the official WhatsApp Business Cloud API
    or validates readiness for Offline Emergency Code verification.
    Strict Rule (Section 6): If WhatsApp API credentials are not configured on the server,
    explicitly report 503 Service Unavailable — never silently simulate message delivery.
    Supports both international (+213...) and local Algerian (05/06/07...) phone formats,
    matching either primary `phone` or `emergency_phone`.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"recovery_req:{client_ip}", max_requests=3, window_seconds=300)

    cfg = get_whatsapp_config()
    if payload.channel == "whatsapp_cloud_api" and not cfg["is_configured"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Official WhatsApp Business Cloud API is not configured on this server (missing WHATSAPP_CLOUD_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID). Use an administrator-generated offline emergency recovery code instead."
        )

    e164_phone, local_phone, _ = normalize_algerian_phone(payload.phone)
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM admin_users
               WHERE (phone IN (?, ?) OR emergency_phone IN (?, ?))
                 AND is_active = 1 AND whatsapp_verified = 1""",
            (e164_phone, local_phone, e164_phone, local_phone)
        )
        user = cur.fetchone()

        if payload.channel == "offline_emergency":
            if user:
                log_audit(conn, user["id"], "offline_emergency_recovery_initiated", "admin_user", str(user["id"]), {"channel": "offline_emergency"})
            return {
                "status": "recovery_initiated",
                "channel": "offline_emergency",
                "message": "Saisissez votre code de secours hors-ligne à usage unique et votre nouveau mot de passe."
            }

        # Do not reveal whether an arbitrary phone number is registered
        if user and payload.channel == "whatsapp_cloud_api":
            otp = f"{secrets.randbelow(900000) + 100000}"
            otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
            expires_at = int(time.time()) + 300  # 5 minutes expiry

            # Invalidate any older unused WhatsApp OTP codes for this user before issuing a new one
            cur.execute(
                "UPDATE admin_recovery_codes SET is_used = 1 WHERE admin_user_id = ? AND channel = 'whatsapp_cloud_api' AND is_used = 0",
                (user["id"],)
            )
            cur.execute(
                """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
                   VALUES (?, ?, ?, 'whatsapp_cloud_api', 3, ?)""",
                (user["id"], e164_phone, otp_hash, expires_at)
            )
            try:
                dispatch_info = dispatch_whatsapp_recovery_otp(e164_phone, otp, expires_minutes=5)
                log_audit(
                    conn,
                    user["id"],
                    "whatsapp_recovery_requested",
                    "admin_user",
                    str(user["id"]),
                    {"channel": payload.channel, "mode": dispatch_info.get("mode"), "message_id": dispatch_info.get("message_id")},
                )
            except RuntimeError as exc:
                log_audit(conn, user["id"], "whatsapp_recovery_dispatch_error", "admin_user", str(user["id"]), {"error": str(exc)[:200]})
                if not config.is_production():
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

            resp = {
                "status": "recovery_initiated",
                "channel": "whatsapp_cloud_api",
                "expires_in_seconds": 300,
                "message": "If this verified administrator number is eligible, a single-use verification code has been dispatched.",
            }
            if (not config.is_production()) and cfg["test_capture"]:
                resp["test_otp"] = otp
            return resp

        return {
            "status": "recovery_initiated",
            "channel": payload.channel,
            "expires_in_seconds": 300,
            "message": "If this verified administrator number is eligible, a single-use verification code has been dispatched.",
        }

@app.post("/api/v1/admin/auth/recovery/verify")
def verify_admin_password_recovery(payload: RecoveryVerifyInput, request: Request):
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"recovery_verify:{client_ip}", max_requests=5, window_seconds=300)

    e164_phone, local_phone, _ = normalize_algerian_phone(payload.phone)
    submitted_hash = hashlib.sha256(payload.verification_code.strip().encode("utf-8")).hexdigest()
    now_ts = int(time.time())

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM admin_users
               WHERE (phone IN (?, ?) OR emergency_phone IN (?, ?))
                 AND is_active = 1""",
            (e164_phone, local_phone, e164_phone, local_phone)
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")

        cur.execute(
            """SELECT * FROM admin_recovery_codes
               WHERE admin_user_id = ? AND is_used = 0 AND expires_at >= ?
               ORDER BY id DESC LIMIT 10""",
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
            log_audit(conn, user["id"], "password_recovery_failed", "admin_user", str(user["id"]), {"phone": e164_phone})
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")

        # Mark single-use code as used, update password with PBKDF2-HMAC-SHA256, and revoke existing tokens
        cur.execute("UPDATE admin_recovery_codes SET is_used = 1, attempts = attempts + 1 WHERE id = ?", (matched_code["id"],))
        new_hash = hash_password(payload.new_password)
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_hash, user["id"])
        )
        revoke_all_user_sessions(int(user["id"]), conn)

        # If an offline_emergency code was consumed, automatically provision a replacement single-use emergency code
        replacement_emergency_code = None
        if matched_code["channel"] == "offline_emergency":
            replacement_emergency_code = f"LUXE-EMERG-{secrets.token_hex(4).upper()}"
            repl_hash = hashlib.sha256(replacement_emergency_code.encode("utf-8")).hexdigest()
            cur.execute(
                """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
                   VALUES (?, ?, ?, 'offline_emergency', 3, ?)""",
                (user["id"], user["emergency_phone"] or user["phone"], repl_hash, int(time.time()) + 86400 * 365)
            )

        log_audit(conn, user["id"], "password_recovered_and_rotated", "admin_user", str(user["id"]), {"channel": matched_code["channel"]})
        result = {"status": "password_updated", "sessions_revoked": True, "channel_used": matched_code["channel"]}
        if replacement_emergency_code:
            result["replacement_emergency_code"] = replacement_emergency_code
        return result

@app.post("/api/v1/admin/auth/recovery/rotate-emergency-code")
def rotate_admin_emergency_recovery_code(admin: dict = Depends(require_permission("settings:write"))):
    """
    Generates a fresh single-use offline emergency recovery code for the authenticated administrator
    and invalidates previous unused offline emergency codes.
    """
    admin_id = int(admin["sub"])
    new_code = f"LUXE-EMERG-{secrets.token_hex(6).upper()}"
    new_hash = hashlib.sha256(new_code.encode("utf-8")).hexdigest()
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT phone, emergency_phone FROM admin_users WHERE id = ?", (admin_id,))
        u = cur.fetchone()
        target_phone = (u["emergency_phone"] or u["phone"]) if u else "+213655534154"
        cur.execute(
            "UPDATE admin_recovery_codes SET is_used = 1 WHERE admin_user_id = ? AND channel = 'offline_emergency' AND is_used = 0",
            (admin_id,)
        )
        cur.execute(
            """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
               VALUES (?, ?, ?, 'offline_emergency', 3, ?)""",
            (admin_id, target_phone, new_hash, int(time.time()) + 86400 * 365)
        )
        log_audit(conn, admin_id, "rotate_emergency_recovery_code", "admin_user", str(admin_id), {})
        return {
            "status": "rotated",
            "emergency_code": new_code,
            "expires_in_days": 365,
            "notice": "Conservez ce code hors-ligne en lieu sûr. Seul son hash SHA-256 est stocké en base."
        }

MAX_WEBHOOK_BODY_BYTES = 64 * 1024
MAX_WEBHOOK_STATUSES_PER_CALL = 50

@app.get("/api/v1/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Meta WhatsApp Cloud API Webhook Verification Endpoint (GET).
    C-3.4: Returns 503 when WHATSAPP_WEBHOOK_VERIFY_TOKEN is empty/unconfigured.
    """
    cfg = get_whatsapp_config()
    expected_token = cfg["webhook_verify_token"]
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WhatsApp webhook verify token is not configured")
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, expected_token):
        return Response(content=str(hub_challenge or ""), media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification token mismatch")

@app.post("/api/v1/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    """
    Meta WhatsApp Cloud API Webhook Receiver (POST) for message delivery & read receipts (H-4).
    - Enforces per-IP rate limiting.
    - Returns 503 if WHATSAPP_APP_SECRET is not configured.
    - Caps payload size at 64 KB and statuses logged per request at 50.
    - Always requires a valid HMAC-SHA256 X-Hub-Signature-256 header.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"wa_webhook:{client_ip}", max_requests=60, window_seconds=60)
    cfg = get_whatsapp_config()
    if not cfg["app_secret"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WhatsApp webhook app secret is not configured")
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook payload exceeds 64 KB limit")
    sig_header = request.headers.get("X-Hub-Signature-256")
    if not verify_whatsapp_webhook_signature(raw_body, sig_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Hub-Signature-256 webhook signature")
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON webhook payload")

    statuses_logged = 0
    with db_session(commit=True) as conn:
        for entry in (payload.get("entry") or [])[:20]:
            for change in (entry.get("changes") or [])[:20]:
                val = change.get("value") or {}
                for st in (val.get("statuses") or [])[:MAX_WEBHOOK_STATUSES_PER_CALL]:
                    if statuses_logged >= MAX_WEBHOOK_STATUSES_PER_CALL:
                        break
                    statuses_logged += 1
                    log_audit(
                        conn,
                        None,
                        "whatsapp_webhook_status",
                        "whatsapp_message",
                        str(st.get("id", "unknown"))[:120],
                        {"status": str(st.get("status", ""))[:64], "recipient_id": str(st.get("recipient_id", ""))[:64]},
                    )
    return {"received": True, "statuses_logged": statuses_logged}

# ============================================================================
# SECTION 5 & 9: GUEST ORDER TRACKING, COUPONS & OPTIMISTIC CONCURRENCY SYNC
# ============================================================================

@app.get("/api/v1/orders/track")
def track_guest_order(request: Request, reference: str = Query(...), phone: str = Query(...)):
    """
    Public guest order tracking requiring BOTH order_reference and matching customer phone
    to prevent IDOR enumeration of other customers' orders.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"track_order:{client_ip}", max_requests=30, window_seconds=60)
    from .whatsapp import normalize_algerian_phone as _norm_phone
    e164_p, local_p, _ = _norm_phone(phone)
    cleaned_phone = re.sub(r"[\s\-\.]", "", phone)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM orders WHERE order_reference = ? AND customer_phone IN (?, ?, ?)",
            (reference.strip().upper(), cleaned_phone, local_p, e164_p)
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
        if payload.sku and payload.sku != prod["sku"]:
            cur.execute("SELECT id FROM products WHERE sku = ? AND id != ?", (payload.sku, product_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product SKU '{payload.sku}' is already used by another product"
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
               WHERE id = ? AND version = ?""",
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
                current_version,
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
        code_upper = payload.code.strip().upper()
        cur.execute("SELECT id FROM coupons WHERE UPPER(code) = ?", (code_upper,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Coupon code '{code_upper}' already exists")
        cur.execute(
            """INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, max_discount_dzd, usage_limit, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (payload.code.upper(), payload.discount_type, payload.discount_value, payload.min_order_dzd, payload.max_discount_dzd, payload.usage_limit)
        )
        cid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_coupon", "coupon", str(cid), {"code": payload.code.upper()})
        cur.execute("SELECT * FROM coupons WHERE id = ?", (cid,))
        return dict(cur.fetchone())

@app.get("/api/v1/admin/coupons")
def admin_list_coupons(admin: dict = Depends(require_permission("content:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM coupons ORDER BY id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.delete("/api/v1/admin/coupons/{coupon_id}")
def admin_deactivate_coupon(
    coupon_id: int,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,))
        cpn = cur.fetchone()
        if not cpn:
            raise HTTPException(status_code=404, detail="Coupon not found")
        cur.execute("UPDATE coupons SET is_active = 0 WHERE id = ?", (coupon_id,))
        log_audit(conn, int(admin["sub"]), "deactivate_coupon", "coupon", str(coupon_id), {"code": cpn["code"]})
        return {"deactivated": True, "coupon_id": coupon_id, "code": cpn["code"]}


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
    client_ip = get_real_client_ip(request)
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
    is_active: Optional[bool] = True

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
        if dict(cpn).get("usage_limit") is not None and int(cpn["usage_count"]) >= int(dict(cpn)["usage_limit"]):
            raise HTTPException(status_code=400, detail="Ce code promo a atteint sa limite d'utilisation")
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
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variant not found")
        cur.execute(
            "UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ? AND (stock_qty + ?) >= 0",
            (payload.change_qty, variant_id, payload.change_qty)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="Stock quantity cannot become negative")
        cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (variant_id,))
        new_qty = int(cur.fetchone()["stock_qty"])
        prev_qty = new_qty - payload.change_qty
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
            cpn_limit_ok = cpn and (dict(cpn).get("usage_limit") is None or int(cpn["usage_count"]) < int(dict(cpn)["usage_limit"]))
            if cpn and cpn_limit_ok and subtotal_dzd >= int(cpn["min_order_dzd"]):
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
            if item.is_active is not None:
                cur.execute("UPDATE delivery_zones SET is_active = ? WHERE id = ?", (1 if item.is_active else 0, z["id"]))
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
    slug: Optional[str] = None
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

        cur.execute(f"SELECT COUNT(*) AS cnt FROM products p WHERE {' AND '.join(where)}", params)
        total = int(cur.fetchone()["cnt"])
        start = (page - 1) * page_size
        cur.execute(
            f"SELECT * FROM products p WHERE {' AND '.join(where)} ORDER BY p.id DESC LIMIT ? OFFSET ?",
            [*params, page_size, start]
        )
        paged_rows = [serialize_product(conn, dict(r), include_private=True) for r in cur.fetchall()]
        return {
            "items": paged_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

@app.delete("/api/v1/admin/products/{product_id}")
def admin_safe_delete_or_archive_product(
    product_id: int,
    hard_delete: bool = Query(False),
    force: bool = Query(False),
    admin: dict = Depends(require_permission("products:write"))
):
    """
    Safely archives or permanently deletes a product without destroying historical order records.
    If hard_delete=True and the product has never been ordered, it is permanently deleted from database.
    If historical orders exist and force=False, it is safely archived to preserve customer invoices.
    If hard_delete=True and force=True, historical test order attachments are purged and product is deleted.
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM order_items WHERE product_id = ? OR variant_id IN (SELECT id FROM product_variants WHERE product_id = ?)",
            (product_id, product_id)
        )
        order_refs = cur.fetchone()["cnt"]

        if hard_delete:
            if order_refs > 0 and not force:
                # Historical orders exist: preserve accounting & invoice immutability unless forced
                cur.execute(
                    "UPDATE products SET status = 'archived', deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (product_id,)
                )
                cur.execute("UPDATE product_variants SET is_active = 0 WHERE product_id = ?", (product_id,))
                log_audit(conn, int(admin["sub"]), "archive_product", "product", str(product_id), {
                    "sku": prod["sku"],
                    "historical_order_items_preserved": order_refs,
                    "reason": "Hard delete converted to archive to protect orders"
                })
                return {
                    "archived": True,
                    "deleted": False,
                    "has_orders": True,
                    "product_id": product_id,
                    "status": "archived",
                    "historical_order_items_preserved": order_refs,
                    "message": f"Ce produit a {order_refs} commande(s) rattachée(s) : archivé pour protéger la comptabilité. Utilisez l'option 'Forcer' pour le retirer définitivement."
                }

            if force and order_refs > 0:
                cur.execute("DELETE FROM order_items WHERE product_id = ? OR variant_id IN (SELECT id FROM product_variants WHERE product_id = ?)", (product_id, product_id))
                cur.execute("DELETE FROM orders WHERE id NOT IN (SELECT DISTINCT order_id FROM order_items)")

            # Hard delete: permanently remove product and all dependent data
            cur.execute("DELETE FROM purchase_order_items WHERE product_id = ? OR variant_id IN (SELECT id FROM product_variants WHERE product_id = ?)", (product_id, product_id))
            cur.execute("DELETE FROM inventory_movements WHERE variant_id IN (SELECT id FROM product_variants WHERE product_id = ?)", (product_id,))
            cur.execute("DELETE FROM variant_attribute_values WHERE variant_id IN (SELECT id FROM product_variants WHERE product_id = ?)", (product_id,))
            cur.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM product_images WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM product_attribute_values WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM products WHERE id = ?", (product_id,))

            log_audit(conn, int(admin["sub"]), "delete_product", "product", str(product_id), {
                "sku": prod["sku"],
                "name_fr": prod["name_fr"],
                "forced": force
            })
            return {
                "deleted": True,
                "archived": False,
                "product_id": product_id,
                "status": "deleted",
                "historical_order_items_preserved": 0,
                "message": f"Produit \"{prod['name_fr']}\" supprimé définitivement du catalogue et de la base."
            }

        # Soft archive (default)
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
            "deleted": False,
            "product_id": product_id,
            "status": "archived",
            "historical_order_items_preserved": order_refs,
            "message": f"Produit \"{prod['name_fr']}\" archivé avec succès."
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
    hard_delete: bool = Query(False),
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE category_id = ? AND deleted_at IS NULL", (category_id,))
        prods_count = cur.fetchone()["cnt"]

        if hard_delete:
            if prods_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Impossible de supprimer définitivement : {prods_count} produit(s) sont encore rattachés à cette catégorie. Veuillez d'abord réassigner ou archiver ces produits."
                )
            cur.execute("DELETE FROM category_attribute_options WHERE attribute_id IN (SELECT id FROM category_attributes WHERE category_id = ?)", (category_id,))
            cur.execute("DELETE FROM category_attributes WHERE category_id = ?", (category_id,))
            cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            log_audit(conn, int(admin["sub"]), "delete_category_permanent", "category", str(category_id), {"slug": cat["slug"]})
            return {"deleted": True, "category_id": category_id}
        else:
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
        def _safe_csv_cell(val: Any) -> Any:
            if not isinstance(val, str):
                return val
            stripped = val.lstrip()
            # Prevent CSV Formula Injection in Excel/Calc while preserving +213 phone numbers
            if stripped.startswith(("=", "-", "@", "\t", "\r")) or (stripped.startswith("+") and not re.match(r"^\+213\d+$", stripped)):
                return f"'{val}"
            return val

        for r in cur.fetchall():
            writer.writerow([
                r["id"], _safe_csv_cell(r["order_reference"]), _safe_csv_cell(r["status"]), _safe_csv_cell(r["payment_method"]),
                _safe_csv_cell(r["customer_name"]), _safe_csv_cell(r["customer_phone"]), _safe_csv_cell(r["wilaya_code"]), _safe_csv_cell(r["wilaya_name"]),
                _safe_csv_cell(r["commune"]), _safe_csv_cell(r["delivery_method"]), r["subtotal_dzd"], r["delivery_fee_dzd"],
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

@app.get("/health")
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


# ============================================================================
# ANTI-RETOUR COD: PHONE RETURN-RATE SCORING & BLACKLIST MANAGEMENT
# ============================================================================

class CodBlacklistInput(BaseModel):
    phone: str = Field(..., min_length=8, max_length=30)
    reason: str = Field("Retour abusif / Non-récupération COD", min_length=3, max_length=250)
    is_blocked: bool = True

@app.get("/api/v1/admin/cod-risk/check")
def admin_check_phone_cod_risk(
    phone: str = Query(..., min_length=8),
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        return compute_customer_cod_risk(conn, phone)

@app.get("/api/v1/admin/cod-risk/blacklist")
def admin_list_cod_blacklist(
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customer_phone_blacklist WHERE is_blocked = 1 ORDER BY id DESC")
        items = []
        for r in cur.fetchall():
            row = dict(r)
            row["cod_risk"] = compute_customer_cod_risk(conn, row["phone_e164"])
            items.append(row)
        return {"items": items}

@app.post("/api/v1/admin/cod-risk/blacklist")
def admin_upsert_cod_blacklist(
    payload: CodBlacklistInput,
    admin: dict = Depends(require_permission("orders:write"))
):
    e164_p, local_p, _ = normalize_algerian_phone(payload.phone)
    if not re.match(r"^\+213(5|6|7)[0-9]{8}$", e164_p):
        raise HTTPException(status_code=400, detail="Format de numéro algérien invalide (05/06/07 ou +213)")
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO customer_phone_blacklist (phone_e164, phone_local, reason, is_blocked, blocked_by, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(phone_e164) DO UPDATE SET
                   reason = excluded.reason,
                   is_blocked = excluded.is_blocked,
                   blocked_by = excluded.blocked_by,
                   updated_at = CURRENT_TIMESTAMP""",
            (e164_p, local_p, payload.reason.strip(), 1 if payload.is_blocked else 0, int(admin["sub"]))
        )
        log_audit(conn, int(admin["sub"]), "upsert_cod_blacklist", "customer_phone_blacklist", e164_p, {
            "phone_local": local_p,
            "reason": payload.reason.strip(),
            "is_blocked": payload.is_blocked,
        })
        return compute_customer_cod_risk(conn, e164_p)

@app.delete("/api/v1/admin/cod-risk/blacklist/{phone}")
def admin_remove_cod_blacklist(
    phone: str,
    admin: dict = Depends(require_permission("orders:write"))
):
    e164_p, local_p, _ = normalize_algerian_phone(phone)
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE customer_phone_blacklist SET is_blocked = 0, updated_at = CURRENT_TIMESTAMP WHERE phone_e164 = ? OR phone_local = ?",
            (e164_p, local_p)
        )
        log_audit(conn, int(admin["sub"]), "remove_cod_blacklist", "customer_phone_blacklist", e164_p, {})
        return compute_customer_cod_risk(conn, e164_p)


# ============================================================================
# CUSTOMER & ADMIN WHATSAPP COMMUNICATION ENGINE & NETWORKING OUTBOX
# ============================================================================

class OrderWhatsappNotifyInput(BaseModel):
    template_type: str = Field("confirmation_call", regex=r"^(confirmation_call|shipped_notice|no_answer_followup|delivery_arrived)$")
    custom_message: Optional[str] = Field(None, max_length=1000)


@app.post("/api/v1/admin/orders/{order_id}/notify-whatsapp")
def admin_notify_order_customer_whatsapp(
    order_id: int,
    payload: OrderWhatsappNotifyInput,
    admin: dict = Depends(require_permission("orders:write")),
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        ord_row = cur.fetchone()
        if not ord_row:
            raise HTTPException(status_code=404, detail="Order not found")
        od = dict(ord_row)
        receipt = dispatch_customer_whatsapp_order_update(
            od,
            template_type=payload.template_type,
            custom_message=payload.custom_message,
        )
        log_audit(
            conn,
            int(admin["sub"]),
            "notify_customer_whatsapp",
            "order",
            str(order_id),
            {
                "order_reference": od["order_reference"],
                "template_type": payload.template_type,
                "recipient_e164": receipt["recipient_e164"],
                "message_id": receipt["message_id"],
            },
        )
        return receipt


@app.get("/api/v1/admin/communications/outbox")
def admin_list_communications_outbox(
    limit: int = Query(30, ge=1, le=100),
    admin: dict = Depends(require_permission("orders:write")),
):
    cfg = get_whatsapp_config()
    items = list_recent_whatsapp_outbox(limit=limit)
    return {
        "items": items,
        "count": len(items),
        "whatsapp_configured": cfg["is_configured"],
        "sandbox_mode": cfg["sandbox_mode"],
        "boutique_whatsapp_e164": "+213655534154",
        "boutique_whatsapp_local": "0655534154",
    }


@app.get("/api/v1/ready")
def api_readiness_check():
    try:
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM delivery_zones WHERE is_active = 1")
            w_cnt = int(cur.fetchone()["cnt"])
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE deleted_at IS NULL")
            p_cnt = int(cur.fetchone()["cnt"])
        storage_ok = os.path.isdir(UPLOAD_STORAGE_DIR) and os.access(UPLOAD_STORAGE_DIR, os.W_OK)
        return {
            "ready": w_cnt == 69 and storage_ok,
            "status": "ready" if (w_cnt == 69 and storage_ok) else "degraded",
            "database": "connected",
            "storage_writable": storage_ok,
            "active_wilayas": w_cnt,
            "catalog_products": p_cnt,
            "timestamp": int(time.time()),
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/api/v1/admin/audit-logs")
def admin_list_audit_logs(
    limit: int = Query(40, ge=1, le=200),
    action_filter: Optional[str] = Query(None, alias="action"),
    admin: dict = Depends(require_permission("settings:write")),
):
    with db_session() as conn:
        cur = conn.cursor()
        if action_filter:
            cur.execute(
                """SELECT al.*, au.email AS admin_email, au.full_name AS admin_name
                   FROM audit_logs al
                   LEFT JOIN admin_users au ON au.id = al.admin_user_id
                   WHERE al.action = ?
                   ORDER BY al.id DESC LIMIT ?""",
                (action_filter.strip(), limit),
            )
        else:
            cur.execute(
                """SELECT al.*, au.email AS admin_email, au.full_name AS admin_name
                   FROM audit_logs al
                   LEFT JOIN admin_users au ON au.id = al.admin_user_id
                   ORDER BY al.id DESC LIMIT ?""",
                (limit,),
            )
        items = []
        for r in cur.fetchall():
            d = dict(r)
            try:
                d["details"] = json.loads(d.pop("details_json") or "{}")
            except Exception:
                d["details"] = {}
            items.append(d)
        return {"items": items, "count": len(items)}
# ============================================================================
# ERP MODULES: PURCHASING, SUPPLIERS, EXPENSES, TREASURY & ACCOUNTING LEDGER
# ============================================================================

class SupplierCreateInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None

class SupplierUpdateInput(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class PurchaseOrderItemInput(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(..., gt=0)
    unit_cost_dzd: int = Field(..., ge=0)

class PurchaseOrderCreateInput(BaseModel):
    supplier_id: int
    shipping_dzd: int = Field(0, ge=0)
    tax_dzd: int = Field(0, ge=0)
    expected_date: Optional[str] = None
    notes: Optional[str] = None
    items: List[PurchaseOrderItemInput]

class ExpenseCreateInput(BaseModel):
    description: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., min_length=2, max_length=64)
    amount_dzd: int = Field(..., gt=0)
    expense_date: Optional[str] = None
    payment_method: str = Field("cash", regex=r"^(cash|bank_transfer|check|card)$")
    recipient: Optional[str] = None
    receipt_reference: Optional[str] = None
    payment_status: str = Field("paid", regex=r"^(paid|pending)$")
    notes: Optional[str] = None

class CashMovementCreateInput(BaseModel):
    account_type: str = Field("cash_box", regex=r"^(cash_box|bank_account)$")
    movement_type: str = Field(..., regex=r"^(inflow|outflow|deposit|withdrawal)$")
    amount_dzd: int = Field(..., gt=0)
    description: str = Field(..., min_length=3, max_length=255)
    source_reference: Optional[str] = None


# --- SUPPLIER ENDPOINTS ---

@app.get("/api/v1/admin/suppliers")
def admin_list_suppliers(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers ORDER BY id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.post("/api/v1/admin/suppliers", status_code=201)
def admin_create_supplier(
    payload: SupplierCreateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO suppliers (name, company_name, contact_person, phone, email, address, tax_id, notes, balance_dzd, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)""",
            (
                payload.name.strip(),
                (payload.company_name or "").strip() or None,
                (payload.contact_person or "").strip() or None,
                (payload.phone or "").strip() or None,
                (payload.email or "").strip().lower() or None,
                (payload.address or "").strip() or None,
                (payload.tax_id or "").strip() or None,
                (payload.notes or "").strip() or None,
            )
        )
        sup_id = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_supplier", "supplier", str(sup_id), {"name": payload.name})
        cur.execute("SELECT * FROM suppliers WHERE id = ?", (sup_id,))
        return dict(cur.fetchone())

@app.put("/api/v1/admin/suppliers/{supplier_id}")
def admin_update_supplier(
    supplier_id: int,
    payload: SupplierUpdateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        sup = cur.fetchone()
        if not sup:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        cur.execute(
            """UPDATE suppliers
               SET name = COALESCE(?, name),
                   company_name = COALESCE(?, company_name),
                   contact_person = COALESCE(?, contact_person),
                   phone = COALESCE(?, phone),
                   email = COALESCE(?, email),
                   address = COALESCE(?, address),
                   tax_id = COALESCE(?, tax_id),
                   notes = COALESCE(?, notes),
                   is_active = COALESCE(?, is_active),
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                payload.name.strip() if payload.name else None,
                payload.company_name.strip() if payload.company_name else None,
                payload.contact_person.strip() if payload.contact_person else None,
                payload.phone.strip() if payload.phone else None,
                payload.email.strip().lower() if payload.email else None,
                payload.address.strip() if payload.address else None,
                payload.tax_id.strip() if payload.tax_id else None,
                payload.notes.strip() if payload.notes else None,
                (1 if payload.is_active else 0) if payload.is_active is not None else None,
                supplier_id,
            )
        )
        cur.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        return dict(cur.fetchone())

@app.delete("/api/v1/admin/suppliers/{supplier_id}")
def admin_delete_supplier(
    supplier_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        cur.execute("SELECT COUNT(*) AS cnt FROM purchase_orders WHERE supplier_id = ?", (supplier_id,))
        if cur.fetchone()["cnt"] > 0:
            cur.execute("UPDATE suppliers SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (supplier_id,))
            return {"archived": True, "message": "Fournisseur archivé car des bons de commande y sont rattachés"}
        cur.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        return {"deleted": True, "supplier_id": supplier_id}


# --- PURCHASING & PURCHASE ORDERS ENDPOINTS ---

@app.get("/api/v1/admin/purchases")
def admin_list_purchases(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT po.*, s.name AS supplier_name, s.phone AS supplier_phone, s.company_name AS supplier_company
               FROM purchase_orders po
               JOIN suppliers s ON s.id = po.supplier_id
               ORDER BY po.id DESC"""
        )
        pos = []
        for r in cur.fetchall():
            d = dict(r)
            cur.execute("SELECT * FROM purchase_order_items WHERE purchase_order_id = ?", (d["id"],))
            d["items"] = [dict(it) for it in cur.fetchall()]
            pos.append(d)
        return {"items": pos}

@app.post("/api/v1/admin/purchases", status_code=201)
def admin_create_purchase_order(
    payload: PurchaseOrderCreateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Au moins un article d'approvisionnement est requis")

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers WHERE id = ? AND is_active = 1", (payload.supplier_id,))
        sup = cur.fetchone()
        if not sup:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable ou inactif")

        # Generate unique reference e.g. ACH-2026-0001
        ref = f"ACH-{int(time.time())}-{secrets.token_hex(2).upper()}"
        subtotal = 0
        enriched_items = []
        for it in payload.items:
            cur.execute("SELECT * FROM products WHERE id = ?", (it.product_id,))
            p = cur.fetchone()
            if not p:
                raise HTTPException(status_code=400, detail=f"Produit ID {it.product_id} introuvable")
            variant_title = "Standard"
            sku = p["sku"]
            if it.variant_id:
                cur.execute("SELECT * FROM product_variants WHERE id = ?", (it.variant_id,))
                v = cur.fetchone()
                if v:
                    variant_title = v["title"]
                    sku = v["sku"]
            line_tot = it.quantity * it.unit_cost_dzd
            subtotal += line_tot
            enriched_items.append({
                "product_id": it.product_id,
                "variant_id": it.variant_id,
                "product_name": p["name_fr"],
                "variant_title": variant_title,
                "sku": sku,
                "quantity_ordered": it.quantity,
                "unit_cost_dzd": it.unit_cost_dzd,
                "line_total_dzd": line_tot,
            })

        total_cost = subtotal + payload.shipping_dzd + payload.tax_dzd
        cur.execute(
            """INSERT INTO purchase_orders (supplier_id, reference, status, subtotal_dzd, shipping_dzd, tax_dzd, total_cost_dzd, payment_status, paid_amount_dzd, expected_date, notes, created_by)
               VALUES (?, ?, 'ordered', ?, ?, ?, ?, 'unpaid', 0, ?, ?, ?)""",
            (
                payload.supplier_id,
                ref,
                subtotal,
                payload.shipping_dzd,
                payload.tax_dzd,
                total_cost,
                payload.expected_date,
                payload.notes,
                int(admin["sub"]),
            )
        )
        po_id = cur.lastrowid

        for e_it in enriched_items:
            cur.execute(
                """INSERT INTO purchase_order_items (purchase_order_id, product_id, variant_id, product_name, variant_title, sku, quantity_ordered, quantity_received, unit_cost_dzd, line_total_dzd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    po_id,
                    e_it["product_id"],
                    e_it["variant_id"],
                    e_it["product_name"],
                    e_it["variant_title"],
                    e_it["sku"],
                    e_it["quantity_ordered"],
                    e_it["unit_cost_dzd"],
                    e_it["line_total_dzd"],
                )
            )

        log_audit(conn, int(admin["sub"]), "create_purchase_order", "purchase_order", str(po_id), {
            "reference": ref,
            "total_cost_dzd": total_cost,
            "supplier_id": payload.supplier_id
        })
        cur.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
        result = dict(cur.fetchone())
        result["items"] = enriched_items
        return result

@app.post("/api/v1/admin/purchases/{po_id}/receive")
def admin_receive_purchase_order(
    po_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    """
    Records arrival of purchased goods:
    1. Increments variant inventory.
    2. Logs inventory movement.
    3. Recomputes Weighted Average Cost (PMP) for products.
    4. Updates supplier balance liability.
    5. Posts balanced double-entry accounting ledger: Debit 3000 (Stock) / Credit 4010 (Fournisseurs).
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
        po = cur.fetchone()
        if not po:
            raise HTTPException(status_code=404, detail="Bon de commande introuvable")
        if po["status"] == "received":
            raise HTTPException(status_code=400, detail="Ce bon de commande a déjà été réceptionné en stock")

        cur.execute("SELECT * FROM purchase_order_items WHERE purchase_order_id = ?", (po_id,))
        items = [dict(it) for it in cur.fetchall()]

        today_str = datetime.now().strftime("%Y-%m-%d")
        for it in items:
            v_id = it["variant_id"]
            if not v_id:
                cur.execute("SELECT id, stock_qty FROM product_variants WHERE product_id = ? LIMIT 1", (it["product_id"],))
                v_row = cur.fetchone()
                v_id = v_row["id"] if v_row else None
            else:
                cur.execute("SELECT id, stock_qty FROM product_variants WHERE id = ?", (v_id,))
                v_row = cur.fetchone()

            if v_row:
                old_stock = int(v_row["stock_qty"])
                new_stock = old_stock + it["quantity_ordered"]
                cur.execute("UPDATE product_variants SET stock_qty = ? WHERE id = ?", (new_stock, v_row["id"]))
                cur.execute(
                    """INSERT INTO inventory_movements (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (v_row["id"], int(admin["sub"]), it["quantity_ordered"], old_stock, new_stock, f"Réception fournisseur {po['reference']}")
                )

            # Update Product Cost using Weighted Average Cost (PMP)
            cur.execute("SELECT purchase_cost_dzd FROM products WHERE id = ?", (it["product_id"],))
            p_cost_row = cur.fetchone()
            curr_cost = int(p_cost_row["purchase_cost_dzd"]) if p_cost_row and p_cost_row["purchase_cost_dzd"] else it["unit_cost_dzd"]
            cur.execute("SELECT COALESCE(SUM(stock_qty), 0) AS total_stk FROM product_variants WHERE product_id = ?", (it["product_id"],))
            total_stk = int(cur.fetchone()["total_stk"])
            # Weighted average formula
            if total_stk > 0:
                weighted_unit_cost = int(((total_stk - it["quantity_ordered"]) * curr_cost + it["quantity_ordered"] * it["unit_cost_dzd"]) / total_stk)
            else:
                weighted_unit_cost = it["unit_cost_dzd"]
            cur.execute("UPDATE products SET purchase_cost_dzd = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (weighted_unit_cost, it["product_id"]))
            cur.execute("UPDATE purchase_order_items SET quantity_received = quantity_ordered WHERE id = ?", (it["id"],))

        # Update purchase order status
        cur.execute("UPDATE purchase_orders SET status = 'received', received_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (po_id,))
        # Update supplier debt
        cur.execute("UPDATE suppliers SET balance_dzd = balance_dzd + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (po["total_cost_dzd"], po["supplier_id"]))

        # Double-entry ledger: Debit Stock 3000 / Credit Fournisseurs 4010
        cur.execute(
            """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
               VALUES (?, 'ACH', ?, '3000', 'Stocks de Marchandises', ?, ?, 0, ?)""",
            (f"ENTRY-{po['reference']}-D", today_str, f"Achats réceptionnés {po['reference']}", po["total_cost_dzd"], po["reference"])
        )
        cur.execute(
            """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
               VALUES (?, 'ACH', ?, '4010', 'Dettes Fournisseurs', ?, 0, ?, ?)""",
            (f"ENTRY-{po['reference']}-C", today_str, f"Facture fournisseur {po['reference']}", po["total_cost_dzd"], po["reference"])
        )

        log_audit(conn, int(admin["sub"]), "receive_purchase_order", "purchase_order", str(po_id), {
            "reference": po["reference"],
            "total_cost_dzd": po["total_cost_dzd"]
        })
        return {"received": True, "purchase_order_id": po_id, "status": "received"}

@app.post("/api/v1/admin/purchases/{po_id}/pay")
def admin_pay_purchase_order(
    po_id: int,
    payment_method: str = Query("cash", regex=r"^(cash|bank_transfer|check)$"),
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
        po = cur.fetchone()
        if not po:
            raise HTTPException(status_code=404, detail="Bon de commande introuvable")
        if po["payment_status"] == "paid":
            raise HTTPException(status_code=400, detail="Ce bon de commande est déjà payé")

        pay_amount = int(po["total_cost_dzd"]) - int(po["paid_amount_dzd"])
        cur.execute(
            "UPDATE purchase_orders SET payment_status = 'paid', paid_amount_dzd = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (po["total_cost_dzd"], po_id)
        )
        cur.execute(
            "UPDATE suppliers SET balance_dzd = balance_dzd - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (pay_amount, po["supplier_id"])
        )

        # Cash Movement (Outflow)
        acc_type = "bank_account" if payment_method == "bank_transfer" else "cash_box"
        cur.execute(
            """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
               VALUES (?, 'outflow', ?, 'purchase_payment', ?, ?, ?)""",
            (acc_type, pay_amount, po["reference"], f"Paiement fournisseur ({po['reference']})", int(admin["sub"]))
        )

        # Double-entry ledger: Debit 4010 (Fournisseurs) / Credit 5300 (Caisse) or 5120 (Banque)
        today_str = datetime.now().strftime("%Y-%m-%d")
        credit_acc = "5120" if payment_method == "bank_transfer" else "5300"
        credit_name = "Banque" if payment_method == "bank_transfer" else "Caisse Boutique"
        cur.execute(
            """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
               VALUES (?, 'CAI', ?, '4010', 'Dettes Fournisseurs', ?, ?, 0, ?)""",
            (f"PAY-{po['reference']}-D", today_str, f"Règlement fournisseur {po['reference']}", pay_amount, po["reference"])
        )
        cur.execute(
            """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
               VALUES (?, 'CAI', ?, ?, ?, ?, 0, ?, ?)""",
            (f"PAY-{po['reference']}-C", today_str, credit_acc, credit_name, f"Règlement fournisseur {po['reference']}", pay_amount, po["reference"])
        )

        return {"paid": True, "purchase_order_id": po_id, "paid_amount_dzd": pay_amount}


# --- OPERATING EXPENSES (DÉPENSES & FRAIS GÉNÉRAUX) ---

@app.get("/api/v1/admin/expenses")
def admin_list_expenses(
    category: Optional[str] = None,
    admin: dict = Depends(require_permission("dashboard:read"))
):
    with db_session() as conn:
        cur = conn.cursor()
        if category:
            cur.execute("SELECT * FROM expenses WHERE category = ? ORDER BY expense_date DESC, id DESC", (category,))
        else:
            cur.execute("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}

@app.post("/api/v1/admin/expenses", status_code=201)
def admin_create_expense(
    payload: ExpenseCreateInput,
    admin: dict = Depends(require_permission("settings:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        exp_date = payload.expense_date or datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            """INSERT INTO expenses (description, category, amount_dzd, expense_date, payment_method, recipient, receipt_reference, payment_status, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.description.strip(),
                payload.category.strip(),
                payload.amount_dzd,
                exp_date,
                payload.payment_method,
                (payload.recipient or "").strip() or None,
                (payload.receipt_reference or "").strip() or None,
                payload.payment_status,
                (payload.notes or "").strip() or None,
                int(admin["sub"]),
            )
        )
        exp_id = cur.lastrowid

        # If paid, immediately register cash outflow and ledger entry
        if payload.payment_status == "paid":
            acc_type = "bank_account" if payload.payment_method == "bank_transfer" else "cash_box"
            cur.execute(
                """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
                   VALUES (?, 'outflow', ?, 'expense_payment', ?, ?, ?)""",
                (acc_type, payload.amount_dzd, f"EXP-{exp_id}", f"Dépense: {payload.description}", int(admin["sub"]))
            )

            # Balanced Ledger: Debit 6100 (Charges d'exploitation) / Credit 5300 (Caisse)
            credit_acc = "5120" if payload.payment_method == "bank_transfer" else "5300"
            credit_name = "Banque" if payload.payment_method == "bank_transfer" else "Caisse Boutique"
            cur.execute(
                """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
                   VALUES (?, 'OD', ?, '6100', 'Charges et Dépenses d''Exploitation', ?, ?, 0, ?)""",
                (f"EXP-{exp_id}-D", exp_date, payload.description, payload.amount_dzd, f"EXP-{exp_id}")
            )
            cur.execute(
                """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
               VALUES (?, 'OD', ?, ?, ?, ?, 0, ?, ?)""",
                (f"EXP-{exp_id}-C", exp_date, credit_acc, credit_name, payload.description, payload.amount_dzd, f"EXP-{exp_id}")
            )

        log_audit(conn, int(admin["sub"]), "create_expense", "expense", str(exp_id), {
            "description": payload.description,
            "amount_dzd": payload.amount_dzd,
            "category": payload.category
        })
        cur.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,))
        return dict(cur.fetchone())

@app.delete("/api/v1/admin/expenses/{expense_id}")
def admin_delete_expense(
    expense_id: int,
    admin: dict = Depends(require_permission("settings:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        exp = cur.fetchone()
        if not exp:
            raise HTTPException(status_code=404, detail="Dépense introuvable")
        cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        log_audit(conn, int(admin["sub"]), "delete_expense", "expense", str(expense_id), {"description": exp["description"]})
        return {"deleted": True, "expense_id": expense_id}


# --- CASH REGISTER & TREASURY (CAISSE & TRÉSORERIE) ---

@app.get("/api/v1/admin/treasury/summary")
def admin_get_treasury_summary(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        # Inflows & Outflows for Cash Box
        cur.execute("SELECT COALESCE(SUM(amount_dzd), 0) AS s FROM cash_movements WHERE account_type = 'cash_box' AND movement_type IN ('inflow', 'deposit')")
        cash_in = int(cur.fetchone()["s"])
        cur.execute("SELECT COALESCE(SUM(amount_dzd), 0) AS s FROM cash_movements WHERE account_type = 'cash_box' AND movement_type IN ('outflow', 'withdrawal')")
        cash_out = int(cur.fetchone()["s"])
        cash_balance = cash_in - cash_out

        # Inflows & Outflows for Bank
        cur.execute("SELECT COALESCE(SUM(amount_dzd), 0) AS s FROM cash_movements WHERE account_type = 'bank_account' AND movement_type IN ('inflow', 'deposit')")
        bank_in = int(cur.fetchone()["s"])
        cur.execute("SELECT COALESCE(SUM(amount_dzd), 0) AS s FROM cash_movements WHERE account_type = 'bank_account' AND movement_type IN ('outflow', 'withdrawal')")
        bank_out = int(cur.fetchone()["s"])
        bank_balance = bank_in - bank_out

        # Pending COD Receivables (Orders Shipped / In Prep not yet marked Delivered)
        cur.execute("SELECT COALESCE(SUM(total_dzd), 0) AS s FROM orders WHERE status IN ('shipped', 'in_preparation', 'confirmed')")
        pending_cod = int(cur.fetchone()["s"])

        # Total Delivered Orders Cash Collected
        cur.execute("SELECT COALESCE(SUM(total_dzd), 0) AS s FROM orders WHERE status = 'delivered'")
        collected_orders_dzd = int(cur.fetchone()["s"])

        # Total Supplier Debts
        cur.execute("SELECT COALESCE(SUM(balance_dzd), 0) AS s FROM suppliers")
        supplier_debts = int(cur.fetchone()["s"])

        # Inventory Value at Purchase Cost
        cur.execute(
            """SELECT COALESCE(SUM(pv.stock_qty * COALESCE(p.purchase_cost_dzd, 0)), 0) AS s
               FROM product_variants pv
               JOIN products p ON p.id = pv.product_id
               WHERE p.deleted_at IS NULL"""
        )
        inventory_valuation = int(cur.fetchone()["s"])

        return {
            "cash_balance_dzd": cash_balance,
            "bank_balance_dzd": bank_balance,
            "total_liquid_treasury_dzd": cash_balance + bank_balance,
            "total_liquidity_dzd": cash_balance + bank_balance,
            "pending_cod_receivables_dzd": pending_cod,
            "pending_cod_collections_dzd": pending_cod,
            "collected_orders_total_dzd": collected_orders_dzd,
            "supplier_debts_dzd": supplier_debts,
            "inventory_valuation_dzd": inventory_valuation,
        }

@app.get("/api/v1/admin/treasury/movements")
def admin_list_cash_movements(
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(require_permission("dashboard:read"))
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cash_movements ORDER BY id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        cash_bal = 0
        bank_bal = 0
        for m in rows:
            amt = int(m.get("amount_dzd") or 0)
            if m.get("movement_type") == "outflow":
                amt = -amt
            if m.get("account_type") == "bank_account":
                bank_bal += amt
                m["balance_after_dzd"] = bank_bal
            else:
                cash_bal += amt
                m["balance_after_dzd"] = cash_bal
        rows.reverse()
        return {"items": rows[:limit]}

@app.post("/api/v1/admin/treasury/movements", status_code=201)
def admin_record_cash_movement(
    payload: CashMovementCreateInput,
    admin: dict = Depends(require_permission("settings:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
               VALUES (?, ?, ?, 'manual_adjustment', ?, ?, ?)""",
            (
                payload.account_type,
                payload.movement_type,
                payload.amount_dzd,
                payload.source_reference,
                payload.description.strip(),
                int(admin["sub"]),
            )
        )
        mov_id = cur.lastrowid
        return {"created": True, "movement_id": mov_id}


# --- COMPTABILITÉ & CALCUL DES BÉNÉFICES (P&L, MARGINS & LEDGER) ---

@app.get("/api/v1/admin/accounting/pnl")
def admin_get_pnl_statement(admin: dict = Depends(require_permission("dashboard:read"))):
    """
    Authoritative Financial Statement (Compte de Résultat & Analyse des Marges):
    1. Chiffre d'Affaires Brut (Sales Revenue).
    2. Frais de port collectés.
    3. Coût d'Achat des Marchandises Vendues (COGS).
    4. Marge Brute Réalisée (Gross Profit = Ventes - Coût Achat).
    5. Taux de Marge Brute (%).
    6. Dépenses d'Exploitation (Loyer, Salaires, Pub, Packaging).
    7. Résultat Net d'Exploitation (Net Profit = Marge Brute - Dépenses).
    8. Taux de Marge Nette (%).
    """
    with db_session() as conn:
        cur = conn.cursor()
        # All orders non-cancelled
        cur.execute(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(subtotal_dzd), 0) AS subtotal_dzd,
                      COALESCE(SUM(delivery_fee_dzd), 0) AS delivery_fee_dzd,
                      COALESCE(SUM(total_dzd), 0) AS total_dzd
               FROM orders
               WHERE status != 'cancelled'"""
        )
        ord_stats = dict(cur.fetchone())

        # Delivered (Collected) Orders
        cur.execute(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(subtotal_dzd), 0) AS subtotal_dzd,
                      COALESCE(SUM(total_dzd), 0) AS total_dzd
               FROM orders
               WHERE status = 'delivered'"""
        )
        deliv_stats = dict(cur.fetchone())

        # Cost of Goods Sold (COGS) for all active orders
        cur.execute(
            """SELECT COALESCE(SUM(oi.quantity * COALESCE(p.purchase_cost_dzd, 0)), 0) AS cogs_total
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               JOIN products p ON p.id = oi.product_id
               WHERE o.status != 'cancelled'"""
        )
        cogs_all = int(cur.fetchone()["cogs_total"])

        # Cost of Goods Sold (COGS) for delivered orders only
        cur.execute(
            """SELECT COALESCE(SUM(oi.quantity * COALESCE(p.purchase_cost_dzd, 0)), 0) AS cogs_deliv
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               JOIN products p ON p.id = oi.product_id
               WHERE o.status = 'delivered'"""
        )
        cogs_delivered = int(cur.fetchone()["cogs_deliv"])

        # Total Operating Expenses
        cur.execute("SELECT COALESCE(SUM(amount_dzd), 0) AS s FROM expenses WHERE payment_status = 'paid'")
        total_expenses = int(cur.fetchone()["s"])

        # Expenses by category breakdown
        cur.execute("SELECT category, COALESCE(SUM(amount_dzd), 0) AS total_dzd, COUNT(*) AS count FROM expenses GROUP BY category")
        expenses_by_cat = [dict(r) for r in cur.fetchall()]

        # Financial Calculations (in DZD integers)
        subtotal = int(ord_stats["subtotal_dzd"])
        gross_profit_all = subtotal - cogs_all
        gross_margin_pct_all = round((gross_profit_all / subtotal * 100), 1) if subtotal > 0 else 0.0

        subtotal_deliv = int(deliv_stats["subtotal_dzd"])
        gross_profit_delivered = subtotal_deliv - cogs_delivered
        gross_margin_pct_deliv = round((gross_profit_delivered / subtotal_deliv * 100), 1) if subtotal_deliv > 0 else 0.0

        net_profit_all = gross_profit_all - total_expenses
        net_margin_pct_all = round((net_profit_all / subtotal * 100), 1) if subtotal > 0 else 0.0

        net_profit_delivered = gross_profit_delivered - total_expenses

        # Count total units sold across non-cancelled orders
        cur.execute(
            """SELECT COALESCE(SUM(oi.quantity), 0) AS total_units
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.status != 'cancelled'"""
        )
        total_units_sold = int(cur.fetchone()["total_units"])

        # Current total inventory valuation
        cur.execute(
            """SELECT COALESCE(SUM(pv.stock_qty * COALESCE(p.purchase_cost_dzd, 0)), 0) AS total_val
               FROM product_variants pv
               JOIN products p ON p.id = pv.product_id"""
        )
        inv_val = int(cur.fetchone()["total_val"])

        return {
            "gross_revenue_dzd": subtotal,
            "delivery_revenue_dzd": int(ord_stats["delivery_fee_dzd"]),
            "total_revenue_dzd": int(ord_stats["total_dzd"]),
            "cogs_dzd": cogs_all,
            "gross_profit_dzd": gross_profit_all,
            "gross_margin_percent": gross_margin_pct_all,
            "operating_expenses_dzd": total_expenses,
            "net_operating_profit_dzd": net_profit_all,
            "net_margin_percent": net_margin_pct_all,
            "orders_count": int(ord_stats["count"]),
            "units_sold": total_units_sold,
            "inventory_valuation_dzd": inv_val,
            "revenue": {
                "total_sales_dzd": int(ord_stats["total_dzd"]),
                "subtotal_merchandise_dzd": subtotal,
                "delivery_fees_dzd": int(ord_stats["delivery_fee_dzd"]),
                "orders_count": int(ord_stats["count"]),
                "delivered_sales_dzd": int(deliv_stats["total_dzd"]),
                "delivered_subtotal_dzd": subtotal_deliv,
                "delivered_orders_count": int(deliv_stats["count"]),
            },
            "cogs": {
                "cogs_all_orders_dzd": cogs_all,
                "cogs_delivered_orders_dzd": cogs_delivered,
            },
            "margins": {
                "gross_profit_all_dzd": gross_profit_all,
                "gross_margin_pct_all": gross_margin_pct_all,
                "gross_profit_delivered_dzd": gross_profit_delivered,
                "gross_margin_pct_delivered": gross_margin_pct_deliv,
            },
            "operating_expenses": {
                "total_expenses_dzd": total_expenses,
                "breakdown_by_category": expenses_by_cat,
            },
            "net_results": {
                "net_profit_all_dzd": net_profit_all,
                "net_margin_pct_all": net_margin_pct_all,
                "net_profit_delivered_dzd": net_profit_delivered,
            }
        }

@app.get("/api/v1/admin/accounting/products-profitability")
def admin_get_products_profitability(
    include_archived: bool = Query(True),
    admin: dict = Depends(require_permission("dashboard:read"))
):
    """
    Returns unit margins, markups, total sales and total profits generated by each product.
    """
    with db_session() as conn:
        cur = conn.cursor()
        where_clause = "" if include_archived else "WHERE p.deleted_at IS NULL"
        cur.execute(
            f"""SELECT p.id, p.sku, p.name_fr, p.selling_price_dzd,
                      COALESCE(p.purchase_cost_dzd, 0) AS purchase_cost_dzd,
                      p.status,
                      COALESCE(SUM(oi.quantity), 0) AS units_sold,
                      COALESCE(SUM(oi.line_total_dzd), 0) AS total_revenue_dzd
               FROM products p
               LEFT JOIN order_items oi ON oi.product_id = p.id
               {where_clause}
               GROUP BY p.id
               ORDER BY total_revenue_dzd DESC, p.id ASC"""
        )
        items = []
        for r in cur.fetchall():
            d = dict(r)
            sell = int(d["selling_price_dzd"])
            cost = int(d["purchase_cost_dzd"])
            unit_profit = sell - cost
            gross_margin_pct = round((unit_profit / sell * 100), 1) if sell > 0 else 0.0
            markup_pct = round((unit_profit / cost * 100), 1) if cost > 0 else 0.0
            total_cost_sold = cost * int(d["units_sold"])
            total_profit = int(d["total_revenue_dzd"]) - total_cost_sold
            d["unit_profit_dzd"] = unit_profit
            d["gross_margin_pct"] = gross_margin_pct
            d["markup_pct"] = markup_pct
            d["total_cost_sold_dzd"] = total_cost_sold
            d["total_profit_dzd"] = total_profit
            items.append(d)
        return {"items": items}

@app.get("/api/v1/admin/accounting/ledger")
def admin_list_accounting_ledger(
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(require_permission("dashboard:read"))
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM accounting_ledger ORDER BY entry_date DESC, id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COALESCE(SUM(debit_dzd), 0) AS deb, COALESCE(SUM(credit_dzd), 0) AS cred FROM accounting_ledger")
        sums = cur.fetchone()
        return {
            "items": rows,
            "entries": rows,
            "total_debit_dzd": int(sums["deb"]),
            "total_debits_dzd": int(sums["deb"]),
            "total_credit_dzd": int(sums["cred"]),
            "total_credits_dzd": int(sums["cred"]),
            "is_balanced": int(sums["deb"]) == int(sums["cred"]),
            "entries_count": len(rows),
        }

