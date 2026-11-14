"""Products, variants, categories, attributes, brands, images, uploads and barcodes (CMS)."""
from fastapi import APIRouter
import io
import os
import hashlib
import itertools
import re
import secrets
from typing import Any, Dict, List, Optional
from fastapi import Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..seed import SUPPORTED_ATTRIBUTE_TYPES
from ..security import validate_uploaded_image
from ..deps import (
    log_audit,
    require_any_permission,
    require_permission,
)
from ..common import (
    UPLOAD_STORAGE_DIR,
    _boutique_info_from_settings,
    serialize_categories_batch,
    serialize_category,
    serialize_product,
    serialize_products_batch,
)

router = APIRouter()



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
    # No invented photo: empty until the owner uploads one (the shop then
    # shows a neutral placeholder).
    image_url: Optional[str] = ""
    banner_url: Optional[str] = ""
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
    # No invented photo: empty until the owner uploads one.
    main_image_url: Optional[str] = ""
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
                detail=f"Caractéristique '{key}' inconnue pour cette catégorie",
            )
        if key not in axes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{key}' ne sert pas à créer des déclinaisons dans cette catégorie",
            )
        val = str(raw_val).strip()
        if not val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Valeur vide pour '{key}'",
            )
        allowed = cat_attrs[key].get("option_values") or set()
        if allowed and val not in allowed and not allow_custom_values:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Valeur '{val}' non valable pour '{key}'. Valeurs possibles : {', '.join(sorted(allowed))}",
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
        raise HTTPException(status_code=422, detail="La référence (SKU) de la déclinaison est obligatoire")
    cur = conn.cursor()
    if exclude_variant_id is None:
        cur.execute("SELECT id FROM product_variants WHERE sku = ?", (sku,))
    else:
        cur.execute("SELECT id FROM product_variants WHERE sku = ? AND id != ?", (sku, exclude_variant_id))
    if cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La référence (SKU) '{sku}' existe déjà",
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
        raise HTTPException(status_code=404, detail="Déclinaison introuvable")
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


# --- DYNAMIC CATEGORY & ATTRIBUTE BUILDER ---

@router.post("/api/v1/admin/categories", status_code=201)
def create_custom_category(
    payload: CategoryCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE slug = ?", (payload.slug,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"L'adresse de catégorie '{payload.slug}' existe déjà")

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


@router.post("/api/v1/admin/category-attributes", status_code=201)
def add_category_attribute(
    payload: CategoryAttributeCreate,
    admin: dict = Depends(require_permission("categories:write"))
):
    if not payload.category_id:
        raise HTTPException(status_code=400, detail="Choisissez une catégorie")
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE id = ?", (payload.category_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Catégorie de destination introuvable")

        cur.execute(
            "SELECT id FROM category_attributes WHERE category_id = ? AND attr_key = ?",
            (payload.category_id, payload.attr_key)
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"La caractéristique '{payload.attr_key}' existe déjà dans cette catégorie")

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


@router.delete("/api/v1/admin/category-attributes/{attr_id}")
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
            raise HTTPException(status_code=404, detail="Caractéristique introuvable")

        cur.execute("SELECT COUNT(*) AS cnt FROM product_attribute_values WHERE attribute_id = ?", (attr_id,))
        prod_usage = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM variant_attribute_values WHERE attribute_id = ?", (attr_id,))
        var_usage = cur.fetchone()["cnt"]
        total_usage = prod_usage + var_usage

        if var_usage > 0 and int(attr["is_variant_axis"] or 0):
            # Variants are told apart by this attribute (e.g. Noir / Rouge):
            # removing it would leave identical, indistinguishable variants.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"« {attr['label_fr']} » sert à distinguer {var_usage} variante(s) de produits (ex. couleurs, tailles). "
                    "Supprimez ou archivez d'abord ces variantes / produits, puis retirez l'attribut."
                ),
            )
        if total_usage > 0 and not force_migrate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"« {attr['label_fr']} » est renseigné sur {total_usage} fiche(s) produit. "
                    "Si vous confirmez, ces valeurs seront effacées des produits."
                ),
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

