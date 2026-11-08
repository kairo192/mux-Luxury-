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

from starlette.middleware.gzip import GZipMiddleware

# High-Performance HTTP Response Compression (brotli/gzip for JSON payloads > 1000 bytes)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "ETag", "Cache-Control"],
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

def require_any_permission(perms: List[str]):
    def dep(admin: dict = Depends(get_current_admin)) -> dict:
        granted = admin.get("perms", [])
        if not any(p in granted for p in perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: one of {perms} required"
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
    category_id: Optional[int] = None
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
    banner_url: Optional[str] = "/assets/hero_bag_clean.jpg"
    parent_id: Optional[int] = None
    display_order: int = 10
    is_active: bool = True
    show_on_homepage: bool = True
    attributes: List[CategoryAttributeCreate] = []

class VariantInput(BaseModel):
    sku: str
    barcode: Optional[str] = None
    title: str
    price_override_dzd: Optional[int] = Field(None, ge=0)
    stock_qty: int = Field(0, ge=0)
    image_url: Optional[str] = None
    purchase_cost_dzd: Optional[int] = Field(None, ge=0)
    weight_grams: Optional[int] = Field(None, ge=0)
    low_stock_threshold: int = Field(3, ge=0)
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
    description_ar: Optional[str] = ""
    description_en: Optional[str] = ""
    main_image_url: Optional[str] = "/assets/prod_sac_chanel_hd.jpg"
    purchase_cost_dzd: int = Field(0, ge=0)
    selling_price_dzd: int = Field(..., ge=0)
    previous_price_dzd: Optional[int] = Field(None, ge=0)
    discount_percent: int = Field(0, ge=0, le=95)
    status: str = Field("draft", regex=r"^(draft|published|archived)$")
    is_featured: bool = False
    is_new_arrival: bool = False
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    weight_grams: Optional[int] = Field(None, ge=0)
    dimensions_cm: Optional[str] = None
    tags: Optional[str] = None
    dynamic_attributes: Dict[str, Any] = {}
    variants: List[VariantInput] = []

class VariantMatrixRequest(BaseModel):
    axes: Dict[str, List[str]] # e.g. {"color": ["Noir", "Blanc"], "size": ["40", "41"]}
    default_stock: int = Field(3, ge=0)
    price_override_dzd: Optional[int] = Field(None, ge=0)
    low_stock_threshold: int = Field(3, ge=0)

class VariantCreateInput(BaseModel):
    sku: Optional[str] = None
    barcode: Optional[str] = None
    title: Optional[str] = None
    price_override_dzd: Optional[int] = Field(None, ge=0)
    stock_qty: int = Field(0, ge=0)
    image_url: Optional[str] = None
    purchase_cost_dzd: Optional[int] = Field(None, ge=0)
    weight_grams: Optional[int] = Field(None, ge=0)
    low_stock_threshold: int = Field(3, ge=0)
    is_active: bool = True
    attributes: Dict[str, str] = {}

class VariantUpdateInput(BaseModel):
    sku: Optional[str] = None
    barcode: Optional[str] = None
    title: Optional[str] = None
    price_override_dzd: Optional[int] = Field(None, ge=0)
    clear_price_override: bool = False
    stock_qty: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = None
    purchase_cost_dzd: Optional[int] = Field(None, ge=0)
    weight_grams: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    attributes: Optional[Dict[str, str]] = None

class VariantBulkUpdateInput(BaseModel):
    variant_ids: List[int] = Field(..., min_items=1, max_items=500)
    set_stock_qty: Optional[int] = Field(None, ge=0)
    adjust_stock_qty: Optional[int] = None
    set_price_override_dzd: Optional[int] = Field(None, ge=0)
    clear_price_override: bool = False
    is_active: Optional[bool] = None
    reason: str = Field("cms_bulk_update", min_length=3, max_length=120)

class CategoryAttributeUpdate(BaseModel):
    label_fr: Optional[str] = None
    label_ar: Optional[str] = None
    label_en: Optional[str] = None
    input_type: Optional[str] = None
    unit: Optional[str] = None
    is_required: Optional[bool] = None
    default_value: Optional[str] = None
    allow_multiple: Optional[bool] = None
    is_visible_on_storefront: Optional[bool] = None
    is_filterable: Optional[bool] = None
    is_variant_axis: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)

    @validator("input_type")
    def validate_optional_input_type(cls, v):
        if v is not None and v not in SUPPORTED_ATTRIBUTE_TYPES:
            raise ValueError(f"Unsupported input_type '{v}'. Allowed: {SUPPORTED_ATTRIBUTE_TYPES}")
        return v

class AttributeOptionUpsert(BaseModel):
    value: str = Field(..., min_length=1, max_length=140)
    label_fr: Optional[str] = None
    label_ar: Optional[str] = ""
    label_en: Optional[str] = ""
    color_hex: Optional[str] = Field(None, regex=r"^#[0-9a-fA-F]{6}$")
    display_order: int = Field(1, ge=0)

class CategoryReorderInput(BaseModel):
    items: List[Dict[str, int]] = Field(..., min_items=1, max_items=300)


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
            "SELECT id, value, label_fr, label_ar, label_en, color_hex, display_order FROM category_attribute_options WHERE attribute_id = ? ORDER BY display_order ASC",
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

def serialize_products_batch(conn, product_rows: List[dict], include_private: bool = False) -> List[dict]:
    """
    High-Performance Batch Product Serializer:
    Eliminates the N+1 query problem by fetching brands, categories, attribute values,
    variants, and images in 6 batched queries total instead of 12+ queries per product.
    """
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
        f"""SELECT pav.product_id, ca.attr_key, pav.value_text
            FROM product_attribute_values pav
            JOIN category_attributes ca ON ca.id = pav.attribute_id
            WHERE pav.product_id IN ({placeholders_p}) AND (? = 1 OR ca.is_visible_on_storefront = 1)
            ORDER BY ca.display_order ASC""",
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
            f"""SELECT vav.variant_id, ca.attr_key, vav.option_value
                FROM variant_attribute_values vav
                JOIN category_attributes ca ON ca.id = vav.attribute_id
                WHERE vav.variant_id IN ({placeholders_v})""",
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
            v["is_active"] = bool(v.get("is_active", 1))
            threshold = v.get("low_stock_threshold")
            v["is_low_stock"] = int(v["stock_qty"]) <= int(threshold if threshold is not None else 3)
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
    return res[0] if res else dict(row)

# --- Variant + attribute validation helpers (shared by all variant mutation endpoints) ---

def normalize_variant_sku(value: Optional[str]) -> str:
    return re.sub(r"\s+", "-", str(value or "").strip())

def build_variant_signature(attributes: Dict[str, str], sku_fallback: str = "") -> str:
    if attributes:
        return "|".join(f"{k}:{attributes[k]}" for k in sorted(attributes.keys()))
    return f"sku:{sku_fallback}"

def load_category_attributes_with_options(conn, category_id: int) -> Dict[str, dict]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (category_id,))
    attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}
    if not attrs:
        return attrs
    attr_ids = [a["id"] for a in attrs.values()]
    placeholders = ",".join("?" for _ in attr_ids)
    cur.execute(
        f"SELECT attribute_id, value FROM category_attribute_options WHERE attribute_id IN ({placeholders})",
        attr_ids,
    )
    options_by_attr: Dict[int, set] = {}
    for row in cur.fetchall():
        options_by_attr.setdefault(row["attribute_id"], set()).add(str(row["value"]).strip())
    for attr in attrs.values():
        attr["option_values"] = options_by_attr.get(attr["id"], set())
    return attrs

def validate_variant_attributes(
    cat_attrs: Dict[str, dict],
    attributes: Dict[str, str],
    allow_empty: bool = True,
    allow_custom_values: bool = False,
) -> Dict[str, str]:
    """
    Rejects unknown attributes, non-axis attributes and (unless custom values are allowed)
    option values that do not belong to the category definition. Returns the trimmed map.
    """
    axes = {k: a for k, a in cat_attrs.items() if a.get("is_variant_axis")}
    cleaned: Dict[str, str] = {}
    for raw_key, raw_val in (attributes or {}).items():
        key = str(raw_key).strip()
        if key not in cat_attrs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown attribute '{key}' for this category",
            )
        if key not in axes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Attribute '{key}' is not configured as a variant axis for this category",
            )
        val = str(raw_val).strip()
        if not val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Empty value for variant attribute '{key}'",
            )
        allowed = cat_attrs[key].get("option_values") or set()
        if allowed and val not in allowed and not allow_custom_values:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid value '{val}' for attribute '{key}'. Allowed values: {', '.join(sorted(allowed))}",
            )
        cleaned[key] = val
    if not cleaned and axes and not allow_empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one variant attribute value is required for this category",
        )
    return cleaned

def ensure_variant_attribute_options(conn, cat_attrs: Dict[str, dict], attributes: Dict[str, str]) -> None:
    """
    Registers a custom axis value as a reusable option so dropdowns, filters and the CMS
    stay consistent. Existing options are untouched.
    """
    cur = conn.cursor()
    for key, val in attributes.items():
        attr = cat_attrs.get(key)
        if not attr:
            continue
        allowed = attr.get("option_values") or set()
        if val in allowed:
            continue
        cur.execute(
            "SELECT COALESCE(MAX(display_order), 0) AS mx FROM category_attribute_options WHERE attribute_id = ?",
            (attr["id"],),
        )
        next_order = int(cur.fetchone()["mx"] or 0) + 1
        cur.execute(
            """INSERT INTO category_attribute_options
               (attribute_id, value, label_fr, label_ar, label_en, display_order)
               VALUES (?, ?, ?, '', '', ?)""",
            (attr["id"], val, val, next_order),
        )
        allowed.add(val)
        attr["option_values"] = allowed

def assert_variant_sku_available(conn, sku: str, exclude_variant_id: Optional[int] = None) -> None:
    if not sku:
        raise HTTPException(status_code=422, detail="Variant SKU cannot be empty")
    cur = conn.cursor()
    if exclude_variant_id is None:
        cur.execute("SELECT id FROM product_variants WHERE sku = ?", (sku,))
    else:
        cur.execute("SELECT id FROM product_variants WHERE sku = ? AND id != ?", (sku, exclude_variant_id))
    if cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Variant SKU '{sku}' already exists",
        )

def assert_variant_signature_available(
    conn,
    product_id: int,
    signature: str,
    exclude_variant_id: Optional[int] = None,
) -> None:
    cur = conn.cursor()
    if exclude_variant_id is None:
        cur.execute(
            "SELECT id FROM product_variants WHERE product_id = ? AND combination_signature = ?",
            (product_id, signature),
        )
    else:
        cur.execute(
            "SELECT id FROM product_variants WHERE product_id = ? AND combination_signature = ? AND id != ?",
            (product_id, signature, exclude_variant_id),
        )
    if cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A variant with this color/size/attribute combination already exists for this product",
        )

def replace_variant_attribute_values(conn, variant_id: int, cat_attrs: Dict[str, dict], attributes: Dict[str, str]) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM variant_attribute_values WHERE variant_id = ?", (variant_id,))
    for key, val in attributes.items():
        cur.execute(
            "INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)",
            (variant_id, cat_attrs[key]["id"], val),
        )

def auto_variant_sku(conn, product_sku: str, attributes: Dict[str, str], signature: str) -> str:
    if attributes:
        parts = [re.sub(r"[^A-Z0-9]", "", str(attributes[k]).upper())[:4] for k in sorted(attributes)]
        base = f"{product_sku}-{'-'.join(parts)}"
    else:
        base = f"{product_sku}-STD"
    cur = conn.cursor()
    cur.execute("SELECT id FROM product_variants WHERE sku = ?", (base,))
    if cur.fetchone():
        base = f"{base}-{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:4].upper()}"
    return base

