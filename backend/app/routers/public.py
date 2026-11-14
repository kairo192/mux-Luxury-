"""Public shop API: catalog, store info, pages, delivery zones, orders, health checks, uploaded images."""
from fastapi import APIRouter
import os
import hashlib
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..security import check_rate_limit, get_real_client_ip
from ..whatsapp import build_customer_order_whatsapp_message
from ..deps import (
    log_audit,
    require_permission,
)
from ..common import (
    CMS_UPDATE_MANIFEST_URL,
    UPLOAD_STORAGE_DIR,
    _boutique_info_from_settings,
    _is_protected_setting_key,
    serialize_categories_batch,
    serialize_category,
    serialize_product,
    serialize_products_batch,
)

router = APIRouter()



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
            raise ValueError("Numéro de mobile algérien invalide (il doit commencer par 05, 06, 07 ou +213)")
        return cleaned

    @validator("full_name", "commune", "delivery_address", "customer_notes", pre=True, always=True)
    def reject_xss_and_html_tags(cls, v):
        if v is None:
            return ""
        # Invisible control and text-direction override characters (U+202E…)
        # can disguise a name in the CMS and on receipts: removed.
        s = re.sub(r"[\u0000-\u0008\u000b-\u001f\u007f\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", str(v)).strip()
        if re.search(r"(<\s*/?\s*(script|iframe|svg|img|object|embed|link|style|meta)|javascript\s*:|on\w+\s*=)", s, re.IGNORECASE):
            raise ValueError("Code HTML ou script refusé dans les coordonnées")
        if "<" in s or ">" in s:
            raise ValueError("Les caractères < et > ne sont pas acceptés dans les coordonnées")
        return s