@router.post("/api/v1/admin/products", status_code=201)
def create_dynamic_product(
    payload: ProductCreate,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id = ?", (payload.category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")

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
                    detail=f"Caractéristiques obligatoires manquantes pour '{cat['name_fr']}' : {', '.join(missing)}"
                )

        cur.execute("SELECT id, slug, sku FROM products WHERE slug = ? OR sku = ?", (payload.slug, payload.sku))
        existing_prod = cur.fetchone()
        if existing_prod:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Un produit avec l'adresse '{payload.slug}' ou la référence '{payload.sku}' existe déjà"
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
                raise HTTPException(status_code=422, detail="La référence (SKU) de la déclinaison est obligatoire")
            if v_sku in seen_skus:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"La référence '{v_sku}' apparaît deux fois")
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
                    (v.image_url or "").strip() or None, v.purchase_cost_dzd, v.weight_grams,
                    v.low_stock_threshold, 1, sig,
                )
            )
            vid = cur.lastrowid
            replace_variant_attribute_values(conn, vid, cat_attrs_full, v_attrs)

        log_audit(conn, int(admin["sub"]), "create_product", "product", str(prod_id), {"sku": payload.sku, "status": payload.status})
        cur.execute("SELECT * FROM products WHERE id = ?", (prod_id,))
        return serialize_product(conn, dict(cur.fetchone()), include_private=True)


@router.post("/api/v1/admin/products/{product_id}/generate-variants", status_code=201)
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
            raise HTTPException(status_code=404, detail="Produit introuvable")

        cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (prod["category_id"],))
        cat_attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}

        axis_keys = sorted(payload.axes.keys())
        if not axis_keys:
            raise HTTPException(status_code=400, detail="At least one variant axis is required")
        for k in axis_keys:
            if k not in cat_attrs or not cat_attrs[k]["is_variant_axis"]:
                raise HTTPException(status_code=400, detail=f"'{k}' ne sert pas à créer des déclinaisons dans cette catégorie")
            if not payload.axes[k]:
                raise HTTPException(status_code=400, detail=f"Aucune valeur choisie pour '{k}'")

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
                    None, payload.low_stock_threshold, sig,
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


@router.post("/api/v1/admin/products/{product_id}/variants", status_code=201)
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
            raise HTTPException(status_code=404, detail="Produit introuvable")

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
                (payload.image_url or "").strip() or None, payload.purchase_cost_dzd,
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


@router.put("/api/v1/admin/variants/{variant_id}")
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
            raise HTTPException(status_code=404, detail="Déclinaison introuvable")

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
                raise HTTPException(status_code=422, detail="Le nom de la déclinaison est obligatoire")
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


@router.delete("/api/v1/admin/variants/{variant_id}")
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
            raise HTTPException(status_code=404, detail="Déclinaison introuvable")

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


@router.post("/api/v1/admin/variants/bulk-update")
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
                    detail=f"Le stock de '{variant['sku']}' ne peut pas devenir négatif ({new_stock})",
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

@router.get("/api/v1/admin/categories")
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
        return {"items": serialize_categories_batch(conn, cur.fetchall())}


@router.put("/api/v1/admin/category-attributes/{attr_id}")
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
            raise HTTPException(status_code=404, detail="Caractéristique introuvable")

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


@router.post("/api/v1/admin/category-attributes/{attr_id}/options", status_code=201)
def admin_create_attribute_option(
    attr_id: int,
    payload: AttributeOptionUpsert,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attributes WHERE id = ?", (attr_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Caractéristique introuvable")
        value = payload.value.strip()
        cur.execute(
            "SELECT id FROM category_attribute_options WHERE attribute_id = ? AND value = ?",
            (attr_id, value),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"La valeur '{value}' existe déjà")
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