def serialize_variant_row(conn, variant_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """SELECT pv.*, p.selling_price_dzd, p.sku AS product_sku
           FROM product_variants pv
           JOIN products p ON p.id = pv.product_id
           WHERE pv.id = ?""",
        (variant_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Variant not found")
    out = dict(row)
    cur.execute(
        """SELECT ca.attr_key, vav.option_value
           FROM variant_attribute_values vav
           JOIN category_attributes ca ON ca.id = vav.attribute_id
           WHERE vav.variant_id = ?""",
        (variant_id,),
    )
    out["attributes"] = {r["attr_key"]: r["option_value"] for r in cur.fetchall()}
    out["effective_price_dzd"] = (
        out["price_override_dzd"] if out["price_override_dzd"] is not None else out["selling_price_dzd"]
    )
    out["is_active"] = bool(out["is_active"])
    threshold = out.get("low_stock_threshold")
    out["is_low_stock"] = int(out["stock_qty"]) <= int(threshold if threshold is not None else 3)
    return out

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
        return payload

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
        return payload

@app.get("/api/v1/products")
def list_public_products(
    request: Request,
    response: Response,
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
        items = serialize_products_batch(conn, cur.fetchall(), include_private=False)
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
        return serialize_category(conn, dict(cur.fetchone()))

@app.post("/api/v1/admin/category-attributes", status_code=201)
def add_category_attribute(
    payload: CategoryAttributeCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    if not payload.category_id:
        raise HTTPException(status_code=400, detail="category_id is required")
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
            cur.execute("SELECT DISTINCT variant_id FROM variant_attribute_values WHERE attribute_id = ?", (attr_id,))
            affected_variants = [r["variant_id"] for r in cur.fetchall()]
            cur.execute("DELETE FROM product_attribute_values WHERE attribute_id = ?", (attr_id,))
            cur.execute("DELETE FROM variant_attribute_values WHERE attribute_id = ?", (attr_id,))
            # Variant combination signatures are derived from the remaining axes.
            for variant_id in affected_variants:
                try:
                    recompute_variant_signature(conn, variant_id)
                except Exception:
                    pass

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

        # Validate every variant (axis membership + option values) and catch duplicates
        # inside the same payload before touching the database, so clients get a clean 409/422.
        cat_attrs_full = load_category_attributes_with_options(conn, payload.category_id)
        validated_variants = []
        seen_skus = set()
        seen_signatures = set()
        for v in payload.variants:
            v_sku = normalize_variant_sku(v.sku)
            if not v_sku:
                raise HTTPException(status_code=422, detail="Variant SKU cannot be empty")
            if v_sku in seen_skus:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Duplicate variant SKU '{v_sku}' in payload")
            seen_skus.add(v_sku)
            v_attrs = validate_variant_attributes(cat_attrs_full, v.attributes, allow_custom_values=True)
            ensure_variant_attribute_options(conn, cat_attrs_full, v_attrs)
            sig = build_variant_signature(v_attrs, v_sku)
            if sig in seen_signatures:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate variant combination in payload")
            seen_signatures.add(sig)
            assert_variant_sku_available(conn, v_sku)
            validated_variants.append((v, v_sku, v_attrs, sig))

        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival, seo_title, seo_description,
                weight_grams, dimensions_cm, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.category_id, payload.brand_id, payload.slug, payload.sku, payload.barcode,
                payload.name_fr, payload.name_ar, payload.name_en, payload.description_fr,
                payload.description_ar, payload.description_en, payload.main_image_url,
                payload.purchase_cost_dzd, payload.selling_price_dzd,
                payload.previous_price_dzd, payload.discount_percent, payload.status,
                1 if payload.is_featured else 0, 1 if payload.is_new_arrival else 0,
                payload.seo_title, payload.seo_description,
                payload.weight_grams, payload.dimensions_cm, payload.tags
            )
        )
        prod_id = cur.lastrowid

        for akey, aval in payload.dynamic_attributes.items():
            if akey in cat_attrs:
                cur.execute(
                    "INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)",
                    (prod_id, cat_attrs[akey]["id"], str(aval))
                )

        for v, v_sku, v_attrs, sig in validated_variants:
            cur.execute(
                """INSERT INTO product_variants
                   (product_id, sku, barcode, title, price_override_dzd, stock_qty, image_url,
                    purchase_cost_dzd, weight_grams, low_stock_threshold, is_active, combination_signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prod_id, v_sku, v.barcode, v.title, v.price_override_dzd, v.stock_qty,
                    v.image_url or payload.main_image_url, v.purchase_cost_dzd, v.weight_grams,
                    v.low_stock_threshold, 1, sig,
                )
            )
            vid = cur.lastrowid
            replace_variant_attribute_values(conn, vid, cat_attrs_full, v_attrs)

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
            if not payload.axes[k]:
                raise HTTPException(status_code=400, detail=f"Axis '{k}' has no values")

        # Reject axis values that are not part of the category's configured options.
        cat_attrs_full = load_category_attributes_with_options(conn, prod["category_id"])
        for k in axis_keys:
            for raw_val in payload.axes[k]:
                cleaned_axis_value = validate_variant_attributes(
                    cat_attrs_full, {k: raw_val}, allow_custom_values=True
                )
                ensure_variant_attribute_options(conn, cat_attrs_full, cleaned_axis_value)

        value_lists = [payload.axes[k] for k in axis_keys]
        created = []
        skipped_duplicates = 0
        for combo in itertools.product(*value_lists):
            combo_map = dict(zip(axis_keys, combo))
            sig = build_variant_signature(combo_map)
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
                   (product_id, sku, title, price_override_dzd, stock_qty, image_url,
                    low_stock_threshold, combination_signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id, v_sku, v_title, payload.price_override_dzd, payload.default_stock,
                    prod["main_image_url"], payload.low_stock_threshold, sig,
                )
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

# --- ADMIN VARIANT MANAGEMENT (create / edit / delete / bulk) ---

def recompute_variant_signature(conn, variant_id: int) -> str:
    cur = conn.cursor()
    cur.execute(
        """SELECT ca.attr_key, vav.option_value
           FROM variant_attribute_values vav
           JOIN category_attributes ca ON ca.id = vav.attribute_id
           WHERE vav.variant_id = ?""",
        (variant_id,),
    )
    attrs = {r["attr_key"]: r["option_value"] for r in cur.fetchall()}
    cur.execute("SELECT sku FROM product_variants WHERE id = ?", (variant_id,))
    row = cur.fetchone()
    sig = build_variant_signature(attrs, row["sku"] if row else "")
    cur.execute("UPDATE product_variants SET combination_signature = ? WHERE id = ?", (sig, variant_id))
    return sig

@app.post("/api/v1/admin/products/{product_id}/variants", status_code=201)
def admin_create_variant(
    product_id: int,
    payload: VariantCreateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")

        cat_attrs = load_category_attributes_with_options(conn, prod["category_id"])
        attrs = validate_variant_attributes(cat_attrs, payload.attributes, allow_custom_values=True)
        ensure_variant_attribute_options(conn, cat_attrs, attrs)
        sku = normalize_variant_sku(payload.sku) if payload.sku else auto_variant_sku(
            conn, prod["sku"], attrs, build_variant_signature(attrs)
        )
        assert_variant_sku_available(conn, sku)
        sig = build_variant_signature(attrs, sku)
        assert_variant_signature_available(conn, product_id, sig)

        title = (payload.title or "").strip() or (" / ".join(attrs[k] for k in sorted(attrs)) if attrs else "Standard")
        cur.execute(
            """INSERT INTO product_variants
               (product_id, sku, barcode, title, price_override_dzd, stock_qty, image_url,
                purchase_cost_dzd, weight_grams, low_stock_threshold, is_active, combination_signature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                product_id, sku, payload.barcode, title, payload.price_override_dzd, payload.stock_qty,
                payload.image_url or prod["main_image_url"], payload.purchase_cost_dzd,
                payload.weight_grams, payload.low_stock_threshold, 1 if payload.is_active else 0, sig,
            )
        )
        variant_id = cur.lastrowid
        replace_variant_attribute_values(conn, variant_id, cat_attrs, attrs)
        if payload.stock_qty > 0:
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (variant_id, int(admin["sub"]), payload.stock_qty, 0, payload.stock_qty, "variant_created"),
            )
        log_audit(conn, int(admin["sub"]), "create_variant", "product_variant", str(variant_id), {
            "product_id": product_id, "sku": sku, "signature": sig, "stock_qty": payload.stock_qty,
        })
        return serialize_variant_row(conn, variant_id)

@app.put("/api/v1/admin/variants/{variant_id}")
def admin_update_variant(
    variant_id: int,
    payload: VariantUpdateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute(
            """SELECT pv.*, p.category_id AS product_category_id, p.selling_price_dzd, p.sku AS product_sku
               FROM product_variants pv
               JOIN products p ON p.id = pv.product_id
               WHERE pv.id = ?""",
            (variant_id,),
        )
        variant = cur.fetchone()
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")

        fields: Dict[str, Any] = {}
        if payload.sku is not None:
            sku = normalize_variant_sku(payload.sku)
            assert_variant_sku_available(conn, sku, exclude_variant_id=variant_id)
            fields["sku"] = sku
        if payload.barcode is not None:
            fields["barcode"] = payload.barcode.strip() or None
        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise HTTPException(status_code=422, detail="Variant title cannot be empty")
            fields["title"] = title
        if payload.clear_price_override:
            fields["price_override_dzd"] = None
        elif payload.price_override_dzd is not None:
            fields["price_override_dzd"] = payload.price_override_dzd
        if payload.image_url is not None:
            fields["image_url"] = payload.image_url.strip() or None
        if payload.purchase_cost_dzd is not None:
            fields["purchase_cost_dzd"] = payload.purchase_cost_dzd
        if payload.weight_grams is not None:
            fields["weight_grams"] = payload.weight_grams
        if payload.low_stock_threshold is not None:
            fields["low_stock_threshold"] = payload.low_stock_threshold
        if payload.is_active is not None:
            fields["is_active"] = 1 if payload.is_active else 0

        previous_stock = int(variant["stock_qty"])
        stock_change = 0
        if payload.stock_qty is not None and int(payload.stock_qty) != previous_stock:
            stock_change = int(payload.stock_qty) - previous_stock
            fields["stock_qty"] = int(payload.stock_qty)

        validated_attrs = None
        cat_attrs = None
        if payload.attributes is not None:
            cat_attrs = load_category_attributes_with_options(conn, variant["product_category_id"])
            validated_attrs = validate_variant_attributes(
                cat_attrs, payload.attributes, allow_custom_values=True
            )
            ensure_variant_attribute_options(conn, cat_attrs, validated_attrs)
            sig = build_variant_signature(validated_attrs, fields.get("sku", variant["sku"]))
            assert_variant_signature_available(
                conn, variant["product_id"], sig, exclude_variant_id=variant_id
            )
            fields["combination_signature"] = sig

        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields.keys())
            cur.execute(
                f"UPDATE product_variants SET {assignments} WHERE id = ?",
                [*fields.values(), variant_id],
            )
        if validated_attrs is not None and cat_attrs is not None:
            replace_variant_attribute_values(conn, variant_id, cat_attrs, validated_attrs)
        if stock_change:
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    variant_id, int(admin["sub"]), stock_change, previous_stock,
                    previous_stock + stock_change, "variant_edit",
                )
            )
        log_audit(conn, int(admin["sub"]), "update_variant", "product_variant", str(variant_id), {
            "changed_fields": sorted(fields.keys()),
            "stock_change": stock_change,
        })
        return serialize_variant_row(conn, variant_id)

@app.delete("/api/v1/admin/variants/{variant_id}")
def admin_delete_variant(
    variant_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,))
        variant = cur.fetchone()
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")

        cur.execute("SELECT COUNT(*) AS cnt FROM order_items WHERE variant_id = ?", (variant_id,))
        used_in_orders = int(cur.fetchone()["cnt"] or 0)
        if used_in_orders > 0:
            cur.execute("UPDATE product_variants SET is_active = 0 WHERE id = ?", (variant_id,))
            log_audit(conn, int(admin["sub"]), "deactivate_variant", "product_variant", str(variant_id), {
                "sku": variant["sku"], "order_lines": used_in_orders,
            })
            return {
                "deleted": False,
                "deactivated": True,
                "variant_id": variant_id,
                "reason": f"Variant is referenced by {used_in_orders} historical order line(s) and was deactivated instead of deleted.",
            }

        cur.execute("DELETE FROM variant_attribute_values WHERE variant_id = ?", (variant_id,))
        cur.execute("DELETE FROM product_variants WHERE id = ?", (variant_id,))
        log_audit(conn, int(admin["sub"]), "delete_variant", "product_variant", str(variant_id), {
            "sku": variant["sku"],
        })
        return {"deleted": True, "deactivated": False, "variant_id": variant_id}

@app.post("/api/v1/admin/variants/bulk-update")
def admin_bulk_update_variants(
    payload: VariantBulkUpdateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        updated = 0
        missing_ids = []
        stock_updates = 0
        for variant_id in dict.fromkeys(payload.variant_ids):
            cur.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,))
            variant = cur.fetchone()
            if not variant:
                missing_ids.append(variant_id)
                continue

            fields: Dict[str, Any] = {}
            previous_stock = int(variant["stock_qty"])
            new_stock = previous_stock
            if payload.set_stock_qty is not None:
                new_stock = int(payload.set_stock_qty)
            elif payload.adjust_stock_qty is not None:
                new_stock = previous_stock + int(payload.adjust_stock_qty)
            if new_stock < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock for variant '{variant['sku']}' cannot become negative (requested {new_stock})",
                )
            if new_stock != previous_stock:
                fields["stock_qty"] = new_stock
            if payload.clear_price_override:
                fields["price_override_dzd"] = None
            elif payload.set_price_override_dzd is not None:
                fields["price_override_dzd"] = payload.set_price_override_dzd
            if payload.is_active is not None:
                fields["is_active"] = 1 if payload.is_active else 0

            if not fields:
                continue
            assignments = ", ".join(f"{column} = ?" for column in fields.keys())
            cur.execute(
                f"UPDATE product_variants SET {assignments} WHERE id = ?",
                [*fields.values(), variant_id],
            )
            updated += 1
            if new_stock != previous_stock:
                stock_updates += 1
                cur.execute(
                    """INSERT INTO inventory_movements
                       (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        variant_id, int(admin["sub"]), new_stock - previous_stock,
                        previous_stock, new_stock, payload.reason,
                    )
                )

        log_audit(conn, int(admin["sub"]), "bulk_update_variants", "product_variant", "bulk", {
            "requested": len(payload.variant_ids), "updated": updated, "stock_updates": stock_updates,
        })
        return {"updated_count": updated, "stock_updates": stock_updates, "missing_ids": missing_ids}

# --- ADMIN CATEGORY / ATTRIBUTE MANAGEMENT ---

@app.get("/api/v1/admin/categories")
def admin_list_categories(
    include_archived: bool = Query(True),
    admin: dict = Depends(require_any_permission(["categories:write", "products:write"]))
):
    with db_session() as conn:
        cur = conn.cursor()
        if include_archived:
            cur.execute("SELECT * FROM categories ORDER BY display_order ASC, id ASC")
        else:
            cur.execute("SELECT * FROM categories WHERE deleted_at IS NULL ORDER BY display_order ASC, id ASC")
        return {"items": [serialize_category(conn, dict(r)) for r in cur.fetchall()]}

@app.put("/api/v1/admin/categories-reorder")
def admin_reorder_categories(
    payload: CategoryReorderInput,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        updated = 0
        for item in payload.items:
            try:
                category_id = int(item.get("id", 0))
                display_order = int(item.get("display_order", 0))
            except (TypeError, ValueError):
                continue
            if category_id <= 0:
                continue
            cur.execute(
                "UPDATE categories SET display_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (display_order, category_id),
            )
            updated += cur.rowcount
        log_audit(conn, int(admin["sub"]), "reorder_categories", "category", "bulk", {"updated": updated})
        return {"updated_count": updated}

@app.put("/api/v1/admin/category-attributes/{attr_id}")
def admin_update_category_attribute(
    attr_id: int,
    payload: CategoryAttributeUpdate,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attributes WHERE id = ?", (attr_id,))
        attr = cur.fetchone()
        if not attr:
            raise HTTPException(status_code=404, detail="Attribute not found")

        provided = payload.dict(exclude_unset=True)
        fields: Dict[str, Any] = {}
        for key in (
            "label_fr", "label_ar", "label_en", "input_type", "unit", "default_value",
            "display_order",
        ):
            if key in provided and provided[key] is not None:
                fields[key] = provided[key]
        for key in ("is_required", "allow_multiple", "is_visible_on_storefront", "is_filterable", "is_variant_axis"):
            if key in provided and provided[key] is not None:
                fields[key] = 1 if provided[key] else 0
        if "label_fr" in fields and not str(fields["label_fr"]).strip():
            raise HTTPException(status_code=422, detail="French label cannot be empty")

        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields.keys())
            cur.execute(
                f"UPDATE category_attributes SET {assignments} WHERE id = ?",
                [*fields.values(), attr_id],
            )
            log_audit(conn, int(admin["sub"]), "update_category_attribute", "category_attribute", str(attr_id), {
                "changed_fields": sorted(fields.keys()),
            })
        cur.execute("SELECT * FROM categories WHERE id = ?", (attr["category_id"],))
        return serialize_category(conn, dict(cur.fetchone()))

@app.post("/api/v1/admin/category-attributes/{attr_id}/options", status_code=201)
def admin_create_attribute_option(
    attr_id: int,
    payload: AttributeOptionUpsert,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attributes WHERE id = ?", (attr_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Attribute not found")
        value = payload.value.strip()
        cur.execute(
            "SELECT id FROM category_attribute_options WHERE attribute_id = ? AND value = ?",
            (attr_id, value),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Option '{value}' already exists on this attribute")
        cur.execute(
            """INSERT INTO category_attribute_options
               (attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                attr_id, value, payload.label_fr or value, payload.label_ar or "",
                payload.label_en or "", payload.color_hex, payload.display_order,
            )
        )
        option_id = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_attribute_option", "category_attribute_option", str(option_id), {
            "attribute_id": attr_id, "value": value,
        })
        return {
            "id": option_id, "attribute_id": attr_id, "value": value,
            "label_fr": payload.label_fr or value, "label_ar": payload.label_ar or "",
            "label_en": payload.label_en or "", "color_hex": payload.color_hex,
            "display_order": payload.display_order,
        }