def _free_delivery_threshold(cur) -> int:
    """CMS → Contenu → "Seuil Livraison Gratuite (DA)". 0 / empty = no free delivery."""
    cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", ("free_delivery_threshold_dzd",))
    row = cur.fetchone()
    if not row:
        return 0
    raw = row["setting_value"]
    try:
        raw = json.loads(raw)
    except Exception:
        pass
    try:
        return max(0, int(str(raw).replace(" ", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


@router.get("/api/v1/store/settings")
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


# Shop data the owner changes in the CMS (stock, prices, visibility,
# delivery prices): the browser keeps a copy but checks it on every load
# (ETag -> 304 when nothing changed), so a sold-out bag, a new price or an
# archived product shows at once — never minutes or hours late.
_PUBLIC_LIVE_CACHE = "public, no-cache"



@router.get("/api/v1/categories")
def list_public_categories(response: Response, request: Request):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC, id ASC"
        )
        cats = serialize_categories_batch(conn, cur.fetchall())
        payload = {"items": cats}
        etag = f'"{hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"'
        response.headers["ETag"] = etag
        # Short cache: a category deleted in the CMS disappears from the shop within ~30 s.
        response.headers["Cache-Control"] = _PUBLIC_LIVE_CACHE
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
        return payload


@router.get("/api/v1/categories/{slug}")
def get_public_category(slug: str):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE slug = ? AND is_active = 1 AND deleted_at IS NULL", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        return serialize_category(conn, dict(row))


@router.get("/api/v1/brands")
def list_public_brands():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, slug, logo_url FROM brands WHERE is_active = 1 ORDER BY name ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}


@router.get("/api/v1/delivery-zones")
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
        response.headers["Cache-Control"] = _PUBLIC_LIVE_CACHE
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
        return payload


@router.get("/api/v1/products")
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
            response.headers["Cache-Control"] = _PUBLIC_LIVE_CACHE
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


@router.get("/api/v1/products/{slug}")
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
            raise HTTPException(status_code=404, detail="Produit introuvable")
        return serialize_product(conn, dict(row), include_private=False)


@router.post("/api/v1/orders", status_code=201)
def create_guest_order(
    payload: GuestOrderCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"order:{client_ip}", max_requests=15, window_seconds=60)

    # Anti-Retour COD: Block orders from phones on the active COD Blacklist
    from ..whatsapp import normalize_algerian_phone as _norm_phone
    e164_chk, local_chk, _ = _norm_phone(payload.phone)
    with db_session() as chk_conn:
        chk_cur = chk_conn.cursor()
        chk_cur.execute(
            "SELECT * FROM customer_phone_blacklist WHERE (phone_e164 = ? OR phone_local = ?) AND is_blocked = 1",
            (e164_chk, local_chk)
        )
        bl_row = chk_cur.fetchone()
        if bl_row:
            shop = _boutique_info_from_settings(chk_conn)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"Commande refusée (Protection Anti-Retour COD) : Ce numéro ({local_chk}) ne peut pas passer de "
                        f"commande automatique. Contactez le service client {shop['name']} sur WhatsApp au {shop['phone']}.")
            )

    if not payload.items:
        raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")

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
                detail=f"Commande déjà enregistrée (référence {dup['order_reference']})"
            )

        # 1. Verify Wilaya & Delivery Method Rate on the server
        cur.execute("SELECT * FROM delivery_zones WHERE wilaya_code = ? AND is_active = 1", (payload.wilaya_code,))
        zone = cur.fetchone()
        if not zone:
            raise HTTPException(status_code=400, detail=f"Wilaya {payload.wilaya_code} non desservie")

        cur.execute(
            "SELECT fee_dzd, is_supported FROM delivery_rates WHERE zone_id = ? AND delivery_method = ?",
            (zone["id"], payload.delivery_method)
        )
        rate = cur.fetchone()
        if not rate or not rate["is_supported"]:
            raise HTTPException(status_code=400, detail=("La livraison à domicile" if payload.delivery_method == "home" else "La livraison en point relais (stop-desk)") + f" n'est pas disponible pour la wilaya {zone['wilaya_name_fr']}. Choisissez l'autre mode de livraison.")
        delivery_fee_dzd = int(rate["fee_dzd"])

        # 2. Consolidate duplicate variant_ids, Verify Variants & Stock, and Calculate True Server-Side Subtotal
        consolidated_items: List[OrderItemInput] = []
        merged_qty_by_vid: Dict[int, int] = {}
        for raw_item in payload.items:
            merged_qty_by_vid[raw_item.variant_id] = merged_qty_by_vid.get(raw_item.variant_id, 0) + int(raw_item.quantity)
        for vid, total_q in merged_qty_by_vid.items():
            if total_q > 50:
                raise HTTPException(status_code=422, detail=f"50 pièces maximum par article (demandé : {total_q})")
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
                raise HTTPException(status_code=404, detail=f"Un article n'est plus disponible")
            if v["stock_qty"] < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Stock insuffisant pour '{v['product_name']} ({v['title']})' : demandé {item.quantity}, disponible {v['stock_qty']}"
                )
            unit_price = int(v["price_override_dzd"]) if v["price_override_dzd"] is not None else int(v["selling_price_dzd"])
            line_total = unit_price * item.quantity
            subtotal_dzd += line_total
            resolved_lines.append((v, item.quantity, unit_price, line_total))

        discount_dzd = 0
        coupon_used: Optional[str] = None
        if payload.coupon_code:
            cur.execute(
                "SELECT * FROM coupons WHERE UPPER(code) = ? AND is_active = 1",
                (payload.coupon_code.strip().upper(),)
            )
            cpn = cur.fetchone()
            if not cpn:
                raise HTTPException(status_code=400, detail="Code promo inconnu ou expiré")
            if dict(cpn).get("usage_limit") is not None and int(cpn["usage_count"]) >= int(dict(cpn)["usage_limit"]):
                raise HTTPException(status_code=400, detail=f"Le code promo '{cpn['code']}' n'est plus utilisable (limite atteinte)")
            if subtotal_dzd < int(cpn["min_order_dzd"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Le code promo '{cpn['code']}' demande un minimum de {cpn['min_order_dzd']} DA d'achat"
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
                raise HTTPException(status_code=400, detail=f"Le code promo '{cpn['code']}' n'est plus utilisable (limite atteinte)")
            coupon_used = str(cpn["code"])

        # Free delivery promised by the shop (CMS threshold) is applied HERE, so
        # the stored order (what the courier collects) matches what the
        # customer was shown.
        free_threshold = _free_delivery_threshold(cur)
        if free_threshold and subtotal_dzd >= free_threshold:
            delivery_fee_dzd = 0
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
                        subtotal_dzd, delivery_fee_dzd, total_dzd, status, customer_notes, stock_deducted, idempotency_hash,
                        coupon_code, discount_dzd)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'cod', ?, ?, ?, 'new', ?, 1, ?, ?, ?)""",
                    (
                        order_ref, customer_id, payload.full_name, payload.phone,
                        payload.wilaya_code, zone["wilaya_name_fr"], payload.commune,
                        payload.delivery_address, payload.delivery_method,
                        subtotal_dzd, delivery_fee_dzd, total_dzd,
                        payload.customer_notes, idem_hash,
                        coupon_used, discount_dzd,
                    ),
                )
                order_id = cur.lastrowid
                break
            except Exception:
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
                    detail=f"Stock insuffisant pour '{v['product_name']} ({v['title']})'"
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


@router.put("/api/v1/admin/categories-reorder")
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


@router.get("/uploads/{filename}")
def serve_uploaded_image(filename: str):
    if not re.match(r"^img_[a-f0-9]{16}\.(jpg|png|webp)$", filename):
        raise HTTPException(status_code=400, detail="Invalid media filename")
    fpath = os.path.join(UPLOAD_STORAGE_DIR, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Fichier introuvable")
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


@router.get("/api/v1/store/layout")
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

        # All blocks, with their on/off state: the shop hides the ones switched off.
        cur.execute("SELECT * FROM homepage_sections ORDER BY display_order ASC")
        sections = []
        for s in cur.fetchall():
            sd = dict(s)
            sd["config"] = json.loads(sd.pop("config_json") or "{}")
            sections.append(sd)

        cur.execute("SELECT * FROM banners WHERE is_active = 1 ORDER BY display_order ASC, id ASC")
        banners = [dict(b) for b in cur.fetchall()]

        cur.execute("SELECT * FROM categories WHERE is_active = 1 AND deleted_at IS NULL ORDER BY display_order ASC")
        categories = serialize_categories_batch(conn, cur.fetchall())

        return {
            "settings": settings,
            "homepage_sections": sections,
            "banners": banners,
            "categories": categories,
        }


# ============================================================================
# SECTION 5 & 9: GUEST ORDER TRACKING, COUPONS & OPTIMISTIC CONCURRENCY SYNC
# ============================================================================

@router.get("/api/v1/orders/track")
def track_guest_order(request: Request, reference: str = Query(...), phone: str = Query(...)):
    """
    Public guest order tracking requiring BOTH order_reference and matching customer phone
    to prevent IDOR enumeration of other customers' orders.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"track_order:{client_ip}", max_requests=30, window_seconds=60)
    from ..whatsapp import normalize_algerian_phone as _norm_phone
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
            raise HTTPException(status_code=404, detail="Aucune commande ne correspond à cette référence et à ce numéro")
        # Only what the customer needs: no internal notes, ids or keys — a new
        # column added to orders is never exposed here by accident.
        row = dict(ord_row)
        public = ("order_reference", "status", "customer_name", "wilaya_code", "wilaya_name", "commune",
                  "delivery_address", "delivery_method", "payment_method", "subtotal_dzd", "discount_dzd",
                  "coupon_code", "delivery_fee_dzd", "total_dzd", "customer_notes", "created_at", "updated_at")
        od = {k: row.get(k) for k in public if k in row}
        cur.execute("SELECT product_name, variant_title, quantity, unit_price_dzd, line_total_dzd FROM order_items WHERE order_id = ?", (row["id"],))
        od["items"] = [dict(r) for r in cur.fetchall()]
        return od




