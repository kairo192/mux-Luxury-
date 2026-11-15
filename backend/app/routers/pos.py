"""Point of sale: register, sales, refunds, catalog mirror, devices and offline sync."""
from fastapi import APIRouter
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from ..database import PostgresCompatConnection, db_session
from ..deps import (
    log_audit,
    require_permission,
)
from ..common import (
    _account_for_method,
    _boutique_info_from_settings,
    _children_by_parent,
    _doc_prefix,
    _fr,
    _get_open_register,
    _record_cash_movement,
    _register_runtime_totals,
)

router = APIRouter()




@router.get("/api/v1/admin/sync/delta")
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
    # Full order records (names, phones, addresses) only for accounts that may
    # manage orders; everyone with dashboard access still gets stock and moves.
    can_see_orders = "orders:write" in admin.get("perms", [])
    with db_session() as conn:
        cur = conn.cursor()
        # Watermarks first, and every delta read bounded by them: a row written
        # while this runs is left for the next sync instead of being skipped.
        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_oid FROM orders")
        latest_order_id = cur.fetchone()["max_oid"]
        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_mid FROM inventory_movements")
        latest_movement_id = cur.fetchone()["max_mid"]

        new_orders: list = []
        if can_see_orders:
            cur.execute("SELECT * FROM orders WHERE id > ? AND id <= ? ORDER BY id DESC",
                        (since_order_id, latest_order_id))
            new_orders = [dict(r) for r in cur.fetchall()]
            items_by_order = _children_by_parent(cur, "order_items", "order_id", [o["id"] for o in new_orders])
            for od in new_orders:
                od["items"] = items_by_order.get(od["id"], [])
        else:
            latest_order_id = since_order_id

        cur.execute("SELECT * FROM inventory_movements WHERE id > ? AND id <= ? ORDER BY id DESC",
                    (since_movement_id, latest_movement_id))
        new_movements = [dict(m) for m in cur.fetchall()]

        cur.execute("SELECT id, sku, stock_qty, price_override_dzd FROM product_variants ORDER BY id ASC")
        variant_stocks = [dict(v) for v in cur.fetchall()]

        return {
            "server_timestamp": int(time.time()),
            "latest_order_id": latest_order_id,
            "latest_movement_id": latest_movement_id,
            "missed_orders_count": len(new_orders),
            "new_orders": new_orders,
            "new_movements": new_movements,
            "current_variant_stocks": variant_stocks,
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



def _pos_sale_payload(conn, sale_id: int) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pos_sales WHERE id = ?", (sale_id,))
    s = cur.fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="Vente introuvable")
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