@app.put("/api/v1/admin/attribute-options/{option_id}")
def admin_update_attribute_option(
    option_id: int,
    payload: AttributeOptionUpsert,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attribute_options WHERE id = ?", (option_id,))
        option = cur.fetchone()
        if not option:
            raise HTTPException(status_code=404, detail="Option not found")
        new_value = payload.value.strip()
        if new_value != option["value"]:
            cur.execute(
                "SELECT id FROM category_attribute_options WHERE attribute_id = ? AND value = ? AND id != ?",
                (option["attribute_id"], new_value, option_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"Option '{new_value}' already exists on this attribute")
            # Keep existing variants consistent: rename the stored option value and
            # recompute each affected variant's combination signature.
            cur.execute(
                "SELECT DISTINCT variant_id FROM variant_attribute_values WHERE attribute_id = ? AND option_value = ?",
                (option["attribute_id"], option["value"]),
            )
            affected_variants = [r["variant_id"] for r in cur.fetchall()]
            cur.execute(
                "UPDATE variant_attribute_values SET option_value = ? WHERE attribute_id = ? AND option_value = ?",
                (new_value, option["attribute_id"], option["value"]),
            )
            for variant_id in affected_variants:
                recompute_variant_signature(conn, variant_id)
        cur.execute(
            """UPDATE category_attribute_options
               SET value = ?, label_fr = ?, label_ar = ?, label_en = ?, color_hex = ?, display_order = ?
               WHERE id = ?""",
            (
                new_value, payload.label_fr or new_value, payload.label_ar or "",
                payload.label_en or "", payload.color_hex, payload.display_order, option_id,
            )
        )
        log_audit(conn, int(admin["sub"]), "update_attribute_option", "category_attribute_option", str(option_id), {
            "attribute_id": option["attribute_id"], "old_value": option["value"], "new_value": new_value,
        })
        return {
            "id": option_id, "attribute_id": option["attribute_id"], "value": new_value,
            "label_fr": payload.label_fr or new_value, "label_ar": payload.label_ar or "",
            "label_en": payload.label_en or "", "color_hex": payload.color_hex,
            "display_order": payload.display_order,
        }

@app.delete("/api/v1/admin/attribute-options/{option_id}")
def admin_delete_attribute_option(
    option_id: int,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attribute_options WHERE id = ?", (option_id,))
        option = cur.fetchone()
        if not option:
            raise HTTPException(status_code=404, detail="Option not found")
        cur.execute(
            """SELECT COUNT(*) AS cnt FROM variant_attribute_values
               WHERE attribute_id = ? AND option_value = ?""",
            (option["attribute_id"], option["value"]),
        )
        in_use = int(cur.fetchone()["cnt"] or 0)
        if in_use > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Option '{option['value']}' is used by {in_use} variant(s). Rename or remove those variants first.",
            )
        cur.execute("DELETE FROM category_attribute_options WHERE id = ?", (option_id,))
        log_audit(conn, int(admin["sub"]), "delete_attribute_option", "category_attribute_option", str(option_id), {
            "attribute_id": option["attribute_id"], "value": option["value"],
        })
        return {"deleted": True, "option_id": option_id}

# --- ADMIN ORDERS & STOCK RESTORATION ---

@app.get("/api/v1/admin/orders")
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
    image_url: str = "/assets/hero_bag_clean.jpg"
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
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    purchase_cost_dzd: Optional[int] = Field(None, ge=0)
    previous_price_dzd: Optional[int] = Field(None, ge=0)
    discount_percent: Optional[int] = Field(None, ge=0, le=95)
    sku: Optional[str] = None
    slug: Optional[str] = Field(None, regex=r"^[a-z0-9-]{2,160}$")
    barcode: Optional[str] = None
    brand_id: Optional[int] = None
    category_id: Optional[int] = None
    main_image_url: Optional[str] = None
    status: Optional[str] = Field(None, regex=r"^(draft|published|archived)$")
    is_featured: Optional[bool] = None
    is_new_arrival: Optional[bool] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    weight_grams: Optional[int] = Field(None, ge=0)
    dimensions_cm: Optional[str] = None
    tags: Optional[str] = None
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
        if payload.slug and payload.slug != prod["slug"]:
            cur.execute("SELECT id FROM products WHERE slug = ? AND id != ?", (payload.slug, product_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product slug '{payload.slug}' is already used by another product"
                )
        new_version = current_version + 1
        cur.execute(
            """UPDATE products
               SET name_fr = ?,
                   selling_price_dzd = ?,
                   name_ar = COALESCE(?, name_ar),
                   name_en = COALESCE(?, name_en),
                   description_fr = COALESCE(?, description_fr),
                   description_ar = COALESCE(?, description_ar),
                   description_en = COALESCE(?, description_en),
                   purchase_cost_dzd = COALESCE(?, purchase_cost_dzd),
                   previous_price_dzd = COALESCE(?, previous_price_dzd),
                   discount_percent = COALESCE(?, discount_percent),
                   sku = COALESCE(?, sku),
                   slug = COALESCE(?, slug),
                   barcode = COALESCE(?, barcode),
                   brand_id = COALESCE(?, brand_id),
                   category_id = COALESCE(?, category_id),
                   main_image_url = COALESCE(?, main_image_url),
                   status = COALESCE(?, status),
                   is_featured = COALESCE(?, is_featured),
                   is_new_arrival = COALESCE(?, is_new_arrival),
                   seo_title = COALESCE(?, seo_title),
                   seo_description = COALESCE(?, seo_description),
                   weight_grams = COALESCE(?, weight_grams),
                   dimensions_cm = COALESCE(?, dimensions_cm),
                   tags = COALESCE(?, tags),
                   version = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND version = ?""",
            (
                payload.name_fr,
                payload.selling_price_dzd,
                payload.name_ar,
                payload.name_en,
                payload.description_fr,
                payload.description_ar,
                payload.description_en,
                payload.purchase_cost_dzd,
                payload.previous_price_dzd,
                payload.discount_percent,
                payload.sku,
                payload.slug,
                payload.barcode,
                payload.brand_id,
                payload.category_id,
                payload.main_image_url,
                payload.status,
                (1 if payload.is_featured else 0) if payload.is_featured is not None else None,
                (1 if payload.is_new_arrival else 0) if payload.is_new_arrival is not None else None,
                payload.seo_title,
                payload.seo_description,
                payload.weight_grams,
                payload.dimensions_cm,
                payload.tags,
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
        paged_rows = serialize_products_batch(conn, cur.fetchall(), include_private=True)
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
    limit: int = Query(50, ge=1, le=500),
    action_filter: Optional[str] = Query(None, alias="action"),
    entity_type: Optional[str] = Query(None),
    admin_user_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, max_length=120),
    admin: dict = Depends(require_permission("settings:write")),
):
    where = []
    params: List[Any] = []
    if action_filter:
        where.append("al.action = ?"); params.append(action_filter.strip())
    if entity_type:
        where.append("al.entity_type = ?"); params.append(entity_type.strip())
    if admin_user_id is not None:
        where.append("al.admin_user_id = ?"); params.append(admin_user_id)
    if q:
        like = f"%{q.strip()}%"
        where.append("(al.action LIKE ? OR al.entity_id LIKE ? OR al.details_json LIKE ?)")
        params.extend([like, like, like])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT al.*, au.email AS admin_email, au.full_name AS admin_name "
        "FROM audit_logs al LEFT JOIN admin_users au ON au.id = al.admin_user_id"
        f"{where_sql} ORDER BY al.id DESC LIMIT ?"
    )
    params.append(limit)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        items = []
        for r in cur.fetchall():
            d = dict(r)
            try:
                d["details"] = json.loads(d.pop("details_json") or "{}")
            except Exception:
                d["details"] = {}
            items.append(d)
        return {"items": items, "count": len(items)}


@app.get("/api/v1/admin/audit-logs/facets")
def admin_audit_log_facets(admin: dict = Depends(require_permission("settings:write"))):
    """Distinct actions and entity types for building the filter UI (last ~5000 rows)."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT action, entity_type, COUNT(*) AS c
               FROM audit_logs
               WHERE id > (SELECT COALESCE(MAX(id), 0) - 5000 FROM audit_logs)
               GROUP BY action, entity_type"""
        )
        actions_set: Dict[str, int] = {}
        entities_set: Dict[str, int] = {}
        for r in cur.fetchall():
            actions_set[r["action"]] = actions_set.get(r["action"], 0) + int(r["c"])
            entities_set[r["entity_type"]] = entities_set.get(r["entity_type"], 0) + int(r["c"])
        return {
            "actions": [{"code": k, "count": v} for k, v in sorted(actions_set.items())],
            "entity_types": [{"code": k, "count": v} for k, v in sorted(entities_set.items())],
        }
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
        # Join per-supplier aggregate stats from purchase_orders so the UI can
        # show outstanding balances and activity without N+1 extra calls.
        cur.execute(
            """SELECT s.*,
                      (SELECT COUNT(*) FROM purchase_orders po WHERE po.supplier_id = s.id) AS purchase_orders_count,
                      (SELECT COALESCE(SUM(total_cost_dzd), 0) FROM purchase_orders po WHERE po.supplier_id = s.id AND po.status != 'cancelled') AS total_purchased_dzd,
                      (SELECT COALESCE(SUM(total_cost_dzd - paid_amount_dzd), 0) FROM purchase_orders po
                        WHERE po.supplier_id = s.id AND po.status NOT IN ('draft', 'cancelled') AND po.total_cost_dzd > po.paid_amount_dzd) AS outstanding_dzd
               FROM suppliers s ORDER BY s.is_active DESC, s.id DESC"""
        )
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.get("/api/v1/admin/suppliers/{supplier_id}")
def admin_get_supplier_detail(
    supplier_id: int,
    admin: dict = Depends(require_permission("dashboard:read")),
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        s = cur.fetchone()
        if not s:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        d = dict(s)
        cur.execute(
            """SELECT id, reference, status, payment_status, subtotal_dzd, shipping_dzd, tax_dzd,
                      total_cost_dzd, paid_amount_dzd, expected_date, received_at, created_at
               FROM purchase_orders WHERE supplier_id = ? ORDER BY id DESC LIMIT 50""",
            (supplier_id,),
        )
        d["recent_purchase_orders"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """SELECT COUNT(*) AS c,
                      COALESCE(SUM(total_cost_dzd), 0) AS total,
                      COALESCE(SUM(paid_amount_dzd), 0) AS paid,
                      COALESCE(SUM(CASE WHEN status NOT IN ('draft','cancelled') AND total_cost_dzd > paid_amount_dzd
                                        THEN total_cost_dzd - paid_amount_dzd ELSE 0 END), 0) AS outstanding
               FROM purchase_orders WHERE supplier_id = ? AND status != 'cancelled'""",
            (supplier_id,),
        )
        agg = cur.fetchone()
        d["stats"] = {
            "purchase_orders_count": int(agg["c"]),
            "total_purchased_dzd": int(agg["total"]),
            "total_paid_dzd": int(agg["paid"]),
            "outstanding_dzd": int(agg["outstanding"]),
        }
        return d

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

# ============================================================================
# POINT OF SALE (POS) — In-store sales, cash register sessions & refunds
# Backend-authoritative: prices, stock deduction and register math are computed
# server-side. In-store sales share the catalog and the inventory_movements
# ledger with online orders but are a distinct transaction type (immediate
# payment, no delivery). Completed sales are never edited/deleted — corrections
# go through reversal (refund) transactions.
# ============================================================================

_POS_PAYMENT_METHODS = {"cash", "card", "transfer", "other"}

_BOUTIQUE_INFO = {
    "name": "Mus Luxury (LUXE)",
    "address": "FVX6+GCJ Mus luxury, Ouled Yaïch, Blida (09), Algérie",
    "phone": "0655534154",
    "whatsapp": "+213655534154",
    "currency": "DZD (DA)",
}


class RegisterOpenInput(BaseModel):
    register_name: str = Field("Caisse principale", min_length=1, max_length=80)
    opening_float_dzd: int = Field(0, ge=0, le=100_000_000)
    notes: Optional[str] = Field(None, max_length=1000)


class RegisterCloseInput(BaseModel):
    counted_cash_dzd: int = Field(..., ge=0, le=100_000_000)
    notes: Optional[str] = Field(None, max_length=1000)


class PosSaleItemInput(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0, le=1000)
    line_discount_dzd: int = Field(0, ge=0, le=100_000_000)


class PosPaymentInput(BaseModel):
    method: str = Field("cash", regex=r"^(cash|card|transfer|other)$")
    amount_dzd: int = Field(..., ge=0, le=100_000_000)
    tendered_dzd: Optional[int] = Field(None, ge=0, le=100_000_000)


class PosSaleCreate(BaseModel):
    items: List[PosSaleItemInput] = Field(..., min_items=1, max_items=200)
    payments: List[PosPaymentInput] = Field(..., min_items=1, max_items=10)
    customer_id: Optional[int] = None
    order_discount_dzd: int = Field(0, ge=0, le=100_000_000)
    notes: Optional[str] = Field(None, max_length=1000)


class PosRefundItemInput(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0, le=1000)


class PosRefundInput(BaseModel):
    items: List[PosRefundItemInput] = Field(default_factory=list, max_items=200)
    refund_method: str = Field("cash", regex=r"^(cash|card|transfer|other)$")
    notes: Optional[str] = Field(None, max_length=1000)


def _pos_store_tax_percent(conn) -> int:
    """Reads a configurable POS tax rate (integer percent) from store_settings; 0 if unset."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", ("pos_tax_rate_percent",))
        row = cur.fetchone()
        if row and row["setting_value"] is not None:
            return max(0, min(100, int(str(row["setting_value"]).strip() or 0)))
    except Exception:
        pass
    return 0


def _get_open_register(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM cash_register_sessions WHERE status = 'open' ORDER BY id DESC LIMIT 1")
    return cur.fetchone()


def _boutique_info_from_settings(conn) -> dict:
    """Prefer configured fiscal settings; fall back to defaults so receipts always render."""
    try:
        f = _read_fiscal_settings(conn)
    except Exception:
        return _BOUTIQUE_INFO
    legal = (f.get("fiscal_legal_name") or "").strip()
    commercial = (f.get("fiscal_commercial_name") or "").strip()
    return {
        "name": commercial or legal or _BOUTIQUE_INFO["name"],
        "legal_name": legal or commercial or _BOUTIQUE_INFO["name"],
        "address": (f.get("fiscal_address") or "").strip() or _BOUTIQUE_INFO["address"],
        "phone": (f.get("fiscal_phone") or "").strip() or _BOUTIQUE_INFO["phone"],
        "whatsapp": _BOUTIQUE_INFO["whatsapp"],
        "currency": _BOUTIQUE_INFO["currency"],
        "nif": f.get("fiscal_nif") or "",
        "nis": f.get("fiscal_nis") or "",
        "rc": f.get("fiscal_rc") or "",
        "article": f.get("fiscal_article") or "",
        "footer_line": (f.get("receipt_footer_line") or "").strip(),
    }


def _pos_sale_payload(conn, sale_id: int) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pos_sales WHERE id = ?", (sale_id,))
    s = cur.fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="Sale not found")
    sale = dict(s)
    cur.execute("SELECT * FROM pos_sale_items WHERE sale_id = ? ORDER BY id", (sale_id,))
    sale["items"] = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM pos_payments WHERE sale_id = ? ORDER BY id", (sale_id,))
    sale["payments"] = [dict(r) for r in cur.fetchall()]
    if sale.get("customer_id"):
        cur.execute("SELECT id, full_name, phone FROM customers WHERE id = ?", (sale["customer_id"],))
        c = cur.fetchone()
        sale["customer"] = dict(c) if c else None
    else:
        sale["customer"] = None
    cur.execute("SELECT full_name FROM admin_users WHERE id = ?", (sale["cashier_admin_id"],))
    cash = cur.fetchone()
    sale["cashier_name"] = cash["full_name"] if cash else None
    sale["boutique_info"] = _boutique_info_from_settings(conn)
    return sale


def _register_runtime_totals(conn, session_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN sale_type = 'sale'   THEN total_dzd ELSE 0 END), 0) AS sales_total,
             COALESCE(SUM(CASE WHEN sale_type = 'refund' THEN total_dzd ELSE 0 END), 0) AS refunds_total,
             COALESCE(SUM(CASE WHEN sale_type = 'sale'   THEN 1 ELSE 0 END), 0)         AS sales_count
           FROM pos_sales WHERE register_session_id = ?""",
        (session_id,),
    )
    agg = cur.fetchone()
    cur.execute(
        """SELECT COALESCE(SUM(CASE WHEN s.sale_type = 'sale' THEN p.amount_dzd ELSE -p.amount_dzd END), 0) AS net_cash
           FROM pos_payments p JOIN pos_sales s ON s.id = p.sale_id
           WHERE s.register_session_id = ? AND p.method = 'cash'""",
        (session_id,),
    )
    net_cash = int(cur.fetchone()["net_cash"])
    return {
        "sales_total_dzd": int(agg["sales_total"]),
        "refunds_total_dzd": int(agg["refunds_total"]),
        "sales_count": int(agg["sales_count"]),
        "net_cash_dzd": net_cash,
    }


@app.post("/api/v1/admin/pos/register/open", status_code=201)
def pos_open_register(payload: RegisterOpenInput, admin: dict = Depends(require_permission("register:manage"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        existing = _get_open_register(conn)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A cash register session (#{existing['id']}) is already open. Close it before opening a new one.",
            )
        cur.execute(
            """INSERT INTO cash_register_sessions
               (register_name, opened_by_admin_id, opening_float_dzd, status, notes)
               VALUES (?, ?, ?, 'open', ?)""",
            (payload.register_name, int(admin["sub"]), payload.opening_float_dzd, payload.notes),
        )
        session_id = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "open_register", "cash_register_session", str(session_id), {
            "opening_float_dzd": payload.opening_float_dzd, "register_name": payload.register_name,
        })
        cur.execute("SELECT * FROM cash_register_sessions WHERE id = ?", (session_id,))
        return dict(cur.fetchone())


@app.get("/api/v1/admin/pos/register/current")
def pos_current_register(admin: dict = Depends(require_permission("pos:read"))):
    with db_session() as conn:
        session = _get_open_register(conn)
        if not session:
            return {"open": False, "session": None}
        sd = dict(session)
        totals = _register_runtime_totals(conn, sd["id"])
        sd.update(totals)
        sd["expected_cash_dzd"] = int(sd["opening_float_dzd"]) + totals["net_cash_dzd"]
        return {"open": True, "session": sd}


@app.post("/api/v1/admin/pos/register/close")
def pos_close_register(payload: RegisterCloseInput, admin: dict = Depends(require_permission("register:manage"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        session = _get_open_register(conn)
        if not session:
            raise HTTPException(status_code=404, detail="No open cash register session to close")
        session_id = int(session["id"])
        totals = _register_runtime_totals(conn, session_id)
        expected_cash = int(session["opening_float_dzd"]) + totals["net_cash_dzd"]
        variance = int(payload.counted_cash_dzd) - expected_cash
        cur.execute(
            """UPDATE cash_register_sessions
               SET status = 'closed', closed_by_admin_id = ?, closed_at = CURRENT_TIMESTAMP,
                   expected_cash_dzd = ?, counted_cash_dzd = ?, variance_dzd = ?,
                   total_sales_dzd = ?, total_refunds_dzd = ?, sales_count = ?,
                   notes = COALESCE(?, notes)
               WHERE id = ? AND status = 'open'""",
            (int(admin["sub"]), expected_cash, payload.counted_cash_dzd, variance,
             totals["sales_total_dzd"], totals["refunds_total_dzd"], totals["sales_count"],
             payload.notes, session_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Register session already closed")
        log_audit(conn, int(admin["sub"]), "close_register", "cash_register_session", str(session_id), {
            "expected_cash_dzd": expected_cash, "counted_cash_dzd": payload.counted_cash_dzd, "variance_dzd": variance,
        })
        cur.execute("SELECT * FROM cash_register_sessions WHERE id = ?", (session_id,))
        return dict(cur.fetchone())


@app.get("/api/v1/admin/pos/register/sessions")
def pos_list_register_sessions(
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(require_permission("pos:read")),
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT crs.*, ao.full_name AS opened_by_name, ac.full_name AS closed_by_name
               FROM cash_register_sessions crs
               LEFT JOIN admin_users ao ON ao.id = crs.opened_by_admin_id
               LEFT JOIN admin_users ac ON ac.id = crs.closed_by_admin_id
               ORDER BY crs.id DESC LIMIT ?""",
            (limit,),
        )
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.get("/api/v1/admin/pos/lookup")
def pos_lookup(
    code: str = Query(..., min_length=1, max_length=120),
    admin: dict = Depends(require_permission("pos:read")),
):
    """Resolve a scanned barcode / typed SKU to a variant, or fall back to a name/SKU search."""
    term = code.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Empty lookup code")
    with db_session() as conn:
        cur = conn.cursor()
        # 1. Exact variant barcode or SKU → single variant
        cur.execute(
            """SELECT pv.id AS variant_id, pv.sku, pv.barcode, pv.title AS variant_title,
                      pv.price_override_dzd, pv.stock_qty, pv.is_active,
                      p.id AS product_id, p.name_fr AS product_name, p.selling_price_dzd,
                      p.main_image_url, p.status AS product_status
               FROM product_variants pv JOIN products p ON p.id = pv.product_id
               WHERE (pv.barcode = ? OR pv.sku = ?) AND pv.is_active = 1 AND p.deleted_at IS NULL
               LIMIT 1""",
            (term, term),
        )
        v = cur.fetchone()
        if v:
            vd = dict(v)
            vd["unit_price_dzd"] = int(vd["price_override_dzd"]) if vd["price_override_dzd"] is not None else int(vd["selling_price_dzd"])
            return {"match_type": "variant", "variant": vd, "results": [vd]}

        # 2. Product-level barcode / SKU → product with its active variants
        cur.execute(
            """SELECT id, name_fr, selling_price_dzd, main_image_url, status
               FROM products WHERE (barcode = ? OR sku = ?) AND deleted_at IS NULL LIMIT 1""",
            (term, term),
        )
        p = cur.fetchone()
        if p:
            return {"match_type": "product", "results": [_pos_product_with_variants(conn, dict(p))]}

        # 3. Fallback name / SKU search (search box)
        like = f"%{term}%"
        cur.execute(
            """SELECT id, name_fr, selling_price_dzd, main_image_url, status
               FROM products
               WHERE deleted_at IS NULL AND status = 'published'
                 AND (name_fr LIKE ? OR sku LIKE ? OR name_en LIKE ?)
               ORDER BY sales_count DESC LIMIT 20""",
            (like, like, like),
        )
        rows = [_pos_product_with_variants(conn, dict(r)) for r in cur.fetchall()]
        return {"match_type": "search" if rows else "none", "results": rows}


def _pos_product_with_variants(conn, product: dict) -> dict:
    cur = conn.cursor()
    cur.execute(
        """SELECT id AS variant_id, sku, barcode, title AS variant_title,
                  price_override_dzd, stock_qty
           FROM product_variants WHERE product_id = ? AND is_active = 1 ORDER BY id""",
        (product["id"],),
    )
    variants = []
    for r in cur.fetchall():
        vd = dict(r)
        vd["product_id"] = product["id"]
        vd["product_name"] = product["name_fr"]
        vd["main_image_url"] = product.get("main_image_url")
        vd["unit_price_dzd"] = int(vd["price_override_dzd"]) if vd["price_override_dzd"] is not None else int(product["selling_price_dzd"])
        variants.append(vd)
    product["variants"] = variants
    return product


@app.post("/api/v1/admin/pos/sales", status_code=201)
def pos_create_sale(
    payload: PosSaleCreate,
    admin: dict = Depends(require_permission("pos:sell")),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    idem = (idempotency_key or "").strip() or None
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()

        # Idempotent retry (offline POS may resend): return the already-created sale.
        if idem:
            cur.execute("SELECT id FROM pos_sales WHERE idempotency_key = ?", (idem,))
            dup = cur.fetchone()
            if dup:
                return _pos_sale_payload(conn, int(dup["id"]))

        session = _get_open_register(conn)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No open cash register session. Open the register before selling.",
            )

        # Validate optional customer
        if payload.customer_id is not None:
            cur.execute("SELECT id FROM customers WHERE id = ?", (payload.customer_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Customer {payload.customer_id} not found")

        # Consolidate duplicate variant lines (sum quantities, sum line discounts)
        merged: Dict[int, Dict[str, int]] = {}
        for it in payload.items:
            m = merged.setdefault(it.variant_id, {"quantity": 0, "line_discount_dzd": 0})
            m["quantity"] += int(it.quantity)
            m["line_discount_dzd"] += int(it.line_discount_dzd)

        subtotal_dzd = 0
        total_line_discount = 0
        resolved = []
        for vid, m in merged.items():
            cur.execute(
                """SELECT pv.*, p.name_fr AS product_name, p.selling_price_dzd, p.status AS product_status
                   FROM product_variants pv JOIN products p ON p.id = pv.product_id
                   WHERE pv.id = ? AND pv.is_active = 1""",
                (vid,),
            )
            v = cur.fetchone()
            if not v or v["product_status"] == "archived":
                raise HTTPException(status_code=404, detail=f"Product variant {vid} is unavailable")
            qty = m["quantity"]
            if v["stock_qty"] < qty:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for '{v['product_name']} ({v['title']})': requested {qty}, available {v['stock_qty']}",
                )
            unit_price = int(v["price_override_dzd"]) if v["price_override_dzd"] is not None else int(v["selling_price_dzd"])
            line_gross = unit_price * qty
            line_discount = min(int(m["line_discount_dzd"]), line_gross)
            line_total = line_gross - line_discount
            subtotal_dzd += line_gross
            total_line_discount += line_discount
            resolved.append((v, qty, unit_price, line_discount, line_total))

        order_discount = min(int(payload.order_discount_dzd), subtotal_dzd - total_line_discount)
        discount_dzd = total_line_discount + order_discount
        net_before_tax = subtotal_dzd - discount_dzd
        tax_percent = _pos_store_tax_percent(conn)
        tax_dzd = (net_before_tax * tax_percent) // 100
        total_dzd = net_before_tax + tax_dzd

        # Payments must settle the total exactly (cash change handled via tendered)
        paid = sum(int(pm.amount_dzd) for pm in payload.payments)
        if paid != total_dzd:
            raise HTTPException(
                status_code=422,
                detail=f"Payments ({paid} DA) must equal sale total ({total_dzd} DA)",
            )

        sale_ref = ""
        sale_id = None
        for _attempt in range(3):
            sale_ref = f"POS-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
            try:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, idempotency_key, notes)
                       VALUES (?, ?, ?, ?, 'sale', ?, ?, ?, ?, 'completed', ?, ?)""",
                    (sale_ref, int(session["id"]), int(admin["sub"]), payload.customer_id,
                     subtotal_dzd, discount_dzd, tax_dzd, total_dzd, idem, payload.notes),
                )
                sale_id = cur.lastrowid
                break
            except Exception:
                if _attempt == 2:
                    raise

        for v, qty, unit_price, line_discount, line_total in resolved:
            cur.execute(
                """INSERT INTO pos_sale_items
                   (sale_id, product_id, variant_id, product_name, variant_title, sku,
                    unit_price_dzd, line_discount_dzd, quantity, line_total_dzd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sale_id, v["product_id"], v["id"], v["product_name"], v["title"], v["sku"],
                 unit_price, line_discount, qty, line_total),
            )
            cur.execute(
                "UPDATE product_variants SET stock_qty = stock_qty - ? WHERE id = ? AND is_active = 1 AND stock_qty >= ?",
                (qty, v["id"], qty),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Insufficient stock for '{v['product_name']} ({v['title']})'")
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (v["id"],))
            new_qty = int(cur.fetchone()["stock_qty"])
            prev_qty = new_qty + qty
            cur.execute("UPDATE products SET sales_count = sales_count + ? WHERE id = ?", (qty, v["product_id"]))
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, pos_sale_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, ?, 'pos_sale')""",
                (v["id"], sale_id, int(admin["sub"]), -qty, prev_qty, new_qty),
            )

        for pm in payload.payments:
            change = 0
            if pm.method == "cash" and pm.tendered_dzd is not None:
                change = max(0, int(pm.tendered_dzd) - int(pm.amount_dzd))
            cur.execute(
                """INSERT INTO pos_payments (sale_id, method, amount_dzd, tendered_dzd, change_dzd)
                   VALUES (?, ?, ?, ?, ?)""",
                (sale_id, pm.method, int(pm.amount_dzd), pm.tendered_dzd, change),
            )

        log_audit(conn, int(admin["sub"]), "pos_sale", "pos_sale", str(sale_id), {
            "sale_reference": sale_ref, "total_dzd": total_dzd, "items": len(resolved),
        })
        return _pos_sale_payload(conn, int(sale_id))


@app.get("/api/v1/admin/pos/sales")
def pos_list_sales(
    limit: int = Query(50, ge=1, le=200),
    session_id: Optional[int] = Query(None),
    admin: dict = Depends(require_permission("pos:read")),
):
    with db_session() as conn:
        cur = conn.cursor()
        if session_id is not None:
            cur.execute(
                "SELECT * FROM pos_sales WHERE register_session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
        else:
            cur.execute("SELECT * FROM pos_sales ORDER BY id DESC LIMIT ?", (limit,))
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.get("/api/v1/admin/pos/sales/{sale_id}")
def pos_get_sale(sale_id: int, admin: dict = Depends(require_permission("pos:read"))):
    with db_session() as conn:
        return _pos_sale_payload(conn, sale_id)


@app.post("/api/v1/admin/pos/sales/{sale_id}/refund", status_code=201)
def pos_refund_sale(
    sale_id: int,
    payload: PosRefundInput,
    admin: dict = Depends(require_permission("pos:refund")),
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM pos_sales WHERE id = ?", (sale_id,))
        orig = cur.fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="Sale not found")
        if orig["sale_type"] != "sale":
            raise HTTPException(status_code=400, detail="Only sales can be refunded")
        if orig["status"] in ("refunded", "voided"):
            raise HTTPException(status_code=409, detail=f"Sale already {orig['status']}")

        session = _get_open_register(conn)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No open cash register session. Open the register before refunding.",
            )

        # Sold quantities per variant on the original sale
        cur.execute(
            "SELECT variant_id, product_id, product_name, variant_title, sku, unit_price_dzd, quantity "
            "FROM pos_sale_items WHERE sale_id = ?",
            (sale_id,),
        )
        sold = {int(r["variant_id"]): dict(r) for r in cur.fetchall()}
        # Already-refunded quantities (from prior partial refunds reversing this sale)
        cur.execute(
            """SELECT psi.variant_id AS vid, COALESCE(SUM(psi.quantity), 0) AS q
               FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
               WHERE ps.sale_type = 'refund' AND ps.reverses_sale_id = ?
               GROUP BY psi.variant_id""",
            (sale_id,),
        )
        refunded_qty = {int(r["vid"]): int(r["q"]) for r in cur.fetchall()}

        # Determine refund lines: explicit subset, or all remaining when none given
        if payload.items:
            requested = {}
            for it in payload.items:
                requested[it.variant_id] = requested.get(it.variant_id, 0) + int(it.quantity)
        else:
            requested = {vid: (sold[vid]["quantity"] - refunded_qty.get(vid, 0)) for vid in sold}
            requested = {vid: q for vid, q in requested.items() if q > 0}

        if not requested:
            raise HTTPException(status_code=400, detail="Nothing left to refund on this sale")

        refund_lines = []
        refund_subtotal = 0
        for vid, qty in requested.items():
            if vid not in sold:
                raise HTTPException(status_code=400, detail=f"Variant {vid} was not part of sale #{sale_id}")
            remaining = sold[vid]["quantity"] - refunded_qty.get(vid, 0)
            if qty > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot refund {qty} of variant {vid}: only {remaining} remain refundable",
                )
            unit_price = int(sold[vid]["unit_price_dzd"])
            line_total = unit_price * qty
            refund_subtotal += line_total
            refund_lines.append((sold[vid], qty, unit_price, line_total))

        ref = ""
        refund_id = None
        for _attempt in range(3):
            ref = f"RMA-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
            try:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        reverses_sale_id, subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, notes)
                       VALUES (?, ?, ?, ?, 'refund', ?, ?, 0, 0, ?, 'completed', ?)""",
                    (ref, int(session["id"]), int(admin["sub"]), orig["customer_id"], sale_id,
                     refund_subtotal, refund_subtotal, payload.notes),
                )
                refund_id = cur.lastrowid
                break
            except Exception:
                if _attempt == 2:
                    raise

        for line, qty, unit_price, line_total in refund_lines:
            cur.execute(
                """INSERT INTO pos_sale_items
                   (sale_id, product_id, variant_id, product_name, variant_title, sku,
                    unit_price_dzd, line_discount_dzd, quantity, line_total_dzd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (refund_id, line["product_id"], line["variant_id"], line["product_name"],
                 line["variant_title"], line["sku"], unit_price, qty, line_total),
            )
            # Restock the returned units
            cur.execute("UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ?", (qty, line["variant_id"]))
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (line["variant_id"],))
            new_qty = int(cur.fetchone()["stock_qty"])
            prev_qty = new_qty - qty
            cur.execute("UPDATE products SET sales_count = MAX(0, sales_count - ?) WHERE id = ?", (qty, line["product_id"]))
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, pos_sale_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, ?, 'pos_refund')""",
                (line["variant_id"], refund_id, int(admin["sub"]), qty, prev_qty, new_qty),
            )

        cur.execute(
            "INSERT INTO pos_payments (sale_id, method, amount_dzd, change_dzd) VALUES (?, ?, ?, 0)",
            (refund_id, payload.refund_method, refund_subtotal),
        )

        # Update original sale status: fully vs partially refunded
        total_refunded_after = {vid: refunded_qty.get(vid, 0) for vid in sold}
        for line, qty, _u, _lt in refund_lines:
            total_refunded_after[line["variant_id"]] = total_refunded_after.get(line["variant_id"], 0) + qty
        fully = all(total_refunded_after.get(vid, 0) >= sold[vid]["quantity"] for vid in sold)
        new_status = "refunded" if fully else "partially_refunded"
        cur.execute("UPDATE pos_sales SET status = ? WHERE id = ?", (new_status, sale_id))

        log_audit(conn, int(admin["sub"]), "pos_refund", "pos_sale", str(refund_id), {
            "refund_reference": ref, "reverses_sale_id": sale_id,
            "refund_total_dzd": refund_subtotal, "original_new_status": new_status,
        })
        return _pos_sale_payload(conn, int(refund_id))

# ============================================================================
# BARCODE & PRODUCT IDENTIFICATION
# Generation (valid check digits), validation, duplicate prevention, assignment
# and label data. Internal store barcodes use the GS1 restricted-distribution
# prefix (20) and are kept distinct from externally registered GS1 identifiers.
# A scanned barcode resolves to a variant via /admin/pos/lookup.
# ============================================================================

# GS1 reserves prefixes 02 and 20-29 for in-store / restricted distribution.
# We mint internal EAN-13 codes under "20" so they never collide with real
# manufacturer GTINs and are never presented as registered GS1 identifiers.
_INTERNAL_EAN_PREFIX = "20"


def ean_check_digit(body: str) -> int:
    """Mod-10 check digit for EAN-13 (12 digits) or EAN-8 (7 digits).
    Weights alternate 1,3,... starting at weight 1 for the leftmost digit of a
    12-digit body (EAN-13) and 3 for a 7-digit body (EAN-8)."""
    digits = [int(c) for c in body]
    # Rightmost body digit always carries weight 3.
    weights = [3 if (len(digits) - 1 - i) % 2 == 0 else 1 for i in range(len(digits))]
    total = sum(d * w for d, w in zip(digits, weights))
    return (10 - (total % 10)) % 10


def upca_check_digit(body11: str) -> int:
    """Mod-10 check digit for UPC-A (11-digit body). Odd positions (1st, 3rd…) weight 3."""
    digits = [int(c) for c in body11]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits))
    return (10 - (total % 10)) % 10


def detect_symbology(code: str) -> str:
    c = code.strip()
    if c.isdigit():
        if len(c) == 13:
            return "ean13"
        if len(c) == 12:
            return "upca"
        if len(c) == 8:
            return "ean8"
        return "numeric"
    return "code128"


def validate_barcode(code: str) -> dict:
    """Returns {valid, symbology, normalized, reason}. Verifies the check digit
    for fixed-length retail symbologies; Code 128 accepts printable ASCII."""
    c = (code or "").strip()
    if not c:
        return {"valid": False, "symbology": None, "normalized": "", "reason": "Code vide"}
    sym = detect_symbology(c)
    if sym == "ean13":
        ok = ean_check_digit(c[:12]) == int(c[12])
        return {"valid": ok, "symbology": "ean13", "normalized": c, "reason": None if ok else "Chiffre de contrôle EAN-13 invalide"}
    if sym == "ean8":
        ok = ean_check_digit(c[:7]) == int(c[7])
        return {"valid": ok, "symbology": "ean8", "normalized": c, "reason": None if ok else "Chiffre de contrôle EAN-8 invalide"}
    if sym == "upca":
        ok = upca_check_digit(c[:11]) == int(c[11])
        return {"valid": ok, "symbology": "upca", "normalized": c, "reason": None if ok else "Chiffre de contrôle UPC-A invalide"}
    if sym == "numeric":
        return {"valid": False, "symbology": "numeric", "normalized": c, "reason": "Longueur numérique non standard (attendu 8, 12 ou 13 chiffres)"}
    # code128: printable ASCII, reasonable length
    if len(c) > 48 or any(ord(ch) < 32 or ord(ch) > 126 for ch in c):
        return {"valid": False, "symbology": "code128", "normalized": c, "reason": "Caractères non imprimables ou code trop long"}
    return {"valid": True, "symbology": "code128", "normalized": c, "reason": None}


def _barcode_in_use(conn, code: str, exclude_variant_id: Optional[int] = None) -> Optional[str]:
    """Returns a human description of where `code` is already used, or None if free."""
    cur = conn.cursor()
    cur.execute("SELECT id, sku FROM products WHERE barcode = ? AND deleted_at IS NULL", (code,))
    p = cur.fetchone()
    if p:
        return f"produit SKU {p['sku']}"
    if exclude_variant_id is not None:
        cur.execute("SELECT id, sku FROM product_variants WHERE barcode = ? AND id != ?", (code, exclude_variant_id))
    else:
        cur.execute("SELECT id, sku FROM product_variants WHERE barcode = ?", (code,))
    v = cur.fetchone()
    if v:
        return f"variante SKU {v['sku']}"
    return None


def _generate_internal_ean13(conn) -> str:
    """Mints a unique internal EAN-13 under the restricted-distribution prefix 20."""
    cur = conn.cursor()
    for _ in range(50):
        body = _INTERNAL_EAN_PREFIX + "".join(str(secrets.randbelow(10)) for _ in range(10))  # 12 digits
        code = body + str(ean_check_digit(body))
        cur.execute("SELECT 1 FROM products WHERE barcode = ? UNION SELECT 1 FROM product_variants WHERE barcode = ?", (code, code))
        if not cur.fetchone():
            return code
    raise HTTPException(status_code=500, detail="Impossible de générer un code-barres unique, réessayez")


class BarcodeGenerateInput(BaseModel):
    count: int = Field(1, ge=1, le=100)


class BarcodeAssignInput(BaseModel):
    barcode: Optional[str] = Field(None, max_length=64)  # omit to auto-generate an internal EAN-13


@app.get("/api/v1/admin/barcodes/validate")
def admin_validate_barcode(
    code: str = Query(..., min_length=1, max_length=64),
    admin: dict = Depends(require_any_permission(["products:write", "pos:read", "inventory:write"])),
):
    return validate_barcode(code)


@app.post("/api/v1/admin/barcodes/generate")
def admin_generate_barcodes(payload: BarcodeGenerateInput, admin: dict = Depends(require_permission("products:write"))):
    with db_session() as conn:
        codes = [_generate_internal_ean13(conn) for _ in range(payload.count)]
        return {"symbology": "ean13", "internal": True, "barcodes": codes}


@app.post("/api/v1/admin/variants/{variant_id}/assign-barcode")
def admin_assign_variant_barcode(
    variant_id: int,
    payload: BarcodeAssignInput,
    admin: dict = Depends(require_permission("products:write")),
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT id, sku, barcode FROM product_variants WHERE id = ?", (variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variante introuvable")

        if payload.barcode and payload.barcode.strip():
            code = payload.barcode.strip()
            result = validate_barcode(code)
            if not result["valid"]:
                raise HTTPException(status_code=422, detail=f"Code-barres invalide: {result['reason']}")
            code = result["normalized"]
            conflict = _barcode_in_use(conn, code, exclude_variant_id=variant_id)
            if conflict:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Code-barres déjà utilisé par {conflict}")
            symbology = result["symbology"]
            internal = False
        else:
            code = _generate_internal_ean13(conn)
            symbology = "ean13"
            internal = True

        cur.execute("UPDATE product_variants SET barcode = ? WHERE id = ?", (code, variant_id))
        log_audit(conn, int(admin["sub"]), "assign_barcode", "product_variant", str(variant_id), {
            "sku": v["sku"], "barcode": code, "symbology": symbology, "internal": internal,
        })
        return {"variant_id": variant_id, "sku": v["sku"], "barcode": code, "symbology": symbology, "internal": internal}


@app.delete("/api/v1/admin/variants/{variant_id}/barcode")
def admin_clear_variant_barcode(variant_id: int, admin: dict = Depends(require_permission("products:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, sku FROM product_variants WHERE id = ?", (variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variante introuvable")
        cur.execute("UPDATE product_variants SET barcode = NULL WHERE id = ?", (variant_id,))
        log_audit(conn, int(admin["sub"]), "clear_barcode", "product_variant", str(variant_id), {"sku": v["sku"]})
        return {"variant_id": variant_id, "sku": v["sku"], "barcode": None}


@app.get("/api/v1/admin/variants/{variant_id}/label")
def admin_variant_label(
    variant_id: int,
    admin: dict = Depends(require_any_permission(["products:write", "pos:read", "inventory:write"])),
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT pv.id AS variant_id, pv.sku, pv.barcode, pv.title AS variant_title,
                      pv.price_override_dzd, p.name_fr AS product_name, p.selling_price_dzd
               FROM product_variants pv JOIN products p ON p.id = pv.product_id
               WHERE pv.id = ?""",
            (variant_id,),
        )
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Variante introuvable")
        d = dict(r)
        price = int(d["price_override_dzd"]) if d["price_override_dzd"] is not None else int(d["selling_price_dzd"])
        sym = detect_symbology(d["barcode"]) if d["barcode"] else None
        return {
            "store_name": _boutique_info_from_settings(conn)["name"],
            "variant_id": d["variant_id"],
            "product_name": d["product_name"],
            "variant_title": d["variant_title"],
            "sku": d["sku"],
            "barcode": d["barcode"],
            "symbology": sym,
            "price_dzd": price,
            "currency": "DA",
        }

# ============================================================================
# DEVICES & HARDWARE MANAGEMENT
# Honest registry of store peripherals. The cloud API cannot touch a shop's USB
# devices or Windows printers directly — that needs a local bridge. So status is
# never fabricated: it stays 'unknown' until a real signal arrives — a server-side
# TCP probe for network devices, or a result reported by the local bridge / client
# print path for the rest.
# ============================================================================

_DEVICE_TYPES = {"receipt_printer", "label_printer", "barcode_scanner", "cash_drawer", "customer_display", "other"}
_CONNECTION_TYPES = {"usb", "network", "windows", "serial", "hid_keyboard", "browser"}


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    device_type: str
    connection_type: str
    config: Dict[str, Any] = {}
    capabilities: List[str] = []
    location: Optional[str] = Field(None, max_length=120)
    is_default: bool = False

    @validator("device_type")
    def _vt(cls, v):
        if v not in _DEVICE_TYPES:
            raise ValueError(f"device_type invalide. Autorisés: {sorted(_DEVICE_TYPES)}")
        return v

    @validator("connection_type")
    def _vc(cls, v):
        if v not in _CONNECTION_TYPES:
            raise ValueError(f"connection_type invalide. Autorisés: {sorted(_CONNECTION_TYPES)}")
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    location: Optional[str] = Field(None, max_length=120)


class DeviceTestInput(BaseModel):
    # Optional result reported by the local hardware bridge / client print path.
    # Ignored for network devices, which the server probes itself.
    success: Optional[bool] = None
    error: Optional[str] = Field(None, max_length=500)
    capabilities: Optional[List[str]] = None


def _validate_device_config(connection_type: str, config: Dict[str, Any]) -> None:
    if connection_type == "network":
        host = str(config.get("host") or "").strip()
        port = config.get("port")
        if not host:
            raise HTTPException(status_code=422, detail="Un appareil réseau requiert 'host' dans la configuration")
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Un appareil réseau requiert un 'port' numérique")
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=422, detail="Le port doit être compris entre 1 et 65535")
    if connection_type == "windows" and not str(config.get("windows_printer_name") or "").strip():
        # Not fatal, but record intent clearly
        pass


def _tcp_probe(host: str, port: int, timeout: float = 2.0) -> tuple:
    """Real reachability check: attempt a TCP connection. Returns (ok, error)."""
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, None
    except Exception as exc:  # noqa: BLE001 — surface the real reason
        return False, f"{type(exc).__name__}: {exc}"


def _device_payload(row) -> dict:
    d = dict(row)
    try:
        d["config"] = json.loads(d.pop("config_json") or "{}")
    except Exception:
        d["config"] = {}
    try:
        d["capabilities"] = json.loads(d.pop("capabilities_json") or "[]")
    except Exception:
        d["capabilities"] = []
    d["is_default"] = bool(d.get("is_default"))
    return d


@app.get("/api/v1/admin/devices")
def admin_list_devices(admin: dict = Depends(require_permission("devices:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices ORDER BY device_type, is_default DESC, id")
        return {"items": [_device_payload(r) for r in cur.fetchall()]}


@app.post("/api/v1/admin/devices", status_code=201)
def admin_create_device(payload: DeviceCreate, admin: dict = Depends(require_permission("devices:write"))):
    _validate_device_config(payload.connection_type, payload.config)
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO devices (name, device_type, connection_type, config_json, capabilities_json, location, is_default, status)
               VALUES (?, ?, ?, ?, ?, ?, 0, 'unknown')""",
            (payload.name, payload.device_type, payload.connection_type,
             json.dumps(payload.config, ensure_ascii=False), json.dumps(payload.capabilities, ensure_ascii=False),
             payload.location),
        )
        device_id = cur.lastrowid
        if payload.is_default:
            cur.execute("UPDATE devices SET is_default = 0 WHERE device_type = ?", (payload.device_type,))
            cur.execute("UPDATE devices SET is_default = 1 WHERE id = ?", (device_id,))
        log_audit(conn, int(admin["sub"]), "create_device", "device", str(device_id), {
            "name": payload.name, "device_type": payload.device_type, "connection_type": payload.connection_type,
        })
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        return _device_payload(cur.fetchone())


@app.put("/api/v1/admin/devices/{device_id}")
def admin_update_device(device_id: int, payload: DeviceUpdate, admin: dict = Depends(require_permission("devices:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil introuvable")
        if payload.config is not None:
            _validate_device_config(dev["connection_type"], payload.config)
        sets, params = [], []
        if payload.name is not None:
            sets.append("name = ?"); params.append(payload.name)
        if payload.location is not None:
            sets.append("location = ?"); params.append(payload.location)
        if payload.config is not None:
            sets.append("config_json = ?"); params.append(json.dumps(payload.config, ensure_ascii=False))
        if payload.capabilities is not None:
            sets.append("capabilities_json = ?"); params.append(json.dumps(payload.capabilities, ensure_ascii=False))
        if not sets:
            return _device_payload(dev)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(device_id)
        cur.execute(f"UPDATE devices SET {', '.join(sets)} WHERE id = ?", tuple(params))
        log_audit(conn, int(admin["sub"]), "update_device", "device", str(device_id), {"fields": [s.split(' =')[0] for s in sets]})
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        return _device_payload(cur.fetchone())


@app.delete("/api/v1/admin/devices/{device_id}")
def admin_delete_device(device_id: int, admin: dict = Depends(require_permission("devices:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM devices WHERE id = ?", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil introuvable")
        cur.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        log_audit(conn, int(admin["sub"]), "delete_device", "device", str(device_id), {"name": dev["name"]})
        return {"deleted": True, "id": device_id}


@app.post("/api/v1/admin/devices/{device_id}/set-default")
def admin_set_default_device(device_id: int, admin: dict = Depends(require_permission("devices:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT device_type FROM devices WHERE id = ?", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil introuvable")
        cur.execute("UPDATE devices SET is_default = 0 WHERE device_type = ?", (dev["device_type"],))
        cur.execute("UPDATE devices SET is_default = 1 WHERE id = ?", (device_id,))
        log_audit(conn, int(admin["sub"]), "set_default_device", "device", str(device_id), {"device_type": dev["device_type"]})
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        return _device_payload(cur.fetchone())


@app.post("/api/v1/admin/devices/{device_id}/test")
def admin_test_device(device_id: int, payload: DeviceTestInput, admin: dict = Depends(require_permission("devices:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil introuvable")
        config = {}
        try:
            config = json.loads(dev["config_json"] or "{}")
        except Exception:
            config = {}

        status_val = "unknown"
        error = None
        method = None

        if dev["connection_type"] == "network":
            method = "tcp_probe"
            host = str(config.get("host") or "").strip()
            port = config.get("port")
            if not host or port is None:
                status_val, error = "error", "Configuration réseau incomplète (host/port)"
            else:
                ok, probe_err = _tcp_probe(host, int(port))
                status_val = "ok" if ok else "error"
                error = None if ok else f"Connexion impossible à {host}:{port} — {probe_err}"
        elif payload.success is not None:
            # Honest client/bridge-reported result (e.g. Windows print path succeeded).
            method = "client_reported"
            status_val = "ok" if payload.success else "error"
            error = None if payload.success else (payload.error or "Échec rapporté par le poste local")
        else:
            # No real signal available: do not fabricate a status.
            method = "unavailable"
            status_val = "unknown"
            error = ("Ce type d'appareil ne peut pas être testé depuis le cloud. "
                     "Utilisez le pont matériel local ou lancez une impression test depuis le poste.")

        caps_sql = json.dumps(payload.capabilities, ensure_ascii=False) if payload.capabilities is not None else dev["capabilities_json"]
        cur.execute(
            "UPDATE devices SET status = ?, last_error = ?, last_test_at = CURRENT_TIMESTAMP, capabilities_json = ? WHERE id = ?",
            (status_val, error, caps_sql, device_id),
        )
        log_audit(conn, int(admin["sub"]), "test_device", "device", str(device_id), {"method": method, "status": status_val})
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        result = _device_payload(cur.fetchone())
        result["test_method"] = method
        return result

# ============================================================================
# OFFLINE SYNCHRONIZATION — batch replay of POS sales created while offline
# Contract:
#   · Each operation carries a client-generated unique transaction id
#     (client_txn_id) stored as the sale's idempotency key → a sale is NEVER
#     created twice, even if the client retries the whole batch.
#   · Stock is still validated server-side on replay. If the units are no longer
#     available (an online order consumed them), the operation is returned as a
#     'conflict' — never silently dropped, never an oversell.
#   · Offline sales are historical facts, so an open register is NOT required;
#     the sale attaches to its original session if it still exists, else the
#     currently open one, else none (reconciled later).
# Source of truth for stock remains the backend inventory_movements ledger.
# ============================================================================

_ISO_CREATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


class PosSyncOperation(BaseModel):
    client_txn_id: str = Field(..., min_length=8, max_length=128)
    type: str = Field("sale", regex=r"^sale$")
    register_session_id: Optional[int] = None
    created_at_client: Optional[str] = Field(None, max_length=40)
    payload: PosSaleCreate


class PosSyncInput(BaseModel):
    operations: List[PosSyncOperation] = Field(..., min_items=1, max_items=200)


def _process_offline_sale(conn, op: PosSyncOperation, cashier_id: int) -> dict:
    """Idempotently materialize one offline POS sale. Returns a per-op result dict
    with status created | duplicate | conflict (soft, no write) and never raises
    for a business conflict — only for unexpected faults."""
    cur = conn.cursor()
    txn = op.client_txn_id.strip()

    # 1. Idempotency — already synced?
    cur.execute("SELECT id, sale_reference FROM pos_sales WHERE idempotency_key = ?", (txn,))
    dup = cur.fetchone()
    if dup:
        return {"client_txn_id": txn, "status": "duplicate", "sale_reference": dup["sale_reference"], "sale_id": int(dup["id"])}

    payload = op.payload

    # 2. Consolidate lines, validate stock & price server-side
    merged: Dict[int, Dict[str, int]] = {}
    for it in payload.items:
        m = merged.setdefault(it.variant_id, {"quantity": 0, "line_discount_dzd": 0})
        m["quantity"] += int(it.quantity)
        m["line_discount_dzd"] += int(it.line_discount_dzd)

    subtotal_dzd = 0
    total_line_discount = 0
    resolved = []
    for vid, m in merged.items():
        cur.execute(
            """SELECT pv.*, p.name_fr AS product_name, p.selling_price_dzd, p.status AS product_status
               FROM product_variants pv JOIN products p ON p.id = pv.product_id
               WHERE pv.id = ? AND pv.is_active = 1""",
            (vid,),
        )
        v = cur.fetchone()
        if not v or v["product_status"] == "archived":
            return {"client_txn_id": txn, "status": "conflict", "reason": "variant_unavailable",
                    "error": f"Variante {vid} indisponible", "variant_id": vid}
        qty = m["quantity"]
        if v["stock_qty"] < qty:
            return {"client_txn_id": txn, "status": "conflict", "reason": "insufficient_stock",
                    "error": f"Stock insuffisant pour '{v['product_name']} ({v['title']})' : demandé {qty}, dispo {v['stock_qty']}",
                    "variant_id": vid, "available": int(v["stock_qty"]), "requested": qty}
        unit_price = int(v["price_override_dzd"]) if v["price_override_dzd"] is not None else int(v["selling_price_dzd"])
        line_gross = unit_price * qty
        line_discount = min(int(m["line_discount_dzd"]), line_gross)
        subtotal_dzd += line_gross
        total_line_discount += line_discount
        resolved.append((v, qty, unit_price, line_discount, line_gross - line_discount))

    order_discount = min(int(payload.order_discount_dzd), subtotal_dzd - total_line_discount)
    discount_dzd = total_line_discount + order_discount
    net_before_tax = subtotal_dzd - discount_dzd
    tax_percent = _pos_store_tax_percent(conn)
    tax_dzd = (net_before_tax * tax_percent) // 100
    total_dzd = net_before_tax + tax_dzd

    paid = sum(int(pm.amount_dzd) for pm in payload.payments)
    if paid != total_dzd:
        return {"client_txn_id": txn, "status": "conflict", "reason": "payment_mismatch",
                "error": f"Règlements ({paid} DA) ≠ total recalculé ({total_dzd} DA)"}

    # 3. Resolve register session (original → current open → none)
    reg = None
    if op.register_session_id:
        cur.execute("SELECT id FROM cash_register_sessions WHERE id = ?", (op.register_session_id,))
        if cur.fetchone():
            reg = int(op.register_session_id)
    if reg is None:
        open_s = _get_open_register(conn)
        reg = int(open_s["id"]) if open_s else None

    created_at_valid = bool(op.created_at_client and _ISO_CREATED_RE.match(op.created_at_client.strip()))

    # 4. Create the sale (idempotency_key = client txn id)
    sale_ref = ""
    sale_id = None
    for _attempt in range(3):
        sale_ref = f"POS-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
        try:
            if created_at_valid:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, idempotency_key, notes, created_at)
                       VALUES (?, ?, ?, ?, 'sale', ?, ?, ?, ?, 'completed', ?, ?, ?)""",
                    (sale_ref, reg, cashier_id, payload.customer_id, subtotal_dzd, discount_dzd, tax_dzd,
                     total_dzd, txn, payload.notes, op.created_at_client.strip()),
                )
            else:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, idempotency_key, notes)
                       VALUES (?, ?, ?, ?, 'sale', ?, ?, ?, ?, 'completed', ?, ?)""",
                    (sale_ref, reg, cashier_id, payload.customer_id, subtotal_dzd, discount_dzd, tax_dzd,
                     total_dzd, txn, payload.notes),
                )
            sale_id = cur.lastrowid
            break
        except Exception:
            if _attempt == 2:
                raise

    for v, qty, unit_price, line_discount, line_total in resolved:
        cur.execute(
            """INSERT INTO pos_sale_items
               (sale_id, product_id, variant_id, product_name, variant_title, sku,
                unit_price_dzd, line_discount_dzd, quantity, line_total_dzd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sale_id, v["product_id"], v["id"], v["product_name"], v["title"], v["sku"],
             unit_price, line_discount, qty, line_total),
        )
        cur.execute(
            "UPDATE product_variants SET stock_qty = stock_qty - ? WHERE id = ? AND is_active = 1 AND stock_qty >= ?",
            (qty, v["id"], qty),
        )
        if cur.rowcount == 0:
            # Lost a race with a concurrent deduction → surface as conflict (abort this op).
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Stock insuffisant pour '{v['product_name']} ({v['title']})'")
        cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (v["id"],))
        new_qty = int(cur.fetchone()["stock_qty"])
        cur.execute("UPDATE products SET sales_count = sales_count + ? WHERE id = ?", (qty, v["product_id"]))
        cur.execute(
            """INSERT INTO inventory_movements
               (variant_id, pos_sale_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
               VALUES (?, ?, ?, ?, ?, ?, 'pos_sale_offline')""",
            (v["id"], sale_id, cashier_id, -qty, new_qty + qty, new_qty),
        )

    for pm in payload.payments:
        change = 0
        if pm.method == "cash" and pm.tendered_dzd is not None:
            change = max(0, int(pm.tendered_dzd) - int(pm.amount_dzd))
        cur.execute(
            "INSERT INTO pos_payments (sale_id, method, amount_dzd, tendered_dzd, change_dzd) VALUES (?, ?, ?, ?, ?)",
            (sale_id, pm.method, int(pm.amount_dzd), pm.tendered_dzd, change),
        )

    log_audit(conn, cashier_id, "pos_sale_offline_sync", "pos_sale", str(sale_id), {
        "client_txn_id": txn, "sale_reference": sale_ref, "total_dzd": total_dzd,
    })
    return {"client_txn_id": txn, "status": "created", "sale_reference": sale_ref, "sale_id": int(sale_id), "total_dzd": total_dzd}