# ============================================================================
# PRODUCTION ENDPOINTS: COUPON VALIDATION, 69-WILAYA RATE MANAGEMENT,
# VARIANT STOCK ADJUSTMENTS, GUEST CUSTOMER RECORDS & ANALYTICS REPORTS
# ============================================================================

class CouponValidateRequest(BaseModel):
    code: str
    subtotal_dzd: int = Field(..., ge=0)


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


@router.post("/api/v1/coupons/validate")
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



@router.get("/api/v1/delivery-zones/calculate")
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

        # Free delivery promised by the shop (CMS threshold) is applied HERE, so
        # the stored order (what the courier collects) matches what the
        # customer was shown.
        free_threshold = _free_delivery_threshold(cur)
        if free_threshold and subtotal_dzd >= free_threshold:
            delivery_fee_dzd = 0
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
            "free_delivery_threshold_dzd": free_threshold,
            "free_delivery_applied": bool(free_threshold and subtotal_dzd >= free_threshold),
            "total_dzd": total_dzd
        }


@router.put("/api/v1/admin/delivery-zones-bulk")
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


@router.get("/health")
@router.get("/api/v1/health")
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



# Compatibility matrix for the Tauri POS / Desktop CMS. The desktop app pings
# this on startup and refuses to run against an API that no longer supports it
# (the user is prompted to install the newer signed release). Keep the keys in
# sync with infrastructure/environments/*.env and docs/cicd/POS_UPDATE_STRATEGY.md.
_POS_MIN_SUPPORTED = os.getenv("POS_MIN_SUPPORTED_VERSION", "1.0.0")