@router.put("/api/v1/admin/attribute-options/{option_id}")
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
            raise HTTPException(status_code=404, detail="Valeur introuvable")
        new_value = payload.value.strip()
        if new_value != option["value"]:
            cur.execute(
                "SELECT id FROM category_attribute_options WHERE attribute_id = ? AND value = ? AND id != ?",
                (option["attribute_id"], new_value, option_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"La valeur '{new_value}' existe déjà")
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


@router.delete("/api/v1/admin/attribute-options/{option_id}")
def admin_delete_attribute_option(
    option_id: int,
    admin: dict = Depends(require_permission("categories:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_attribute_options WHERE id = ?", (option_id,))
        option = cur.fetchone()
        if not option:
            raise HTTPException(status_code=404, detail="Valeur introuvable")
        cur.execute(
            """SELECT COUNT(*) AS cnt FROM variant_attribute_values
               WHERE attribute_id = ? AND option_value = ?""",
            (option["attribute_id"], option["value"]),
        )
        in_use = int(cur.fetchone()["cnt"] or 0)
        if in_use > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La valeur '{option['value']}' est utilisée par {in_use} déclinaison(s). Renommez ou supprimez-les d'abord.",
            )
        cur.execute("DELETE FROM category_attribute_options WHERE id = ?", (option_id,))
        log_audit(conn, int(admin["sub"]), "delete_attribute_option", "category_attribute_option", str(option_id), {
            "attribute_id": option["attribute_id"], "value": option["value"],
        })
        return {"deleted": True, "option_id": option_id}

# BACKUP_STORAGE_DIR removed with the admin-facing /admin/backups endpoints;
# the shell backup script owns its own directory via $BACKUP_DIR directly.

# Phone photos are often 5-12 MB; they are reduced to a few hundred KB on
# arrival (_optimize_product_image), so the upload limit can be generous.
MAX_UPLOAD_IMAGE_BYTES = 15 * 1024 * 1024


PRODUCT_IMAGE_MAX_SIDE = 1600



def _optimize_product_image(data: bytes) -> tuple:
    """Phone photos are 3-5 MB; the shop shows them at most ~800 px wide.
    Each upload is turned upright (phone rotation), stripped of its metadata
    (camera EXIF can hold the shop's GPS position), reduced to 1600 px and
    re-encoded: JPEG, or WebP when it has transparency. A few hundred KB
    instead of several MB: disk (40 GB), backups and mobile data."""
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 64_000_000  # refuse decompression bombs (a 48 MP phone photo is fine)
    try:
        img = Image.open(io.BytesIO(data))
        if img.format != "JPEG" and img.width * img.height > 16_000_000:
            # PNG / WebP decode at full size: keep within the API's 256 MB.
            raise HTTPException(status_code=400, detail="Image trop grande (dimensions). Réduisez-la avant de l'envoyer.")
        if img.format == "JPEG":
            # Decode directly at a reduced scale: fast and light on memory.
            img.draft("RGB", (PRODUCT_IMAGE_MAX_SIDE * 2, PRODUCT_IMAGE_MAX_SIDE * 2))
        img = ImageOps.exif_transpose(img)
        img.thumbnail((PRODUCT_IMAGE_MAX_SIDE, PRODUCT_IMAGE_MAX_SIDE), Image.LANCZOS)
        transparent = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        out = io.BytesIO()
        if transparent:
            img.convert("RGBA").save(out, "WEBP", quality=85, method=4)
            ext = ".webp"
        else:
            img.convert("RGB").save(out, "JPEG", quality=82, optimize=True, progressive=True)
            ext = ".jpg"
        return out.getvalue(), ext, img.size
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=400, detail="Image trop grande (dimensions). Réduisez-la avant de l'envoyer.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Image illisible ou endommagée.")



@router.post("/api/v1/admin/upload", status_code=201)
async def upload_product_image(
    file: UploadFile = File(...),
    admin: dict = Depends(require_permission("products:write"))
):
    data = await file.read(MAX_UPLOAD_IMAGE_BYTES + 1)
    if len(data) > MAX_UPLOAD_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image trop lourde (15 Mo maximum)")
    validate_uploaded_image(file.filename or "upload.jpg", file.content_type or "", data, max_bytes=MAX_UPLOAD_IMAGE_BYTES)
    data, ext, (width, height) = _optimize_product_image(data)
    digest = hashlib.sha256(data).hexdigest()[:16]
    safe_name = f"img_{digest}{ext}"
    dest_path = os.path.join(UPLOAD_STORAGE_DIR, safe_name)
    with open(dest_path, "wb") as uf:
        uf.write(data)
    return {"filename": safe_name, "url": f"/uploads/{safe_name}", "size_bytes": len(data), "width": width, "height": height}

# ============================================================================
# SECTION 6: WEBHOOKS & STORE INTEGRATIONS
# ============================================================================


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


@router.put("/api/v1/admin/products/{product_id}")
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
            raise HTTPException(status_code=404, detail="Produit introuvable")
        current_version = int(prod["version"])
        if payload.expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ce produit a été modifié entre-temps (version {current_version}). Rechargez la fiche avant d'enregistrer."
            )
        if payload.sku and payload.sku != prod["sku"]:
            cur.execute("SELECT id FROM products WHERE sku = ? AND id != ?", (payload.sku, product_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La référence '{payload.sku}' est déjà utilisée par un autre produit"
                )
        if payload.slug and payload.slug != prod["slug"]:
            cur.execute("SELECT id FROM products WHERE slug = ? AND id != ?", (payload.slug, product_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"L'adresse '{payload.slug}' est déjà utilisée par un autre produit"
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


class StockAdjustmentInput(BaseModel):
    change_qty: int
    reason: str = Field("manual_adjustment", min_length=3, max_length=120)


@router.post("/api/v1/admin/variants/{variant_id}/adjust-stock")
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
            raise HTTPException(status_code=404, detail="Déclinaison introuvable")
        cur.execute(
            "UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ? AND (stock_qty + ?) >= 0",
            (payload.change_qty, variant_id, payload.change_qty)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="Le stock ne peut pas devenir négatif : il n'y a plus d'unité à retirer pour cette variante.")
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


@router.get("/api/v1/admin/products")
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


@router.delete("/api/v1/admin/products/{product_id}")
def admin_safe_delete_or_archive_product(
    product_id: int,
    hard_delete: bool = Query(False),
    force: bool = Query(False),
    admin: dict = Depends(require_permission("products:write"))
):
    """
    Archive (default) or permanently delete a product.

    A product that has ANY history — sold online, sold in store, bought from a
    supplier — can only be archived: deleting it would change past invoices,
    reports and supplier accounts. Customer orders are never deleted here.
    `force` is accepted for compatibility and ignored.
    """
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        variant_ids_sql = "SELECT id FROM product_variants WHERE product_id = ?"
        history = {}
        for label, sql in (
            ("online_order_lines", f"SELECT COUNT(*) AS cnt FROM order_items WHERE product_id = ? OR variant_id IN ({variant_ids_sql})"),
            ("in_store_sale_lines", f"SELECT COUNT(*) AS cnt FROM pos_sale_items WHERE product_id = ? OR variant_id IN ({variant_ids_sql})"),
            ("purchase_lines", f"SELECT COUNT(*) AS cnt FROM purchase_order_items WHERE product_id = ? OR variant_id IN ({variant_ids_sql})"),
        ):
            cur.execute(sql, (product_id, product_id))
            history[label] = int(cur.fetchone()["cnt"])
        has_history = any(history.values())

        def _archive(reason: str):
            cur.execute(
                "UPDATE products SET status = 'archived', deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (product_id,),
            )
            cur.execute("UPDATE product_variants SET is_active = 0 WHERE product_id = ?", (product_id,))
            log_audit(conn, int(admin["sub"]), "archive_product", "product", str(product_id), {
                "sku": prod["sku"], "history": history, "reason": reason,
            })

        if hard_delete and has_history:
            _archive("delete requested; product has history")
            parts = []
            if history["online_order_lines"]:
                parts.append(f"{history['online_order_lines']} ligne(s) de commande en ligne")
            if history["in_store_sale_lines"]:
                parts.append(f"{history['in_store_sale_lines']} vente(s) en magasin")
            if history["purchase_lines"]:
                parts.append(f"{history['purchase_lines']} achat(s) fournisseur")
            return {
                "archived": True,
                "deleted": False,
                "has_orders": True,
                "product_id": product_id,
                "status": "archived",
                "historical_order_items_preserved": history["online_order_lines"],
                "history": history,
                "message": (
                    f"« {prod['name_fr']} » a un historique ({', '.join(parts)}) : il a été archivé, "
                    "pas supprimé, pour garder les factures et la comptabilité exactes. Il n'est plus en vente."
                ),
            }

        if hard_delete:
            # Never sold nor bought: remove the product and its own data.
            cur.execute(f"DELETE FROM inventory_movements WHERE variant_id IN ({variant_ids_sql})", (product_id,))
            cur.execute(f"DELETE FROM variant_attribute_values WHERE variant_id IN ({variant_ids_sql})", (product_id,))
            cur.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM product_images WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM product_attribute_values WHERE product_id = ?", (product_id,))
            cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
            log_audit(conn, int(admin["sub"]), "delete_product", "product", str(product_id), {
                "sku": prod["sku"], "name_fr": prod["name_fr"],
            })
            return {
                "deleted": True,
                "archived": False,
                "product_id": product_id,
                "status": "deleted",
                "historical_order_items_preserved": 0,
                "message": f"Produit « {prod['name_fr']} » supprimé définitivement (il n'avait jamais été vendu ni acheté).",
            }

        _archive("archive requested")
        return {
            "archived": True,
            "deleted": False,
            "product_id": product_id,
            "status": "archived",
            "historical_order_items_preserved": history["online_order_lines"],
            "message": f"Produit « {prod['name_fr']} » archivé : il n'est plus en vente, son historique est conservé.",
        }


@router.post("/api/v1/admin/products/bulk-status")
def admin_bulk_update_product_status(
    payload: BulkProductStatusInput,
    admin: dict = Depends(require_permission("products:write"))
):
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Choisissez au moins un produit")
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        updated = 0
        for pid in payload.product_ids:
            if payload.status == "archived":
                # Same effect as the Archive button.
                cur.execute(
                    "UPDATE products SET status = 'archived', deleted_at = COALESCE(deleted_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (pid,),
                )
                updated += cur.rowcount
                cur.execute("UPDATE product_variants SET is_active = 0 WHERE product_id = ?", (pid,))
            else:
                # Published / draft: really bring an archived product back
                # (the archive also hid it with deleted_at and switched its
                # variants off — otherwise it would stay invisible).
                cur.execute(
                    "UPDATE products SET status = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (payload.status, pid),
                )
                updated += cur.rowcount
                cur.execute(
                    "UPDATE product_variants SET is_active = 1 WHERE product_id = ? AND is_active = 0",
                    (pid,),
                )
        log_audit(conn, int(admin["sub"]), "bulk_product_status", "product", "bulk", {"count": updated, "status": payload.status})
        return {"updated_count": updated, "status": payload.status}


@router.post("/api/v1/admin/brands", status_code=201)
def admin_create_brand(
    payload: BrandCreateInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM brands WHERE slug = ?", (payload.slug,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"La marque '{payload.slug}' existe déjà")
        cur.execute(
            "INSERT INTO brands (name, slug, logo_url, is_active) VALUES (?, ?, ?, 1)",
            (payload.name, payload.slug, payload.logo_url)
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_brand", "brand", str(bid), {"slug": payload.slug})
        cur.execute("SELECT * FROM brands WHERE id = ?", (bid,))
        return dict(cur.fetchone())


@router.put("/api/v1/admin/categories/{category_id}")
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
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
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


@router.post("/api/v1/admin/categories/{category_id}/restore")
def admin_restore_category(category_id: int, admin: dict = Depends(require_permission("categories:write"))):
    """Brings an archived category back (visible again in the CMS and, if
    active, on the storefront)."""
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT slug FROM categories WHERE id = ?", (category_id,))
        cat = cur.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        cur.execute("UPDATE categories SET is_active = 1, deleted_at = NULL WHERE id = ?", (category_id,))
        log_audit(conn, int(admin["sub"]), "restore_category", "category", str(category_id), {"slug": cat["slug"]})
        return {"restored": True, "category_id": category_id}



@router.delete("/api/v1/admin/categories/{category_id}")
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
            raise HTTPException(status_code=404, detail="Catégorie introuvable")

        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE category_id = ? AND deleted_at IS NULL", (category_id,))
        prods_count = cur.fetchone()["cnt"]

        if hard_delete:
            if prods_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Impossible de supprimer définitivement : {prods_count} produit(s) sont encore rattachés à cette catégorie. Veuillez d'abord réassigner ou archiver ces produits."
                )
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE category_id = ?", (category_id,))
            archived_count = int(cur.fetchone()["cnt"])
            if archived_count > 0:
                # Archived products still belong to it (their sales history
                # depends on them): hide the category instead of deleting it.
                cur.execute(
                    "UPDATE categories SET is_active = 0, deleted_at = COALESCE(deleted_at, CURRENT_TIMESTAMP) WHERE id = ?",
                    (category_id,),
                )
                log_audit(conn, int(admin["sub"]), "archive_category", "category", str(category_id),
                          {"slug": cat["slug"], "reason": "delete requested; archived products remain"})
                return {
                    "archived": True, "deleted": False, "category_id": category_id,
                    "message": (
                        f"La catégorie « {cat['name_fr']} » contient encore {archived_count} produit(s) archivé(s) "
                        "dont l'historique est conservé : elle a été archivée (masquée) au lieu d'être supprimée."
                    ),
                }
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


@router.post("/api/v1/admin/products/{product_id}/images", status_code=201)
def admin_add_product_image(
    product_id: int,
    payload: ProductImageAddInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Produit introuvable")
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


@router.put("/api/v1/admin/products/{product_id}/images/reorder")
def admin_reorder_product_images(
    product_id: int,
    payload: ProductImageReorderInput,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Produit introuvable")
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


@router.delete("/api/v1/admin/product-images/{image_id}")
def admin_delete_product_image(
    image_id: int,
    admin: dict = Depends(require_permission("products:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product_images WHERE id = ?", (image_id,))
        img = cur.fetchone()
        if not img:
            raise HTTPException(status_code=404, detail="Photo introuvable")
        cur.execute("DELETE FROM product_images WHERE id = ?", (image_id,))
        log_audit(conn, int(admin["sub"]), "delete_product_image", "product_image", str(image_id), {"product_id": img["product_id"]})
        return {"deleted": True, "image_id": image_id}


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



@router.get("/api/v1/admin/barcodes/validate")
def admin_validate_barcode(
    code: str = Query(..., min_length=1, max_length=64),
    admin: dict = Depends(require_any_permission(["products:write", "pos:read", "inventory:write"])),
):
    return validate_barcode(code)



@router.post("/api/v1/admin/barcodes/generate")
def admin_generate_barcodes(payload: BarcodeGenerateInput, admin: dict = Depends(require_permission("products:write"))):
    with db_session() as conn:
        codes = [_generate_internal_ean13(conn) for _ in range(payload.count)]
        return {"symbology": "ean13", "internal": True, "barcodes": codes}



@router.post("/api/v1/admin/variants/{variant_id}/assign-barcode")
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



@router.delete("/api/v1/admin/variants/{variant_id}/barcode")
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



@router.get("/api/v1/admin/variants/{variant_id}/label")
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