# ============================================================================
# BUSINESS DASHBOARD — unified overview across in-store (POS) and online sales.
# Every figure is computed from real records (orders, pos_sales, variants,
# devices, purchase_orders, expenses). Revenue, gross margin and net profit are
# reported as distinct numbers and never presented as interchangeable.
# ============================================================================

# Unit cost expression shared by COGS/valuation queries (variant cost, else product cost).
_UNIT_COST_SQL = "COALESCE(pv.purchase_cost_dzd, p.purchase_cost_dzd, 0)"


def _scalar(cur, sql: str, params=(), key: str = "v") -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    return int(row[key]) if row and row[key] is not None else 0


@app.get("/api/v1/admin/dashboard/business")
def admin_business_dashboard(admin: dict = Depends(require_permission("dashboard:read"))):
    now = datetime.now(timezone.utc)
    today_start = now.strftime("%Y-%m-%d 00:00:00")
    month_start = now.strftime("%Y-%m-01 00:00:00")
    month_start_date = now.strftime("%Y-%m-01")

    with db_session() as conn:
        cur = conn.cursor()

        def online(period_clause: str, params=()):
            cur.execute(
                f"SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS r FROM orders WHERE status != 'cancelled' {period_clause}",
                params,
            )
            row = cur.fetchone()
            return {"count": int(row["c"]), "revenue_dzd": int(row["r"])}

        def instore(sale_type: str, period_clause: str, params=()):
            cur.execute(
                f"SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS r FROM pos_sales WHERE sale_type = ? {period_clause}",
                (sale_type, *params),
            )
            row = cur.fetchone()
            return {"count": int(row["c"]), "revenue_dzd": int(row["r"])}

        sales = {
            "online": {
                "today": online("AND created_at >= ?", (today_start,)),
                "month": online("AND created_at >= ?", (month_start,)),
                "all": online(""),
            },
            "in_store": {
                "today": instore("sale", "AND created_at >= ?", (today_start,)),
                "month": instore("sale", "AND created_at >= ?", (month_start,)),
                "all": instore("sale", ""),
            },
            "in_store_refunds": {
                "today_dzd": instore("refund", "AND created_at >= ?", (today_start,))["revenue_dzd"],
                "month_dzd": instore("refund", "AND created_at >= ?", (month_start,))["revenue_dzd"],
            },
        }
        sales["combined"] = {
            "today_revenue_dzd": sales["online"]["today"]["revenue_dzd"] + sales["in_store"]["today"]["revenue_dzd"] - sales["in_store_refunds"]["today_dzd"],
            "month_revenue_dzd": sales["online"]["month"]["revenue_dzd"] + sales["in_store"]["month"]["revenue_dzd"] - sales["in_store_refunds"]["month_dzd"],
        }

        online_aov = (sales["online"]["month"]["revenue_dzd"] // sales["online"]["month"]["count"]) if sales["online"]["month"]["count"] else 0
        ticket = (sales["in_store"]["month"]["revenue_dzd"] // sales["in_store"]["month"]["count"]) if sales["in_store"]["month"]["count"] else 0

        # --- Gross margin (month): net revenue minus COGS of sold units ---
        online_cogs = _scalar(cur,
            f"""SELECT COALESCE(SUM(oi.quantity * {_UNIT_COST_SQL}),0) AS v
                FROM order_items oi JOIN orders o ON o.id = oi.order_id
                JOIN product_variants pv ON pv.id = oi.variant_id
                JOIN products p ON p.id = pv.product_id
                WHERE o.status != 'cancelled' AND o.created_at >= ?""", (month_start,))
        instore_sale_cogs = _scalar(cur,
            f"""SELECT COALESCE(SUM(psi.quantity * {_UNIT_COST_SQL}),0) AS v
                FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                JOIN product_variants pv ON pv.id = psi.variant_id
                JOIN products p ON p.id = pv.product_id
                WHERE ps.sale_type = 'sale' AND ps.created_at >= ?""", (month_start,))
        instore_refund_cogs = _scalar(cur,
            f"""SELECT COALESCE(SUM(psi.quantity * {_UNIT_COST_SQL}),0) AS v
                FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                JOIN product_variants pv ON pv.id = psi.variant_id
                JOIN products p ON p.id = pv.product_id
                WHERE ps.sale_type = 'refund' AND ps.created_at >= ?""", (month_start,))

        revenue_month = sales["combined"]["month_revenue_dzd"]
        cogs_month = online_cogs + instore_sale_cogs - instore_refund_cogs
        gross_margin = revenue_month - cogs_month
        opex_month = _scalar(cur, "SELECT COALESCE(SUM(amount_dzd),0) AS v FROM expenses WHERE expense_date >= ?", (month_start_date,))
        margin_pct = round((gross_margin / revenue_month) * 100, 1) if revenue_month > 0 else 0.0

        margin_month = {
            "revenue_dzd": revenue_month,
            "cogs_dzd": cogs_month,
            "gross_margin_dzd": gross_margin,
            "gross_margin_percent": margin_pct,
            "operating_expenses_dzd": opex_month,
            "net_profit_dzd": gross_margin - opex_month,
        }

        # --- Inventory valuation + stock health ---
        cur.execute(
            f"""SELECT COALESCE(SUM(pv.stock_qty * {_UNIT_COST_SQL}),0) AS cost,
                       COALESCE(SUM(pv.stock_qty * COALESCE(pv.price_override_dzd, p.selling_price_dzd, 0)),0) AS retail
                FROM product_variants pv JOIN products p ON p.id = pv.product_id
                WHERE pv.is_active = 1 AND p.deleted_at IS NULL"""
        )
        val = cur.fetchone()
        inventory = {
            "valuation_cost_dzd": int(val["cost"]),
            "valuation_retail_dzd": int(val["retail"]),
            "low_stock_count": _scalar(cur, "SELECT COUNT(*) AS v FROM product_variants WHERE is_active=1 AND stock_qty > 0 AND stock_qty <= low_stock_threshold"),
            "out_of_stock_count": _scalar(cur, "SELECT COUNT(*) AS v FROM product_variants WHERE is_active=1 AND stock_qty = 0"),
        }
        cur.execute(
            """SELECT pv.id AS variant_id, pv.sku, pv.title AS variant_title, pv.stock_qty, pv.low_stock_threshold, p.name_fr AS product_name
               FROM product_variants pv JOIN products p ON p.id = pv.product_id
               WHERE pv.is_active = 1 AND p.deleted_at IS NULL AND pv.stock_qty <= pv.low_stock_threshold
               ORDER BY pv.stock_qty ASC, pv.id LIMIT 10"""
        )
        low_stock = [dict(r) for r in cur.fetchall()]

        # --- Cash register ---
        open_session = _get_open_register(conn)
        cash_register = {"open": bool(open_session), "session": None}
        if open_session:
            sd = dict(open_session)
            totals = _register_runtime_totals(conn, sd["id"])
            sd.update(totals)
            sd["expected_cash_dzd"] = int(sd["opening_float_dzd"]) + totals["net_cash_dzd"]
            cash_register["session"] = sd

        # --- Device health ---
        devices_health = {"total": 0, "ok": 0, "error": 0, "offline": 0, "unknown": 0}
        cur.execute("SELECT status, COUNT(*) AS c FROM devices GROUP BY status")
        for r in cur.fetchall():
            devices_health[r["status"]] = int(r["c"])
            devices_health["total"] += int(r["c"])

        # --- Operations ---
        operations = {
            "pending_orders": _scalar(cur, "SELECT COUNT(*) AS v FROM orders WHERE status IN ('new','pending_confirmation','confirmed')"),
            "pending_deliveries": _scalar(cur, "SELECT COUNT(*) AS v FROM orders WHERE status IN ('preparing','ready_for_shipment','shipped')"),
            "supplier_outstanding_dzd": _scalar(cur, "SELECT COALESCE(SUM(total_cost_dzd - paid_amount_dzd),0) AS v FROM purchase_orders WHERE status NOT IN ('draft','cancelled') AND total_cost_dzd > paid_amount_dzd"),
        }

        # --- Best sellers across both channels ---
        cur.execute(
            """SELECT variant_id, product_name, sku, SUM(q) AS qty FROM (
                 SELECT variant_id, product_name, sku, quantity AS q
                 FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status != 'cancelled'
                 UNION ALL
                 SELECT variant_id, product_name, sku, quantity AS q
                 FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id WHERE ps.sale_type = 'sale'
               ) GROUP BY variant_id ORDER BY qty DESC LIMIT 8"""
        )
        best_sellers = [{"variant_id": r["variant_id"], "product_name": r["product_name"], "sku": r["sku"], "qty_sold": int(r["qty"])} for r in cur.fetchall()]

        return {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period": {"today_start": today_start, "month_start": month_start},
            "sales": sales,
            "averages": {"online_aov_dzd": online_aov, "in_store_ticket_dzd": ticket},
            "margin_month": margin_month,
            "inventory": inventory,
            "low_stock": low_stock,
            "cash_register": cash_register,
            "devices": devices_health,
            "operations": operations,
            "best_sellers": best_sellers,
        }


@app.post("/api/v1/admin/pos/sync")
def pos_offline_sync(payload: PosSyncInput, admin: dict = Depends(require_permission("pos:sell"))):
    results = []
    for op in payload.operations:
        try:
            with db_session(commit=True) as conn:
                if not conn.in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                results.append(_process_offline_sale(conn, op, int(admin["sub"])))
        except HTTPException as he:
            results.append({"client_txn_id": op.client_txn_id, "status": "conflict", "reason": "server_rejected", "error": he.detail})
        except Exception as exc:  # noqa: BLE001
            results.append({"client_txn_id": op.client_txn_id, "status": "failed", "error": str(exc)})

    summary = {"created": 0, "duplicate": 0, "conflict": 0, "failed": 0}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"results": results, "summary": summary, "synced_count": len(payload.operations)}

# ============================================================================
# USERS, ROLES & PERMISSIONS — multi-user retail staff management
# Only holders of settings:write (the owner / super admin) can manage staff.
# Permissions are enforced on the backend; the UI only reflects them. Guards
# protect against locking the business out (last active super admin, self
# deactivation). Role, status and password changes revoke the target's sessions
# so they take effect immediately, and every change is written to the audit log.
# ============================================================================

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdminUserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=32)
    role_id: int
    password: str = Field(..., min_length=10, max_length=128)

    @validator("email")
    def _email(cls, v):
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Adresse e-mail invalide")
        return v


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=32)
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=10, max_length=128)