@router.post("/api/v1/admin/pos/register/open", status_code=201)
def pos_open_register(payload: RegisterOpenInput, admin: dict = Depends(require_permission("register:manage"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        existing = _get_open_register(conn)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une caisse (n° {existing['id']}) est déjà ouverte. Clôturez-la avant d'en ouvrir une autre.",
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
        sd = dict(cur.fetchone())
        # Same shape as /register/current: the float shows as expected cash at once.
        totals = _register_runtime_totals(conn, sd["id"])
        sd.update(totals)
        sd["expected_cash_dzd"] = int(sd["opening_float_dzd"]) + totals["net_cash_dzd"]
        return sd



@router.get("/api/v1/admin/pos/register/current")
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



@router.post("/api/v1/admin/pos/register/close")
def pos_close_register(payload: RegisterCloseInput, admin: dict = Depends(require_permission("register:manage"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        session = _get_open_register(conn)
        if not session:
            raise HTTPException(status_code=404, detail="Aucune caisse ouverte à clôturer.")
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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette caisse est déjà clôturée.")
        # The counted drawer is the truth: a shortage leaves the cash box, a
        # surplus enters it, so the treasury matches the money really there.
        if variance != 0:
            _record_cash_movement(
                cur, account="cash_box", movement="inflow" if variance > 0 else "outflow", amount=abs(variance),
                source_type="register_variance", reference=f"CAISSE-{session_id}",
                description=f"Écart de caisse à la clôture ({'excédent' if variance > 0 else 'manque'} de {abs(variance)} DA)",
                user_id=int(admin["sub"]),
            )
        log_audit(conn, int(admin["sub"]), "close_register", "cash_register_session", str(session_id), {
            "expected_cash_dzd": expected_cash, "counted_cash_dzd": payload.counted_cash_dzd, "variance_dzd": variance,
        })
        cur.execute("SELECT * FROM cash_register_sessions WHERE id = ?", (session_id,))
        return dict(cur.fetchone())



@router.get("/api/v1/admin/pos/register/sessions")
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
        items = [dict(r) for r in cur.fetchall()]
        # Totals are stored when a register is closed; an open one is computed live.
        for sd in items:
            if sd.get("status") == "open" or sd.get("closed_at") in (None, ""):
                totals = _register_runtime_totals(conn, sd["id"])
                sd.update(totals)
                sd["expected_cash_dzd"] = int(sd["opening_float_dzd"]) + totals["net_cash_dzd"]
                # Same field names as a closed register.
                sd["total_sales_dzd"] = totals["sales_total_dzd"]
                sd["total_refunds_dzd"] = totals["refunds_total_dzd"]
        return {"items": items}



# ============================================================================
# POS catalog mirror — snapshot + incremental deltas
# ----------------------------------------------------------------------------
# The Desktop CMS keeps a local SQLite copy of the catalog so the POS can
# look up products and sell them even with zero connectivity. These two
# endpoints feed that mirror:
#
#   GET /api/v1/admin/pos/catalog/snapshot
#        Full dump of every active product + variant. Used on first launch,
#        after a mirror reset, or when the mirror is older than a week.
#
#   GET /api/v1/admin/pos/catalog/deltas?since=<iso>
#        Everything created or updated since `since`. The mirror calls this
#        every ~30 seconds when online. Deleted rows come back with
#        `deleted: true` so the mirror can tombstone them.
#
# Rows are flat (no nested arrays), keep every field the POS lookup actually
# uses, and omit anything that would bloat the payload (long descriptions,
# image blobs). Expect ~150 bytes/variant on the wire.
# ============================================================================

def _pos_catalog_products_rows(conn, since_iso: Optional[str] = None):
    cur = conn.cursor()
    base = ("SELECT id, sku, name_fr, name_ar, name_en, selling_price_dzd, "
            "purchase_cost_dzd, main_image_url, status, category_id, updated_at, "
            "deleted_at FROM products")
    if since_iso:
        # Normalize for SQLite: cursors are `YYYY-MM-DDTHH:MM:SSZ`, DB values
        # are `YYYY-MM-DD HH:MM:SS`. datetime() parses both forms so the >=
        # comparison lines up on either engine.
        cur.execute(
            base + " WHERE datetime(updated_at) >= datetime(?) "
                   "   OR datetime(deleted_at) >= datetime(?)",
            (since_iso, since_iso),
        )
    else:
        cur.execute(base + " WHERE deleted_at IS NULL AND status = 'published'")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        rows.append({
            "id": d["id"],
            "sku": d.get("sku"),
            "name_fr": d.get("name_fr") or "",
            "name_ar": d.get("name_ar") or "",
            "name_en": d.get("name_en") or "",
            "selling_price_dzd": int(d.get("selling_price_dzd") or 0),
            "purchase_cost_dzd": int(d.get("purchase_cost_dzd") or 0),
            "main_image_url": d.get("main_image_url"),
            "status": d.get("status") or "draft",
            "category_id": d.get("category_id"),
            "updated_at": d.get("updated_at"),
            "deleted": bool(d.get("deleted_at")),
        })
    return rows



def _pos_catalog_variants_rows(conn, since_iso: Optional[str] = None):
    cur = conn.cursor()
    base = ("SELECT pv.id, pv.product_id, pv.sku, pv.title, pv.barcode, "
            "pv.price_override_dzd, pv.stock_qty, pv.is_active, pv.updated_at "
            "FROM product_variants pv")
    if since_iso:
        cur.execute(base + " WHERE datetime(pv.updated_at) >= datetime(?)",
                    (since_iso,))
    else:
        cur.execute(base + " WHERE pv.is_active = 1")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        rows.append({
            "id": d["id"],
            "product_id": d["product_id"],
            "sku": d.get("sku"),
            "title": d.get("title") or "",
            "barcode": d.get("barcode"),
            "price_override_dzd": (int(d["price_override_dzd"])
                                    if d.get("price_override_dzd") is not None else None),
            "stock_qty": int(d.get("stock_qty") or 0),
            "is_active": bool(d.get("is_active")),
            "updated_at": d.get("updated_at"),
            "deleted": not bool(d.get("is_active")),
        })
    return rows



def _catalog_epoch(conn) -> str:
    """Changes when the database is reset or restored: POS PCs that see a new
    epoch drop their offline catalog and download it again (deltas cannot
    describe rows that were physically removed)."""
    cur = conn.cursor()
    cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", ("catalog_epoch",))
    row = cur.fetchone()
    return str(row["setting_value"]) if row else "initial"



# A row's updated_at is stamped when its transaction STARTS writing (on
# PostgreSQL, CURRENT_TIMESTAMP is the transaction start), but it becomes
# visible only at commit. The cursor therefore trails the clock by this margin:
# each delta re-sends the last minute (the offline catalog overwrites rows it
# already has), so a change committed a few seconds late is never skipped.
SYNC_CURSOR_MARGIN = timedelta(seconds=60)


def _sync_cursor_now() -> str:
    return (datetime.utcnow() - SYNC_CURSOR_MARGIN).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/api/v1/admin/pos/catalog/snapshot")
def pos_catalog_snapshot(admin: dict = Depends(require_permission("pos:read"))):
    """Full catalog dump — call this once, then prefer `/catalog/deltas`.

    The cursor returned is taken BEFORE the read and trails the clock by
    SYNC_CURSOR_MARGIN, and the next delta includes it (`>=`). A row changed
    while this runs, or committed late, is sent again rather than missed (the
    offline catalog simply overwrites a row it already has)."""
    cursor = _sync_cursor_now()
    with db_session() as conn:
        products = _pos_catalog_products_rows(conn, since_iso=None)
        variants = _pos_catalog_variants_rows(conn, since_iso=None)
        epoch = _catalog_epoch(conn)
    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cursor": cursor,
        "catalog_epoch": epoch,
        "products": products,
        "variants": variants,
        "stats": {
            "products": len(products),
            "variants": len(variants),
            "variants_with_barcode": sum(1 for v in variants if v.get("barcode")),
        },
    }



@router.get("/api/v1/admin/pos/catalog/deltas")
def pos_catalog_deltas(
    since: str = Query(..., min_length=1, max_length=64,
                       description="ISO-8601 timestamp of the last sync (use snapshot.cursor)"),
    admin: dict = Depends(require_permission("pos:read")),
):
    """Everything created / updated since `since`. Variants that went inactive
    arrive with `deleted: true`; products with `deleted_at` ditto. The mirror
    is forward-only — the client never re-asks for a cursor it already saw."""
    since_s = since.strip()
    if not since_s:
        raise HTTPException(status_code=400, detail="`since` is required")
    cursor = _sync_cursor_now()  # taken BEFORE the reads; see pos_catalog_snapshot
    with db_session() as conn:
        products = _pos_catalog_products_rows(conn, since_iso=since_s)
        variants = _pos_catalog_variants_rows(conn, since_iso=since_s)
        epoch = _catalog_epoch(conn)
    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cursor": cursor,
        "catalog_epoch": epoch,
        "since": since_s,
        "products": products,
        "variants": variants,
        "stats": {
            "products": len(products),
            "variants": len(variants),
        },
    }



@router.get("/api/v1/admin/pos/lookup")
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



@router.post("/api/v1/admin/pos/sales", status_code=201)
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
                detail="Aucune caisse ouverte. Ouvrez la caisse avant de vendre.",
            )

        # Validate optional customer
        if payload.customer_id is not None:
            cur.execute("SELECT id FROM customers WHERE id = ?", (payload.customer_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Client introuvable")

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
                raise HTTPException(status_code=404, detail=f"Un article n'est plus disponible")
            qty = m["quantity"]
            if v["stock_qty"] < qty:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Stock insuffisant pour '{v['product_name']} ({v['title']})' : demandé {qty}, disponible {v['stock_qty']}",
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
                detail=f"Le paiement ({paid} DA) doit être égal au total de la vente ({total_dzd} DA)",
            )

        sale_ref = ""
        sale_id = None
        for _attempt in range(3):
            sale_ref = f"{_doc_prefix(cur, 'receipt_prefix_pos', 'POS')}-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
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
                                    detail=f"Stock insuffisant pour '{v['product_name']} ({v['title']})'")
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
            _record_cash_movement(cur, account=_account_for_method(pm.method), movement="inflow",
                                  amount=int(pm.amount_dzd), source_type="pos_sale", reference=sale_ref,
                                  description=f"Vente magasin {sale_ref}", user_id=int(admin["sub"]))

        log_audit(conn, int(admin["sub"]), "pos_sale", "pos_sale", str(sale_id), {
            "sale_reference": sale_ref, "total_dzd": total_dzd, "items": len(resolved),
        })
        return _pos_sale_payload(conn, int(sale_id))



@router.get("/api/v1/admin/pos/sales")
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



@router.get("/api/v1/admin/pos/sales/{sale_id}")
def pos_get_sale(sale_id: int, admin: dict = Depends(require_permission("pos:read"))):
    with db_session() as conn:
        return _pos_sale_payload(conn, sale_id)



@router.get("/api/v1/admin/pos/sales/{sale_id}/invoice")
def pos_get_sale_invoice(sale_id: int, admin: dict = Depends(require_permission("pos:read"))):
    """Formal invoice payload (as opposed to the compact receipt): includes the
    full boutique legal identity, line-item breakdown with unit prices and VAT,
    and the customer record when attached. The CMS renders this as an A4 page
    the owner prints on a regular printer for business customers."""
    with db_session() as conn:
        sale = _pos_sale_payload(conn, sale_id)
        # Compute the tax rate from stored tax_dzd vs the taxable base, so historical
        # invoices keep their original rate even if the current setting changes.
        taxable = int(sale["subtotal_dzd"]) - int(sale["discount_dzd"])
        tax_dzd = int(sale["tax_dzd"])
        tax_percent = round((tax_dzd / taxable) * 100, 2) if (taxable > 0 and tax_dzd > 0) else 0
        sale["tax_percent"] = tax_percent
        sale["is_business_invoice"] = bool(sale.get("customer"))
        sale["document_title"] = "Facture" if sale["sale_type"] == "sale" else "Avoir (remboursement)"
        return sale


@router.post("/api/v1/admin/pos/sales/{sale_id}/refund", status_code=201)
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
            raise HTTPException(status_code=404, detail="Vente introuvable")
        if orig["sale_type"] != "sale":
            raise HTTPException(status_code=400, detail="Seule une vente peut être remboursée")
        if orig["status"] in ("refunded", "voided"):
            raise HTTPException(status_code=409, detail=f"Vente déjà {_fr(orig['status']).lower()}")

        session = _get_open_register(conn)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aucune caisse ouverte. Ouvrez la caisse avant de rembourser.",
            )

        # Sold quantities per variant on the original sale
        cur.execute(
            "SELECT variant_id, product_id, product_name, variant_title, sku, unit_price_dzd, quantity, line_total_dzd "
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
            raise HTTPException(status_code=400, detail="Tout a déjà été remboursé sur cette vente")

        # A refund gives back what the customer actually PAID: each unit at its
        # share of the ticket total (line discounts, ticket discount and tax
        # included) — never the list price.
        items_total = sum(int(l["line_total_dzd"] or 0) for l in sold.values())
        paid_total = int(orig["total_dzd"])
        cur.execute(
            "SELECT COALESCE(SUM(total_dzd), 0) AS s FROM pos_sales WHERE sale_type = 'refund' AND reverses_sale_id = ?",
            (sale_id,),
        )
        already_refunded = int(cur.fetchone()["s"])
        refundable_left = max(0, paid_total - already_refunded)

        refund_lines = []
        refund_subtotal = 0      # list price of the returned units
        refund_total = 0         # money given back
        for vid, qty in requested.items():
            if vid not in sold:
                raise HTTPException(status_code=400, detail=f"Cet article ne fait pas partie de la vente n° {sale_id}")
            remaining = sold[vid]["quantity"] - refunded_qty.get(vid, 0)
            if qty > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Impossible de rembourser {qty} pièce(s) : il en reste {remaining} remboursable(s)",
                )
            unit_price = int(sold[vid]["unit_price_dzd"])
            sold_line_total = int(sold[vid]["line_total_dzd"] or 0)
            share = (sold_line_total / items_total) if items_total > 0 else 0
            line_paid = round(paid_total * share * qty / int(sold[vid]["quantity"]))
            refund_subtotal += unit_price * qty
            refund_total += line_paid
            refund_lines.append([sold[vid], qty, unit_price, line_paid])

        # Last refund on the ticket: give back exactly what is left (no rounding drift).
        empties_ticket = all(
            refunded_qty.get(v, 0) + requested.get(v, 0) >= sold[v]["quantity"] for v in sold
        )
        if empties_ticket or refund_total > refundable_left:
            diff = refundable_left - refund_total
            refund_total = refundable_left
            if refund_lines:
                refund_lines[-1][3] += diff

        # The credit note keeps the ticket's tax: the refunded share of it (the
        # last refund takes exactly what is left), and the discount is what
        # brings list price + tax down to the money given back.
        orig_tax = int(orig["tax_dzd"] or 0)
        cur.execute(
            "SELECT COALESCE(SUM(tax_dzd), 0) AS t FROM pos_sales WHERE sale_type = 'refund' AND reverses_sale_id = ?",
            (sale_id,),
        )
        tax_left = max(0, orig_tax - int(cur.fetchone()["t"]))
        if empties_ticket:
            refund_tax = tax_left
        else:
            refund_tax = min(tax_left, round(orig_tax * refund_total / paid_total)) if paid_total > 0 else 0
        refund_discount = refund_subtotal + refund_tax - refund_total

        ref = ""
        refund_id = None
        for _attempt in range(3):
            ref = f"{_doc_prefix(cur, 'receipt_prefix_refund', 'RMA')}-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
            try:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        reverses_sale_id, subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, notes)
                       VALUES (?, ?, ?, ?, 'refund', ?, ?, ?, ?, ?, 'completed', ?)""",
                    (ref, int(session["id"]), int(admin["sub"]), orig["customer_id"], sale_id,
                     refund_subtotal, refund_discount, refund_tax, refund_total, payload.notes),
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (refund_id, line["product_id"], line["variant_id"], line["product_name"],
                 line["variant_title"], line["sku"], unit_price, unit_price * qty - line_total, qty, line_total),
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
            (refund_id, payload.refund_method, refund_total),
        )
        _record_cash_movement(cur, account=_account_for_method(payload.refund_method), movement="outflow",
                              amount=refund_total, source_type="pos_refund", reference=ref,
                              description=f"Remboursement {ref} (vente {orig['sale_reference']})", user_id=int(admin["sub"]))

        # Update original sale status: fully vs partially refunded
        total_refunded_after = {vid: refunded_qty.get(vid, 0) for vid in sold}
        for line, qty, _u, _lt in refund_lines:
            total_refunded_after[line["variant_id"]] = total_refunded_after.get(line["variant_id"], 0) + qty
        fully = all(total_refunded_after.get(vid, 0) >= sold[vid]["quantity"] for vid in sold)
        new_status = "refunded" if fully else "partially_refunded"
        cur.execute("UPDATE pos_sales SET status = ? WHERE id = ?", (new_status, sale_id))

        log_audit(conn, int(admin["sub"]), "pos_refund", "pos_sale", str(refund_id), {
            "refund_reference": ref, "reverses_sale_id": sale_id,
            "refund_total_dzd": refund_total, "original_new_status": new_status,
        })
        return _pos_sale_payload(conn, int(refund_id))


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



def _is_lan_address(host: str) -> bool:
    """True for addresses of a shop's local network (private / link-local IPs,
    .local names). Loopback is NOT included: it is the server's own machine,
    so a failed probe there is a real failure."""
    import ipaddress
    h = (host or "").strip().lower()
    if h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return (ip.is_private or ip.is_link_local) and not ip.is_loopback



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



@router.get("/api/v1/admin/devices")
def admin_list_devices(admin: dict = Depends(require_permission("devices:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices ORDER BY device_type, is_default DESC, id")
        return {"items": [_device_payload(r) for r in cur.fetchall()]}



@router.post("/api/v1/admin/devices", status_code=201)
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



@router.put("/api/v1/admin/devices/{device_id}")
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



@router.delete("/api/v1/admin/devices/{device_id}")
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



@router.post("/api/v1/admin/devices/{device_id}/set-default")
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



@router.post("/api/v1/admin/devices/{device_id}/test")
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

        if payload.success is not None:
            # Honest result reported by the shop PC (the desktop app printed a
            # test ticket / label on the real printer).
            method = "client_reported"
            status_val = "ok" if payload.success else "error"
            error = None if payload.success else (payload.error or "Échec rapporté par le poste local")
        elif dev["connection_type"] == "network":
            method = "tcp_probe"
            host = str(config.get("host") or "").strip()
            port = config.get("port")
            if not host or port is None:
                status_val, error = "error", "Configuration réseau incomplète (adresse IP / port)"
            else:
                ok, probe_err = _tcp_probe(host, int(port))
                if ok:
                    status_val, error = "ok", None
                elif _is_lan_address(host):
                    # A server in the cloud cannot see the shop's local network:
                    # a failed probe says nothing about the printer itself.
                    status_val = "unknown"
                    error = (f"Le serveur ne peut pas joindre {host} : c'est une adresse du réseau local de la boutique. "
                             "Lancez le test depuis l'application de bureau installée sur le poste de la boutique.")
                else:
                    status_val = "error"
                    error = f"Connexion impossible à {host}:{port} — {probe_err}"
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



def _client_ts_to_utc_text(value: Optional[str]) -> Optional[str]:
    """Offline sale time sent by the POS ('2026-11-11T21:30:00', '…Z', '…+01:00')
    -> stored form 'YYYY-MM-DD HH:MM:SS' in UTC (no zone = already UTC, as
    sent by toISOString). None when missing or unreadable."""
    text = (value or "").strip()
    if not text or not _ISO_CREATED_RE.match(text):
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")



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

    client_ts = _client_ts_to_utc_text(op.created_at_client)
    created_at_valid = client_ts is not None

    # 4. Create the sale (idempotency_key = client txn id)
    sale_ref = ""
    sale_id = None
    for _attempt in range(3):
        sale_ref = f"{_doc_prefix(cur, 'receipt_prefix_pos', 'POS')}-{int(time.time()) % 100000:05d}-{secrets.token_hex(3).upper()}"
        try:
            if created_at_valid:
                cur.execute(
                    """INSERT INTO pos_sales
                       (sale_reference, register_session_id, cashier_admin_id, customer_id, sale_type,
                        subtotal_dzd, discount_dzd, tax_dzd, total_dzd, status, idempotency_key, notes, created_at)
                       VALUES (?, ?, ?, ?, 'sale', ?, ?, ?, ?, 'completed', ?, ?, ?)""",
                    (sale_ref, reg, cashier_id, payload.customer_id, subtotal_dzd, discount_dzd, tax_dzd,
                     total_dzd, txn, payload.notes, client_ts),
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
        _record_cash_movement(cur, account=_account_for_method(pm.method), movement="inflow",
                              amount=int(pm.amount_dzd), source_type="pos_sale", reference=sale_ref,
                              description=f"Vente magasin {sale_ref} (hors ligne)", user_id=cashier_id)

    if reg is not None:
        _reconcile_closed_register(conn, reg, sale_ref, cashier_id)

    log_audit(conn, cashier_id, "pos_sale_offline_sync", "pos_sale", str(sale_id), {
        "client_txn_id": txn, "sale_reference": sale_ref, "total_dzd": total_dzd,
    })
    return {"client_txn_id": txn, "status": "created", "sale_reference": sale_ref, "sale_id": int(sale_id), "total_dzd": total_dzd}



def _reconcile_closed_register(conn, session_id: int, sale_ref: str, user_id: int) -> None:
    """An offline sale that reaches the server after its register was closed:
    the drawer counted at closing already held that cash, so closing booked it
    as a surplus. Recompute the closed register's totals and expected cash with
    the sale, and move only the CHANGE in its variance through the cash box
    (the sale's own payment is already booked), so the money counts once."""
    cur = conn.cursor()
    # Two sales synced at the same moment must not both recompute from totals
    # that miss the other one: on PostgreSQL the session row is locked first
    # (the second waits, then reads the first's sale). NO KEY UPDATE, not
    # UPDATE: each transaction already holds a KEY SHARE lock on this row from
    # inserting its sale (foreign key), which FOR UPDATE would wait on — a
    # deadlock. SQLite has no row locks; its BEGIN IMMEDIATE already lets one
    # writer through at a time.
    lock = " FOR NO KEY UPDATE" if isinstance(conn, PostgresCompatConnection) else ""
    cur.execute("SELECT * FROM cash_register_sessions WHERE id = ?" + lock, (session_id,))
    sess = cur.fetchone()
    if not sess or sess["status"] != "closed" or sess["counted_cash_dzd"] is None:
        return
    totals = _register_runtime_totals(conn, session_id)
    expected = int(sess["opening_float_dzd"]) + totals["net_cash_dzd"]
    variance = int(sess["counted_cash_dzd"]) - expected
    cur.execute(
        """UPDATE cash_register_sessions
           SET expected_cash_dzd = ?, variance_dzd = ?,
               total_sales_dzd = ?, total_refunds_dzd = ?, sales_count = ?
           WHERE id = ?""",
        (expected, variance, totals["sales_total_dzd"], totals["refunds_total_dzd"], totals["sales_count"], session_id),
    )
    change = variance - int(sess["variance_dzd"] or 0)
    if change != 0:
        _record_cash_movement(
            cur, account="cash_box", movement="inflow" if change > 0 else "outflow", amount=abs(change),
            source_type="register_variance", reference=f"CAISSE-{session_id}",
            description=f"Écart de caisse corrigé : vente {sale_ref} synchronisée après la clôture",
            user_id=user_id,
        )


@router.post("/api/v1/admin/pos/sync")
def pos_offline_sync(payload: PosSyncInput, admin: dict = Depends(require_permission("pos:sell"))):
    results = []
    for op in payload.operations:
        try:
            with db_session(commit=True) as conn:
                if not conn.in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                result = _process_offline_sale(conn, op, int(admin["sub"]))
            # Reported only once the commit has succeeded (a failed commit
            # lands in `failed` below, never as `created` too).
            results.append(result)
        except HTTPException as he:
            results.append({"client_txn_id": op.client_txn_id, "status": "conflict", "reason": "server_rejected", "error": he.detail})
        except Exception as exc:  # noqa: BLE001
            results.append({"client_txn_id": op.client_txn_id, "status": "failed", "error": str(exc)})

    summary = {"created": 0, "duplicate": 0, "conflict": 0, "failed": 0}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"results": results, "summary": summary, "synced_count": len(payload.operations)}