_POS_LATEST = os.getenv("POS_LATEST_VERSION", "1.0.0")

_POS_API_CONTRACT = os.getenv("POS_API_CONTRACT_VERSION", "1")



@router.get("/api/v1/pos/compat")
def pos_compat(client_version: Optional[str] = None):
    """POS / Desktop CMS version-compatibility probe.

    Returns the minimum supported POS version, the latest released POS
    version, and a boolean telling the client whether its own version is
    still allowed to talk to this API. Backwards-compatible by design: adding
    a new field here must never break an older POS."""
    def _parse(v: str):
        try:
            return tuple(int(p) for p in (v or "0").split(".")[:3])
        except (ValueError, AttributeError):
            return (0, 0, 0)

    supported = True
    deprecated = False
    if client_version:
        cv = _parse(client_version)
        if cv < _parse(_POS_MIN_SUPPORTED):
            supported = False
        elif cv < _parse(_POS_LATEST):
            deprecated = True

    return {
        "api_contract_version": _POS_API_CONTRACT,
        "min_supported_pos_version": _POS_MIN_SUPPORTED,
        "latest_pos_version": _POS_LATEST,
        "client_version": client_version,
        "supported": supported,
        "deprecated": deprecated,
        "update_channel": "shop-server (staff login required)",
        "update_manifest": CMS_UPDATE_MANIFEST_URL,
    }



@router.get("/api/v1/pages")
def list_public_static_pages():
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM static_pages WHERE is_published = 1 ORDER BY id ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}


@router.get("/api/v1/pages/{slug}")
def get_public_static_page(slug: str):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM static_pages WHERE slug = ? AND is_published = 1", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page introuvable")
        return dict(row)



@router.get("/api/v1/ready")
def api_readiness_check():
    try:
        with db_session() as conn:
            cur = conn.cursor()
            # Ready = the 69 wilayas exist (seeded) and photos can be saved.
            # The owner switching off delivery to some wilayas is a business
            # choice, not a fault: it is reported, not counted against health.
            cur.execute("SELECT COUNT(*) AS cnt FROM delivery_zones")
            zones_cnt = int(cur.fetchone()["cnt"])
            cur.execute("SELECT COUNT(*) AS cnt FROM delivery_zones WHERE is_active = 1")
            w_cnt = int(cur.fetchone()["cnt"])
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE deleted_at IS NULL")
            p_cnt = int(cur.fetchone()["cnt"])
        storage_ok = os.path.isdir(UPLOAD_STORAGE_DIR) and os.access(UPLOAD_STORAGE_DIR, os.W_OK)
        ok = zones_cnt == 69 and storage_ok
        return {
            "ready": ok,
            "status": "ready" if ok else "degraded",
            "database": "connected",
            "storage_writable": storage_ok,
            "active_wilayas": w_cnt,
            "catalog_products": p_cnt,
            "timestamp": int(time.time()),
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")