def _role_name(conn, role_id: int) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM roles WHERE id = ?", (role_id,))
    r = cur.fetchone()
    return r["name"] if r else None


def _count_other_active_super_admins(conn, exclude_user_id: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(*) AS c FROM admin_users u JOIN roles r ON r.id = u.role_id
           WHERE r.name = 'super_admin' AND u.is_active = 1 AND u.id != ?""",
        (exclude_user_id,),
    )
    return int(cur.fetchone()["c"])


@app.get("/api/v1/admin/roles")
def admin_list_roles(admin: dict = Depends(require_permission("settings:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description FROM roles ORDER BY id")
        roles = [dict(r) for r in cur.fetchall()]
        for role in roles:
            cur.execute(
                """SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id
                   WHERE rp.role_id = ? ORDER BY p.code""",
                (role["id"],),
            )
            role["permissions"] = [r["code"] for r in cur.fetchall()]
        return {"items": roles}


@app.get("/api/v1/admin/users")
def admin_list_users(admin: dict = Depends(require_permission("settings:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, u.last_login_at, u.created_at,
                      r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id
               ORDER BY u.id"""
        )
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.post("/api/v1/admin/users", status_code=201)
def admin_create_user(payload: AdminUserCreate, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        if not _role_name(conn, payload.role_id):
            raise HTTPException(status_code=404, detail="Rôle introuvable")
        cur.execute("SELECT id FROM admin_users WHERE email = ?", (payload.email,))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un utilisateur avec cet e-mail existe déjà")
        cur.execute(
            """INSERT INTO admin_users (email, full_name, phone, password_hash, role_id, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (payload.email, payload.full_name, payload.phone, hash_password(payload.password), payload.role_id),
        )
        uid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_admin_user", "admin_user", str(uid), {
            "email": payload.email, "role_id": payload.role_id,
        })
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, u.created_at, r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
            (uid,),
        )
        return dict(cur.fetchone())


@app.put("/api/v1/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUserUpdate, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute(
            "SELECT u.*, r.name AS role_name FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        is_self = int(admin["sub"]) == user_id
        was_super = user["role_name"] == "super_admin"

        # Resolve target role & active state after the update
        new_role_id = payload.role_id if payload.role_id is not None else user["role_id"]
        new_active = payload.is_active if payload.is_active is not None else bool(user["is_active"])
        new_role_name = _role_name(conn, new_role_id)
        if new_role_name is None:
            raise HTTPException(status_code=404, detail="Rôle introuvable")

        # Guard: never lock the business out of its last active super admin.
        if was_super and (new_role_name != "super_admin" or not new_active):
            if _count_other_active_super_admins(conn, user_id) == 0:
                raise HTTPException(status_code=400, detail="Impossible : c'est le dernier super administrateur actif")
        # Guard: an admin cannot deactivate their own account.
        if is_self and payload.is_active is False:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")

        sets, params = [], []
        if payload.full_name is not None:
            sets.append("full_name = ?"); params.append(payload.full_name)
        if payload.phone is not None:
            sets.append("phone = ?"); params.append(payload.phone)
        if payload.role_id is not None:
            sets.append("role_id = ?"); params.append(payload.role_id)
        if payload.is_active is not None:
            sets.append("is_active = ?"); params.append(1 if payload.is_active else 0)
        if not sets:
            cur.execute(
                """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, r.id AS role_id, r.name AS role_name
                   FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
            return dict(cur.fetchone())
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        cur.execute(f"UPDATE admin_users SET {', '.join(sets)} WHERE id = ?", tuple(params))

        # Role/status changes take effect immediately: revoke the target's sessions.
        if payload.role_id is not None or payload.is_active is not None:
            revoke_all_user_sessions(user_id, conn)
        log_audit(conn, int(admin["sub"]), "update_admin_user", "admin_user", str(user_id), {
            "role_id": new_role_id, "is_active": new_active,
        })
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
        return dict(cur.fetchone())


@app.post("/api/v1/admin/users/{user_id}/reset-password")
def admin_reset_user_password(user_id: int, payload: AdminPasswordReset, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM admin_users WHERE id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (hash_password(payload.new_password), user_id),
        )
        revoke_all_user_sessions(user_id, conn)
        log_audit(conn, int(admin["sub"]), "reset_admin_password", "admin_user", str(user_id), {"email": user["email"]})
        return {"id": user_id, "email": user["email"], "password_reset": True}

# ============================================================================
# CUSTOMER MANAGEMENT — walk-in and registered customers, cross-channel history
# Customers are shared between the online store and the POS. A POS cashier can
# create a walk-in customer with just a name and phone; online orders keep
# collecting the delivery details. History combines online orders and in-store
# sales. Privacy: only the fields the business needs are stored.
# ============================================================================

_CUSTOMER_MANAGE = require_any_permission(["orders:write", "pos:sell"])


class CustomerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    phone: str = Field(..., min_length=6, max_length=32)
    email: Optional[str] = Field(None, max_length=255)
    wilaya_code: Optional[str] = Field(None, max_length=4)
    commune: Optional[str] = Field(None, max_length=120)
    address: Optional[str] = None
    notes: Optional[str] = None

    @validator("phone")
    def _clean_phone(cls, v):
        return re.sub(r"[\s\-\.]", "", v.strip())

    @validator("email")
    def _email(cls, v):
        if v and not _EMAIL_RE.match(v.strip().lower()):
            raise ValueError("Adresse e-mail invalide")
        return v.strip().lower() if v else v


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=160)
    email: Optional[str] = Field(None, max_length=255)
    wilaya_code: Optional[str] = Field(None, max_length=4)
    commune: Optional[str] = Field(None, max_length=120)
    address: Optional[str] = None
    notes: Optional[str] = None

    @validator("email")
    def _email_u(cls, v):
        if v and not _EMAIL_RE.match(v.strip().lower()):
            raise ValueError("Adresse e-mail invalide")
        return v.strip().lower() if v else v


def _customer_totals_and_history(conn, customer_id: int) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS s FROM orders WHERE customer_id = ? AND status != 'cancelled'", (customer_id,))
    on = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS s FROM pos_sales WHERE customer_id = ? AND sale_type = 'sale'", (customer_id,))
    ins = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(total_dzd),0) AS s FROM pos_sales WHERE customer_id = ? AND sale_type = 'refund'", (customer_id,))
    refund_s = int(cur.fetchone()["s"])

    history = []
    cur.execute("SELECT order_reference AS ref, total_dzd, status, created_at FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 50", (customer_id,))
    for r in cur.fetchall():
        history.append({"channel": "online", "reference": r["ref"], "total_dzd": int(r["total_dzd"]), "status": r["status"], "created_at": r["created_at"]})
    cur.execute("SELECT sale_reference AS ref, total_dzd, status, sale_type, created_at FROM pos_sales WHERE customer_id = ? ORDER BY id DESC LIMIT 50", (customer_id,))
    for r in cur.fetchall():
        history.append({"channel": "in_store", "reference": r["ref"], "total_dzd": int(r["total_dzd"]), "status": r["status"], "sale_type": r["sale_type"], "created_at": r["created_at"]})
    history.sort(key=lambda h: str(h["created_at"]), reverse=True)

    online_spent = int(on["s"])
    instore_spent = int(ins["s"]) - refund_s
    return {
        "totals": {
            "online_orders": int(on["c"]),
            "online_spent_dzd": online_spent,
            "in_store_sales": int(ins["c"]),
            "in_store_spent_dzd": instore_spent,
            "combined_spent_dzd": online_spent + instore_spent,
        },
        "history": history[:50],
    }


@app.get("/api/v1/admin/customers/search")
def admin_search_customers(q: str = Query(..., min_length=1, max_length=120), admin: dict = Depends(_CUSTOMER_MANAGE)):
    like = f"%{q.strip()}%"
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, full_name, phone, email, wilaya_code, commune, orders_count, total_spent_dzd
               FROM customers WHERE full_name LIKE ? OR phone LIKE ? ORDER BY total_spent_dzd DESC, id DESC LIMIT 20""",
            (like, like),
        )
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.get("/api/v1/admin/customers/{customer_id}")
def admin_get_customer(customer_id: int, admin: dict = Depends(_CUSTOMER_MANAGE)):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Client introuvable")
        data = dict(c)
        data.update(_customer_totals_and_history(conn, customer_id))
        return data


@app.post("/api/v1/admin/customers", status_code=201)
def admin_create_customer(payload: CustomerCreate, admin: dict = Depends(_CUSTOMER_MANAGE)):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT id, full_name FROM customers WHERE phone = ?", (payload.phone,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Un client existe déjà avec ce numéro ({existing['full_name']}, #{existing['id']})",
            )
        cur.execute(
            """INSERT INTO customers (full_name, phone, email, wilaya_code, commune, address, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (payload.full_name, payload.phone, payload.email, payload.wilaya_code or "", payload.commune or "", payload.address or "", payload.notes),
        )
        cid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_customer", "customer", str(cid), {"full_name": payload.full_name, "phone": payload.phone})
        cur.execute("SELECT * FROM customers WHERE id = ?", (cid,))
        return dict(cur.fetchone())


@app.put("/api/v1/admin/customers/{customer_id}")
def admin_update_customer(customer_id: int, payload: CustomerUpdate, admin: dict = Depends(require_permission("orders:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Client introuvable")
        sets, params = [], []
        for field in ("full_name", "email", "wilaya_code", "commune", "address", "notes"):
            val = getattr(payload, field)
            if val is not None:
                sets.append(f"{field} = ?"); params.append(val)
        if not sets:
            cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
            return dict(cur.fetchone())
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(customer_id)
        cur.execute(f"UPDATE customers SET {', '.join(sets)} WHERE id = ?", tuple(params))
        log_audit(conn, int(admin["sub"]), "update_customer", "customer", str(customer_id), {"fields": [s.split(' =')[0] for s in sets if '=' in s]})
        cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        return dict(cur.fetchone())

# ============================================================================
# INVENTORY COUNTS — physical stock-taking & reconciliation
# The cashier scans / types SKUs; the system compares each counted quantity to
# the current system stock and shows the variance. Applying the session writes
# real variance movements to inventory_movements (completed sales are never
# edited; the delta is a proper 'physical_count_reconcile' event). Overlapping
# sales between counting and applying are handled: the variance is recomputed
# against the stock at apply time to avoid double-counting.
# ============================================================================


class CountOpenInput(BaseModel):
    name: Optional[str] = Field("Inventaire", max_length=160)
    notes: Optional[str] = Field(None, max_length=1000)


class CountLineInput(BaseModel):
    variant_id: int
    counted_qty: int = Field(..., ge=0, le=1_000_000)


def _recompute_count_totals(conn, count_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        """UPDATE inventory_counts
           SET total_lines = (SELECT COUNT(*) FROM inventory_count_items WHERE count_id = ?),
               total_variance_abs = (
                 SELECT COALESCE(SUM(ABS(counted_qty - expected_qty)), 0)
                 FROM inventory_count_items WHERE count_id = ?
               )
           WHERE id = ?""",
        (count_id, count_id, count_id),
    )


def _count_payload(conn, count_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """SELECT ic.*, ao.full_name AS opened_by_name, aa.full_name AS applied_by_name
           FROM inventory_counts ic
           LEFT JOIN admin_users ao ON ao.id = ic.opened_by_admin_id
           LEFT JOIN admin_users aa ON aa.id = ic.applied_by_admin_id
           WHERE ic.id = ?""",
        (count_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Inventaire introuvable")
    data = dict(row)
    cur.execute(
        """SELECT ici.*, pv.sku, pv.title AS variant_title, pv.stock_qty AS current_stock_qty,
                  p.name_fr AS product_name
           FROM inventory_count_items ici
           JOIN product_variants pv ON pv.id = ici.variant_id
           JOIN products p ON p.id = pv.product_id
           WHERE ici.count_id = ? ORDER BY ici.id""",
        (count_id,),
    )
    items = []
    for r in cur.fetchall():
        d = dict(r)
        d["variance"] = int(d["counted_qty"]) - int(d["expected_qty"])
        items.append(d)
    data["items"] = items
    return data


@app.get("/api/v1/admin/inventory/counts")
def admin_list_counts(
    limit: int = Query(30, ge=1, le=200),
    admin: dict = Depends(require_permission("inventory:write")),
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory_counts ORDER BY id DESC LIMIT ?", (limit,))
        return {"items": [dict(r) for r in cur.fetchall()]}


@app.post("/api/v1/admin/inventory/counts", status_code=201)
def admin_open_count(payload: CountOpenInput, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        ref = ""
        count_id = None
        for _attempt in range(3):
            ref = f"INV-{int(time.time()) % 100000:05d}-{secrets.token_hex(2).upper()}"
            try:
                cur.execute(
                    """INSERT INTO inventory_counts (reference, name, opened_by_admin_id, notes)
                       VALUES (?, ?, ?, ?)""",
                    (ref, payload.name or "Inventaire", int(admin["sub"]), payload.notes),
                )
                count_id = cur.lastrowid
                break
            except Exception:
                if _attempt == 2:
                    raise
        log_audit(conn, int(admin["sub"]), "open_inventory_count", "inventory_count", str(count_id), {"reference": ref})
        return _count_payload(conn, int(count_id))


@app.get("/api/v1/admin/inventory/counts/{count_id}")
def admin_get_count(count_id: int, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session() as conn:
        return _count_payload(conn, count_id)


@app.put("/api/v1/admin/inventory/counts/{count_id}/lines")
def admin_upsert_count_line(
    count_id: int,
    payload: CountLineInput,
    admin: dict = Depends(require_permission("inventory:write")),
):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT status FROM inventory_counts WHERE id = ?", (count_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")
        if c["status"] != "open":
            raise HTTPException(status_code=409, detail=f"Inventaire {c['status']} — lignes non modifiables")
        cur.execute(
            "SELECT pv.stock_qty, pv.sku FROM product_variants pv WHERE pv.id = ? AND pv.is_active = 1",
            (payload.variant_id,),
        )
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variante introuvable ou inactive")
        expected = int(v["stock_qty"])
        # Upsert: a new scan of the same SKU adds to the previous count (cashier scanned twice).
        cur.execute(
            "SELECT id, counted_qty FROM inventory_count_items WHERE count_id = ? AND variant_id = ?",
            (count_id, payload.variant_id),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """UPDATE inventory_count_items
                   SET counted_qty = counted_qty + ?, counted_at = CURRENT_TIMESTAMP, expected_qty = ?
                   WHERE id = ?""",
                (payload.counted_qty, expected, existing["id"]),
            )
        else:
            cur.execute(
                """INSERT INTO inventory_count_items (count_id, variant_id, expected_qty, counted_qty)
                   VALUES (?, ?, ?, ?)""",
                (count_id, payload.variant_id, expected, payload.counted_qty),
            )
        _recompute_count_totals(conn, count_id)
        return _count_payload(conn, count_id)


@app.delete("/api/v1/admin/inventory/counts/{count_id}/lines/{line_id}")
def admin_delete_count_line(
    count_id: int,
    line_id: int,
    admin: dict = Depends(require_permission("inventory:write")),
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM inventory_counts WHERE id = ?", (count_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")
        if c["status"] != "open":
            raise HTTPException(status_code=409, detail="Inventaire déjà appliqué")
        cur.execute("DELETE FROM inventory_count_items WHERE id = ? AND count_id = ?", (line_id, count_id))
        _recompute_count_totals(conn, count_id)
        return _count_payload(conn, count_id)


@app.post("/api/v1/admin/inventory/counts/{count_id}/apply")
def admin_apply_count(count_id: int, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory_counts WHERE id = ?", (count_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")
        if c["status"] != "open":
            raise HTTPException(status_code=409, detail=f"Inventaire déjà {c['status']}")
        cur.execute(
            "SELECT id, variant_id, counted_qty FROM inventory_count_items WHERE count_id = ?",
            (count_id,),
        )
        lines = [dict(r) for r in cur.fetchall()]
        if not lines:
            raise HTTPException(status_code=400, detail="Aucune ligne à appliquer")

        applied = 0
        for line in lines:
            # Re-read stock inside the transaction to compute the delta vs the LIVE
            # stock (sales may have happened between counting and applying). This
            # guarantees stock becomes exactly the counted value without double-
            # counting intermediate sales.
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (line["variant_id"],))
            v = cur.fetchone()
            if not v:
                continue
            prev_q = int(v["stock_qty"])
            new_q = int(line["counted_qty"])
            delta = new_q - prev_q
            if delta == 0:
                continue
            cur.execute("UPDATE product_variants SET stock_qty = ? WHERE id = ?", (new_q, line["variant_id"]))
            cur.execute(
                """INSERT INTO inventory_movements
                   (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
                   VALUES (?, ?, ?, ?, ?, 'physical_count_reconcile')""",
                (line["variant_id"], int(admin["sub"]), delta, prev_q, new_q),
            )
            applied += 1

        cur.execute(
            """UPDATE inventory_counts
               SET status = 'applied', applied_by_admin_id = ?, applied_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status = 'open'""",
            (int(admin["sub"]), count_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=409, detail="Inventaire déjà appliqué")
        log_audit(conn, int(admin["sub"]), "apply_inventory_count", "inventory_count", str(count_id), {
            "reference": c["reference"], "lines_applied": applied, "lines_total": len(lines),
        })
        return _count_payload(conn, count_id)


# ============================================================================
# STOCK WRITE-OFFS — typed, audit-trailed adjustments for damage, loss or
# supplier returns. Unlike the generic /variants/{id}/adjust-stock these carry
# a strict reason so reporting, shrinkage analysis and audit stay clean. Writes
# a real movement to inventory_movements and never edits past sales.
# ============================================================================

_WRITEOFF_REASONS = {"damaged", "lost", "return_to_supplier", "promotional_giveaway", "stocktake_correction"}


class WriteOffInput(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0, le=1_000_000)
    reason: str
    notes: Optional[str] = Field(None, max_length=500)

    @validator("reason")
    def _reason(cls, v):
        if v not in _WRITEOFF_REASONS:
            raise ValueError(f"Motif invalide. Autorisés: {sorted(_WRITEOFF_REASONS)}")
        return v


@app.get("/api/v1/admin/inventory/write-off-reasons")
def admin_writeoff_reasons(admin: dict = Depends(require_permission("inventory:write"))):
    labels = {
        "damaged": "Produit endommagé",
        "lost": "Perte / vol",
        "return_to_supplier": "Retour fournisseur",
        "promotional_giveaway": "Cadeau / promo",
        "stocktake_correction": "Correction d'inventaire",
    }
    return {"items": [{"code": c, "label": labels[c]} for c in sorted(_WRITEOFF_REASONS)]}


@app.post("/api/v1/admin/inventory/write-off", status_code=201)
def admin_stock_write_off(payload: WriteOffInput, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute("SELECT id, sku, stock_qty FROM product_variants WHERE id = ?", (payload.variant_id,))
        v = cur.fetchone()
        if not v:
            raise HTTPException(status_code=404, detail="Variante introuvable")
        if int(v["stock_qty"]) < payload.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuffisant ({v['stock_qty']} dispo, {payload.quantity} demandé)",
            )
        # Atomic deduct
        cur.execute(
            "UPDATE product_variants SET stock_qty = stock_qty - ? WHERE id = ? AND stock_qty >= ?",
            (payload.quantity, payload.variant_id, payload.quantity),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock a changé, réessayez")
        cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (payload.variant_id,))
        new_q = int(cur.fetchone()["stock_qty"])
        prev_q = new_q + payload.quantity
        cur.execute(
            """INSERT INTO inventory_movements
               (variant_id, admin_user_id, change_qty, previous_qty, new_qty, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (payload.variant_id, int(admin["sub"]), -payload.quantity, prev_q, new_q, f"writeoff_{payload.reason}"),
        )
        log_audit(conn, int(admin["sub"]), "stock_write_off", "product_variant", str(payload.variant_id), {
            "sku": v["sku"], "quantity": payload.quantity, "reason": payload.reason,
            "previous_qty": prev_q, "new_qty": new_q, "notes": payload.notes or "",
        })
        return {
            "variant_id": payload.variant_id, "sku": v["sku"],
            "previous_qty": prev_q, "new_qty": new_q,
            "reason": payload.reason, "quantity": payload.quantity,
        }


# ============================================================================
# SALES REPORTS — date-ranged reporting for the owner/accountant.
# All figures are derived from real records (orders + pos_sales/items).
# Revenue is net of in-store refunds. Online cancelled orders are excluded.
# ============================================================================

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date_or_422(s: str, field: str) -> str:
    if not s or not _DATE_RE.match(s):
        raise HTTPException(status_code=422, detail=f"{field}: date attendue au format YYYY-MM-DD")
    return s


def _sales_report_data(conn, date_from: str, date_to: str) -> dict:
    cur = conn.cursor()
    start = f"{date_from} 00:00:00"
    end = f"{date_to} 23:59:59"

    # Per-day online revenue & count
    cur.execute(
        """SELECT substr(created_at, 1, 10) AS day,
                  COUNT(*) AS c, COALESCE(SUM(total_dzd), 0) AS r
           FROM orders
           WHERE status != 'cancelled' AND created_at BETWEEN ? AND ?
           GROUP BY day ORDER BY day""",
        (start, end),
    )
    online_by_day = {r["day"]: {"count": int(r["c"]), "revenue_dzd": int(r["r"])} for r in cur.fetchall()}

    # Per-day in-store (sales minus refunds)
    cur.execute(
        """SELECT substr(created_at, 1, 10) AS day, sale_type,
                  COUNT(*) AS c, COALESCE(SUM(total_dzd), 0) AS r
           FROM pos_sales
           WHERE created_at BETWEEN ? AND ?
           GROUP BY day, sale_type ORDER BY day""",
        (start, end),
    )
    instore_by_day: Dict[str, Dict[str, int]] = {}
    for r in cur.fetchall():
        d = instore_by_day.setdefault(r["day"], {"sales_count": 0, "sales_revenue_dzd": 0, "refunds_dzd": 0, "refunds_count": 0})
        if r["sale_type"] == "sale":
            d["sales_count"] += int(r["c"])
            d["sales_revenue_dzd"] += int(r["r"])
        else:
            d["refunds_count"] += int(r["c"])
            d["refunds_dzd"] += int(r["r"])

    # Union of days
    days = sorted(set(online_by_day.keys()) | set(instore_by_day.keys()))
    by_day = []
    totals = {
        "online_count": 0, "online_revenue_dzd": 0,
        "in_store_count": 0, "in_store_revenue_dzd": 0,
        "in_store_refunds_dzd": 0, "in_store_refunds_count": 0,
        "net_revenue_dzd": 0,
    }
    for d in days:
        o = online_by_day.get(d, {"count": 0, "revenue_dzd": 0})
        s = instore_by_day.get(d, {"sales_count": 0, "sales_revenue_dzd": 0, "refunds_dzd": 0, "refunds_count": 0})
        net = o["revenue_dzd"] + s["sales_revenue_dzd"] - s["refunds_dzd"]
        by_day.append({
            "day": d,
            "online_count": o["count"],
            "online_revenue_dzd": o["revenue_dzd"],
            "in_store_count": s["sales_count"],
            "in_store_revenue_dzd": s["sales_revenue_dzd"],
            "in_store_refunds_dzd": s["refunds_dzd"],
            "in_store_refunds_count": s["refunds_count"],
            "net_revenue_dzd": net,
        })
        for k in ("online_count", "online_revenue_dzd", "in_store_count", "in_store_revenue_dzd",
                 "in_store_refunds_dzd", "in_store_refunds_count", "net_revenue_dzd"):
            totals[k] += by_day[-1][k] if k != "net_revenue_dzd" else net
        totals["net_revenue_dzd"] += 0  # already added above (safe no-op)

    # Recompute net total cleanly from parts (avoid the double-add above)
    totals["net_revenue_dzd"] = totals["online_revenue_dzd"] + totals["in_store_revenue_dzd"] - totals["in_store_refunds_dzd"]

    # Top products across both channels
    cur.execute(
        """SELECT variant_id, product_name, sku, SUM(q) AS qty, SUM(r) AS rev FROM (
             SELECT oi.variant_id, oi.product_name, oi.sku, oi.quantity AS q, oi.line_total_dzd AS r
             FROM order_items oi JOIN orders o ON o.id = oi.order_id
             WHERE o.status != 'cancelled' AND o.created_at BETWEEN ? AND ?
             UNION ALL
             SELECT psi.variant_id, psi.product_name, psi.sku, psi.quantity AS q, psi.line_total_dzd AS r
             FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
             WHERE ps.sale_type = 'sale' AND ps.created_at BETWEEN ? AND ?
           ) GROUP BY variant_id ORDER BY qty DESC LIMIT 20""",
        (start, end, start, end),
    )
    top_products = [{"variant_id": r["variant_id"], "product_name": r["product_name"], "sku": r["sku"],
                     "qty_sold": int(r["qty"]), "revenue_dzd": int(r["rev"])} for r in cur.fetchall()]

    # Payment-method breakdown (in-store only — online is always COD)
    cur.execute(
        """SELECT pp.method, COUNT(*) AS c, COALESCE(SUM(CASE WHEN ps.sale_type = 'sale' THEN pp.amount_dzd ELSE -pp.amount_dzd END), 0) AS total
           FROM pos_payments pp JOIN pos_sales ps ON ps.id = pp.sale_id
           WHERE ps.created_at BETWEEN ? AND ?
           GROUP BY pp.method""",
        (start, end),
    )
    payment_breakdown = [{"method": r["method"], "count": int(r["c"]), "net_dzd": int(r["total"])} for r in cur.fetchall()]

    return {
        "period": {"from": date_from, "to": date_to},
        "totals": totals,
        "by_day": by_day,
        "top_products": top_products,
        "payment_breakdown": payment_breakdown,
    }


# ============================================================================
# FISCAL SETTINGS — configurable tax rate, legal identity and receipt prefixes.
# Stored in the existing store_settings table under `fiscal_*` keys so legacy
# endpoints and backups keep working. Internal keys like session_revoked_ns:*
# remain protected by the existing settings-write guard; this endpoint only
# reads/writes the explicit fiscal allow-list below.
# ============================================================================

_FISCAL_KEYS: Dict[str, Dict[str, Any]] = {
    "fiscal_legal_name":       {"max": 200, "default": "Mus Luxury (LUXE)"},
    "fiscal_commercial_name":  {"max": 200, "default": "Mus Luxury"},
    "fiscal_address":          {"max": 400, "default": "FVX6+GCJ Mus luxury, Ouled Yaïch, Blida (09), Algérie"},
    "fiscal_phone":            {"max": 40,  "default": "0655534154"},
    "fiscal_nif":              {"max": 40,  "default": ""},  # Numéro d'Identification Fiscale
    "fiscal_nis":              {"max": 40,  "default": ""},  # Numéro d'Identification Statistique
    "fiscal_rc":               {"max": 40,  "default": ""},  # Registre de Commerce
    "fiscal_article":          {"max": 40,  "default": ""},  # Article d'imposition
    "receipt_prefix_pos":      {"max": 10,  "default": "POS"},
    "receipt_prefix_refund":   {"max": 10,  "default": "RMA"},
    "receipt_prefix_inventory":{"max": 10,  "default": "INV"},
    "receipt_footer_line":     {"max": 200, "default": "Merci de votre visite — Mus Luxury"},
}


class FiscalSettingsInput(BaseModel):
    pos_tax_rate_percent: Optional[int] = Field(None, ge=0, le=100)
    settings: Optional[Dict[str, str]] = None  # fiscal_* keys only

    @validator("settings")
    def _check_keys(cls, v):
        if v is None:
            return v
        for k, val in v.items():
            if k not in _FISCAL_KEYS:
                raise ValueError(f"Clé fiscale inconnue: {k}")
            if val is not None and len(str(val)) > _FISCAL_KEYS[k]["max"]:
                raise ValueError(f"Valeur trop longue pour {k} (max {_FISCAL_KEYS[k]['max']})")
        return v


def _read_fiscal_settings(conn) -> dict:
    cur = conn.cursor()
    keys = list(_FISCAL_KEYS.keys()) + ["pos_tax_rate_percent"]
    placeholders = ",".join(["?"] * len(keys))
    cur.execute(f"SELECT setting_key, setting_value FROM store_settings WHERE setting_key IN ({placeholders})", tuple(keys))
    stored = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}
    out: Dict[str, Any] = {}
    for k, meta in _FISCAL_KEYS.items():
        out[k] = stored.get(k, meta["default"])
    try:
        out["pos_tax_rate_percent"] = int(stored.get("pos_tax_rate_percent") or 0)
    except (TypeError, ValueError):
        out["pos_tax_rate_percent"] = 0
    return out


def _upsert_setting(cur, key: str, value: str) -> None:
    cur.execute(
        """INSERT INTO store_settings (setting_key, setting_value, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP""",
        (key, value),
    )


@app.get("/api/v1/admin/fiscal/settings")
def admin_get_fiscal_settings(admin: dict = Depends(require_any_permission(["settings:write", "dashboard:read"]))):
    with db_session() as conn:
        return _read_fiscal_settings(conn)


@app.put("/api/v1/admin/fiscal/settings")
def admin_update_fiscal_settings(payload: FiscalSettingsInput, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        changed: Dict[str, Any] = {}
        if payload.pos_tax_rate_percent is not None:
            _upsert_setting(cur, "pos_tax_rate_percent", str(payload.pos_tax_rate_percent))
            changed["pos_tax_rate_percent"] = payload.pos_tax_rate_percent
        if payload.settings:
            for k, v in payload.settings.items():
                _upsert_setting(cur, k, "" if v is None else str(v))
                changed[k] = v
        log_audit(conn, int(admin["sub"]), "update_fiscal_settings", "store_settings", "fiscal", {"keys": sorted(changed.keys())})
        return _read_fiscal_settings(conn)


# ============================================================================
# LOW STOCK ALERTS — actionable reorder view with incoming-stock awareness.
# For each variant at or below its low_stock_threshold we show the current
# stock, the quantity on order (from non-cancelled purchase orders that are
# not fully received) and the typical 30-day velocity. The CMS uses this to
# help the owner decide what to reorder and how much.
# ============================================================================


@app.get("/api/v1/admin/inventory/low-stock")
def admin_low_stock_report(
    include_out_of_stock: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(require_permission("inventory:write")),
):
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT pv.id AS variant_id, pv.sku, pv.title AS variant_title, pv.stock_qty,
                       pv.low_stock_threshold,
                       p.id AS product_id, p.name_fr AS product_name,
                       COALESCE(pv.purchase_cost_dzd, p.purchase_cost_dzd, 0) AS unit_cost_dzd,
                       (SELECT COALESCE(SUM(poi.quantity_ordered - poi.quantity_received), 0)
                          FROM purchase_order_items poi JOIN purchase_orders po ON po.id = poi.purchase_order_id
                          WHERE poi.variant_id = pv.id
                            AND po.status NOT IN ('cancelled','received')
                            AND poi.quantity_ordered > poi.quantity_received) AS on_order_qty
                FROM product_variants pv
                JOIN products p ON p.id = pv.product_id
                WHERE pv.is_active = 1 AND p.deleted_at IS NULL
                  AND pv.stock_qty <= pv.low_stock_threshold
                  {'' if include_out_of_stock else 'AND pv.stock_qty > 0'}
                ORDER BY pv.stock_qty ASC, pv.id
                LIMIT ?""",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            # 30-day velocity = units sold across both channels in last 30 days
            cur.execute(
                """SELECT (
                      SELECT COALESCE(SUM(oi.quantity), 0)
                      FROM order_items oi JOIN orders o ON o.id = oi.order_id
                      WHERE oi.variant_id = ? AND o.status != 'cancelled' AND o.created_at >= ?
                   ) + (
                      SELECT COALESCE(SUM(psi.quantity), 0)
                      FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                      WHERE psi.variant_id = ? AND ps.sale_type = 'sale' AND ps.created_at >= ?
                   ) - (
                      SELECT COALESCE(SUM(psi.quantity), 0)
                      FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                      WHERE psi.variant_id = ? AND ps.sale_type = 'refund' AND ps.created_at >= ?
                   ) AS v""",
                (row["variant_id"], thirty_days_ago, row["variant_id"], thirty_days_ago, row["variant_id"], thirty_days_ago),
            )
            row["velocity_30d"] = int(cur.fetchone()["v"])
            # Suggested reorder = roughly 2 months of velocity, minus current + on_order, at least target threshold + 1
            target = max(int(row["low_stock_threshold"]) + 1, row["velocity_30d"] * 2)
            row["suggested_reorder_qty"] = max(0, target - int(row["stock_qty"]) - int(row["on_order_qty"]))
            row["on_order_qty"] = int(row["on_order_qty"])
            row["unit_cost_dzd"] = int(row["unit_cost_dzd"])

        out_of_stock = sum(1 for r in rows if r["stock_qty"] == 0)
        low_stock = len(rows) - out_of_stock
        total_reorder_value = sum(r["suggested_reorder_qty"] * r["unit_cost_dzd"] for r in rows)
        return {
            "items": rows,
            "summary": {
                "out_of_stock_count": out_of_stock,
                "low_stock_count": low_stock,
                "total_suggested_reorder_value_dzd": total_reorder_value,
            },
        }


# ============================================================================
# EXPENSE REPORTS — date-ranged breakdown by category + CSV export for accounting.
# ============================================================================


def _expenses_report_data(conn, date_from: str, date_to: str) -> dict:
    cur = conn.cursor()
    # Per-category totals
    cur.execute(
        """SELECT category, payment_method, COUNT(*) AS c, COALESCE(SUM(amount_dzd), 0) AS total
           FROM expenses WHERE expense_date BETWEEN ? AND ?
           GROUP BY category, payment_method""",
        (date_from, date_to),
    )
    by_cat: Dict[str, Dict[str, Any]] = {}
    for r in cur.fetchall():
        d = by_cat.setdefault(r["category"], {"category": r["category"], "count": 0, "total_dzd": 0, "by_method": {}})
        d["count"] += int(r["c"])
        d["total_dzd"] += int(r["total"])
        d["by_method"][r["payment_method"]] = d["by_method"].get(r["payment_method"], 0) + int(r["total"])

    # Per-day totals (small table for a chart or a quick glance)
    cur.execute(
        """SELECT expense_date AS day, COALESCE(SUM(amount_dzd), 0) AS total
           FROM expenses WHERE expense_date BETWEEN ? AND ?
           GROUP BY expense_date ORDER BY expense_date""",
        (date_from, date_to),
    )
    by_day = [{"day": r["day"], "total_dzd": int(r["total"])} for r in cur.fetchall()]

    # Recent items (for the detail list, capped)
    cur.execute(
        """SELECT id, description, category, amount_dzd, expense_date, payment_method,
                  recipient, receipt_reference, payment_status, created_at
           FROM expenses WHERE expense_date BETWEEN ? AND ?
           ORDER BY expense_date DESC, id DESC LIMIT 200""",
        (date_from, date_to),
    )
    items = [dict(r) for r in cur.fetchall()]

    total = sum(c["total_dzd"] for c in by_cat.values())
    pending = sum(
        int(it["amount_dzd"]) for it in items if it.get("payment_status") == "pending"
    )
    return {
        "period": {"from": date_from, "to": date_to},
        "totals": {
            "total_dzd": total,
            "count": len(items),
            "pending_dzd": pending,
            "categories_count": len(by_cat),
        },
        "by_category": sorted(by_cat.values(), key=lambda c: c["total_dzd"], reverse=True),
        "by_day": by_day,
        "items": items,
    }


@app.get("/api/v1/admin/reports/expenses")
def admin_expense_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("dashboard:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _expenses_report_data(conn, date_from, date_to)


@app.get("/api/v1/admin/reports/expenses.csv")
def admin_expense_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("dashboard:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _expenses_report_data(conn, date_from, date_to)

    buf = io.StringIO()
    writer = csv.writer(buf)
    def _s(v: Any) -> str:
        s = str(v if v is not None else "")
        if s and s[0] in ("=", "+", "-", "@"):
            s = "'" + s
        return s

    writer.writerow(["date", "category", "description", "recipient", "payment_method", "payment_status", "amount_dzd", "receipt_reference"])
    for it in data["items"]:
        writer.writerow([
            _s(it["expense_date"]), _s(it["category"]), _s(it["description"]), _s(it.get("recipient") or ""),
            _s(it["payment_method"]), _s(it["payment_status"]), it["amount_dzd"], _s(it.get("receipt_reference") or ""),
        ])
    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", "", "", data["totals"]["total_dzd"], ""])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="expenses_{date_from}_{date_to}.csv"'},
    )


@app.get("/api/v1/admin/reports/sales")
def admin_sales_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("dashboard:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _sales_report_data(conn, date_from, date_to)


@app.get("/api/v1/admin/reports/sales.csv")
def admin_sales_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("dashboard:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _sales_report_data(conn, date_from, date_to)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "day", "online_count", "online_revenue_dzd",
        "in_store_count", "in_store_revenue_dzd",
        "in_store_refunds_count", "in_store_refunds_dzd",
        "net_revenue_dzd",
    ])
    # CSV formula-injection defence: prefix leading =/+/-/@ with a single quote.
    def _s(v: Any) -> str:
        s = str(v if v is not None else "")
        if s and s[0] in ("=", "+", "-", "@"):
            s = "'" + s
        return s

    for d in data["by_day"]:
        writer.writerow([
            _s(d["day"]), d["online_count"], d["online_revenue_dzd"],
            d["in_store_count"], d["in_store_revenue_dzd"],
            d["in_store_refunds_count"], d["in_store_refunds_dzd"],
            d["net_revenue_dzd"],
        ])
    t = data["totals"]
    writer.writerow([])
    writer.writerow(["TOTAL", t["online_count"], t["online_revenue_dzd"],
                     t["in_store_count"], t["in_store_revenue_dzd"],
                     t["in_store_refunds_count"], t["in_store_refunds_dzd"],
                     t["net_revenue_dzd"]])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="sales_{date_from}_{date_to}.csv"'},
    )


@app.post("/api/v1/admin/inventory/counts/{count_id}/cancel")
def admin_cancel_count(count_id: int, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, reference FROM inventory_counts WHERE id = ?", (count_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")
        if c["status"] != "open":
            raise HTTPException(status_code=409, detail="Inventaire déjà appliqué")
        cur.execute("UPDATE inventory_counts SET status = 'cancelled' WHERE id = ?", (count_id,))
        log_audit(conn, int(admin["sub"]), "cancel_inventory_count", "inventory_count", str(count_id), {"reference": c["reference"]})
        return _count_payload(conn, count_id)

