"""Online orders, coupons, cash-on-delivery risk and customers (CMS)."""
from fastapi import APIRouter
import re
from typing import Optional
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..whatsapp import build_customer_order_whatsapp_message, dispatch_customer_whatsapp_order_update, normalize_algerian_phone
from ..deps import (
    log_audit,
    require_any_permission,
    require_permission,
)
from ..common import (
    _EMAIL_RE,
    _boutique_info_from_settings,
    _csv_date,
    _excel_csv_response,
    _fr,
    _record_cash_movement,
)

router = APIRouter()



class OrderStatusUpdate(BaseModel):
    status: str = Field(..., regex=r"^(new|pending_confirmation|confirmed|preparing|ready_for_shipment|shipped|delivered|cancelled|returned)$")
    internal_notes: Optional[str] = None


def compute_customer_cod_risk(conn, raw_phone: str) -> dict:
    """
    Anti-Retour COD Scoring Engine:
    Calculates delivered vs returned/cancelled ratios for an Algerian customer phone number
    and checks `customer_phone_blacklist` to flag repeat non-pickup buyers before order confirmation.
    """
    from ..whatsapp import normalize_algerian_phone as _norm_phone
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


# --- ADMIN ORDERS & STOCK RESTORATION ---

@router.get("/api/v1/admin/orders")
def list_admin_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    q: Optional[str] = Query(None, max_length=120),
    admin: dict = Depends(require_permission("orders:write"))
):
    """Newest orders first. `q` finds any order, however old: order number,
    phone (spaces ignored) or customer name (a customer calling about an order
    from months ago is not in the newest 100)."""
    where, params = [], []
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)
    text = (q or "").strip()
    if text:
        digits = re.sub(r"[\s.\-]", "", text)
        where.append("(UPPER(order_reference) LIKE ? OR customer_phone LIKE ? OR LOWER(customer_name) LIKE ?)")
        params += [f"%{text.upper()}%", f"%{digits}%", f"%{text.lower()}%"]
    sql = "SELECT * FROM orders" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(sql, (*params, limit))
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


@router.patch("/api/v1/admin/orders/{order_id}")
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
            raise HTTPException(status_code=404, detail="Commande introuvable")

        prev_status = ord_row["status"]
        stock_deducted = int(ord_row["stock_deducted"])

        # Enforce valid order-status transition rules (Section 3.5)
        terminal_statuses = {"delivered", "cancelled", "returned"}
        if prev_status in terminal_statuses and payload.status != prev_status:
            # Allow delivered -> returned for customer return within 7 days, block all other reversals from terminal states
            if not (prev_status == "delivered" and payload.status == "returned"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Une commande {_fr(prev_status).lower()} ne peut plus changer de statut"
                )

        # A cancelled order gives its promo-code use back (a limited code is not
        # used up by orders that never happened). A returned parcel keeps it.
        # Only once: cancelling an already-cancelled order again gives nothing back.
        if payload.status == "cancelled" and prev_status != "cancelled":
            code_used = dict(ord_row).get("coupon_code")
            if code_used:
                cur.execute(
                    "UPDATE coupons SET usage_count = CASE WHEN usage_count > 0 THEN usage_count - 1 ELSE 0 END WHERE UPPER(code) = ?",
                    (str(code_used).upper(),),
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
        # Treasury: a delivered cash-on-delivery order is money collected; a
        # return after delivery gives it back.
        if payload.status == "delivered" and prev_status != "delivered":
            _record_cash_movement(cur, account="cash_box", movement="inflow", amount=int(ord_row["total_dzd"]),
                                  source_type="cod_collection", reference=ord_row["order_reference"],
                                  description=f"Commande livrée {ord_row['order_reference']} (paiement à la livraison)",
                                  user_id=int(admin["sub"]))
        elif payload.status == "returned" and prev_status == "delivered":
            _record_cash_movement(cur, account="cash_box", movement="outflow", amount=int(ord_row["total_dzd"]),
                                  source_type="cod_refund", reference=ord_row["order_reference"],
                                  description=f"Retour après livraison {ord_row['order_reference']}",
                                  user_id=int(admin["sub"]))
        log_audit(conn, int(admin["sub"]), "update_order_status", "order", str(order_id), {"from": prev_status, "to": payload.status})
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return dict(cur.fetchone())


class CouponCreateInput(BaseModel):
    code: str = Field(..., regex=r"^[A-Z0-9_-]{3,32}$")
    discount_type: str = Field(..., regex=r"^(percentage|fixed_dzd)$")
    discount_value: int = Field(..., gt=0)
    min_order_dzd: int = Field(0, ge=0)
    max_discount_dzd: Optional[int] = None
    usage_limit: Optional[int] = Field(None, ge=1)


@router.post("/api/v1/admin/coupons", status_code=201)
def create_coupon(
    payload: CouponCreateInput,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        code_upper = payload.code.strip().upper()
        cur.execute("SELECT id FROM coupons WHERE UPPER(code) = ?", (code_upper,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Le code promo '{code_upper}' existe déjà")
        cur.execute(
            """INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, max_discount_dzd, usage_limit, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (payload.code.upper(), payload.discount_type, payload.discount_value, payload.min_order_dzd, payload.max_discount_dzd, payload.usage_limit)
        )
        cid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_coupon", "coupon", str(cid), {"code": payload.code.upper()})
        cur.execute("SELECT * FROM coupons WHERE id = ?", (cid,))
        return dict(cur.fetchone())


@router.get("/api/v1/admin/coupons")
def admin_list_coupons(admin: dict = Depends(require_permission("content:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        # Real results per code: orders kept (not cancelled / returned) and the
        # discount they gave.
        cur.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM orders o WHERE UPPER(o.coupon_code) = UPPER(c.code)
                         AND o.status NOT IN ('cancelled', 'returned')) AS orders_count,
                      (SELECT COALESCE(SUM(o.discount_dzd), 0) FROM orders o WHERE UPPER(o.coupon_code) = UPPER(c.code)
                         AND o.status NOT IN ('cancelled', 'returned')) AS discount_given_dzd
               FROM coupons c ORDER BY c.id DESC"""
        )
        return {"items": [dict(r) for r in cur.fetchall()]}


@router.delete("/api/v1/admin/coupons/{coupon_id}")
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


# What a customer really spent, computed from the source (same rules as the
# customer detail and the reports): online orders neither cancelled nor
# returned + in-store sales − in-store refunds. The customers.total_spent_dzd
# column is only a counter bumped when an order is placed, so it is not used.
_CUSTOMER_SPENT_SQL = """
    (SELECT COALESCE(SUM(o.total_dzd), 0) FROM orders o
      WHERE o.customer_id = c.id AND o.status NOT IN ('cancelled', 'returned'))
  + (SELECT COALESCE(SUM(CASE WHEN ps.sale_type = 'refund' THEN -ps.total_dzd ELSE ps.total_dzd END), 0)
       FROM pos_sales ps WHERE ps.customer_id = c.id)"""

_CUSTOMER_COUNT_SQL = """
    (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id AND o.status NOT IN ('cancelled', 'returned'))
  + (SELECT COUNT(*) FROM pos_sales ps WHERE ps.customer_id = c.id AND ps.sale_type = 'sale')"""


# Customers: managed from Commandes (orders:write) and from the till (pos:sell).
_CUSTOMER_MANAGE = require_any_permission(["orders:write", "pos:sell"])


@router.get("/api/v1/admin/customers")
def admin_list_customers(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(_CUSTOMER_MANAGE),
):
    """Best customers first, one page at a time (a shop with 20 000 customers
    sent 5 MB and drew 20 000 table rows); /admin/customers/search finds anyone."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM customers")
        total = int(cur.fetchone()["n"])
        # Totals computed once per table and joined (same figures as
        # _CUSTOMER_SPENT_SQL / _CUSTOMER_COUNT_SQL), not once per customer:
        # with 20 000 customers the per-row version took minutes.
        cur.execute(
            """SELECT c.*,
                      COALESCE(o.spent, 0) + COALESCE(p.spent, 0) AS spent_live,
                      COALESCE(o.cnt, 0) + COALESCE(p.cnt, 0) AS count_live
               FROM customers c
               LEFT JOIN (SELECT customer_id, SUM(total_dzd) AS spent, COUNT(*) AS cnt
                            FROM orders WHERE status NOT IN ('cancelled', 'returned')
                           GROUP BY customer_id) o ON o.customer_id = c.id
               LEFT JOIN (SELECT customer_id,
                                 SUM(CASE WHEN sale_type = 'refund' THEN -total_dzd ELSE total_dzd END) AS spent,
                                 SUM(CASE WHEN sale_type = 'sale' THEN 1 ELSE 0 END) AS cnt
                            FROM pos_sales WHERE customer_id IS NOT NULL
                           GROUP BY customer_id) p ON p.customer_id = c.id
               ORDER BY spent_live DESC, c.id DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        items = []
        for r in cur.fetchall():
            d = dict(r)
            d["total_spent_dzd"] = int(d.pop("spent_live") or 0)
            d["orders_count"] = int(d.pop("count_live") or 0)
            items.append(d)
        return {"items": items, "total": total, "limit": limit, "offset": offset}



@router.get("/api/v1/admin/orders/export.csv")
def admin_export_orders_csv(admin: dict = Depends(require_permission("orders:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = [
            [r["order_reference"], _csv_date(r["created_at"]), _fr(r["status"]), r["customer_name"], r["customer_phone"],
             f'{r["wilaya_code"]} - {r["wilaya_name"]}', r["commune"], _fr(r["delivery_method"]),
             r["subtotal_dzd"], r["delivery_fee_dzd"], r["total_dzd"], _fr(r["payment_method"])]
            for r in cur.fetchall()
        ]
    return _excel_csv_response(
        "commandes_mus_luxury.csv",
        ["Référence", "Date", "Statut", "Client", "Téléphone", "Wilaya", "Commune", "Livraison",
         "Articles (DA)", "Frais de livraison (DA)", "Total (DA)", "Paiement"],
        rows,
    )


@router.get("/api/v1/admin/orders/{order_id}/delivery-note")
def admin_get_order_delivery_note(
    order_id: int,
    admin: dict = Depends(require_permission("orders:write"))
):
    """Delivery note (bon de livraison): shipping-focused document without any
    financial detail beyond COD amount. Handed to the courier / stapled on the
    parcel so the recipient can verify their items match."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        o = cur.fetchone()
        if not o:
            raise HTTPException(status_code=404, detail="Commande introuvable")
        od = dict(o)
        cur.execute(
            """SELECT oi.product_name, oi.variant_title, oi.sku, oi.quantity
               FROM order_items oi WHERE oi.order_id = ? ORDER BY oi.id""",
            (order_id,),
        )
        od["items"] = [dict(r) for r in cur.fetchall()]
        od["total_items"] = sum(int(it["quantity"]) for it in od["items"])
        od["boutique_info"] = _boutique_info_from_settings(conn)
        od["document_title"] = "Bon de livraison"
        od["cod_amount_dzd"] = int(od["total_dzd"]) if od["payment_method"] == "cod" else 0
        return od



@router.get("/api/v1/admin/orders/{order_id}/invoice")
def admin_get_order_invoice(
    order_id: int,
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        o = cur.fetchone()
        if not o:
            raise HTTPException(status_code=404, detail="Commande introuvable")
        od = dict(o)
        cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = [dict(r) for r in cur.fetchall()]
        od["items"] = items
        od["boutique_info"] = {
            **_boutique_info_from_settings(conn),
            "payment_notice": "Paiement en espèces à la livraison",
        }
        return od



# ============================================================================
# ANTI-RETOUR COD: PHONE RETURN-RATE SCORING & BLACKLIST MANAGEMENT
# ============================================================================

class CodBlacklistInput(BaseModel):
    phone: str = Field(..., min_length=8, max_length=30)
    reason: str = Field("Retour abusif / Non-récupération COD", min_length=3, max_length=250)
    is_blocked: bool = True


@router.get("/api/v1/admin/cod-risk/check")
def admin_check_phone_cod_risk(
    phone: str = Query(..., min_length=8),
    admin: dict = Depends(require_permission("orders:write"))
):
    with db_session() as conn:
        return compute_customer_cod_risk(conn, phone)


@router.get("/api/v1/admin/cod-risk/blacklist")
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


@router.post("/api/v1/admin/cod-risk/blacklist")
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


@router.delete("/api/v1/admin/cod-risk/blacklist/{phone}")
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



@router.post("/api/v1/admin/orders/{order_id}/notify-whatsapp")
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
            raise HTTPException(status_code=404, detail="Commande introuvable")
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


# ============================================================================
# CUSTOMER MANAGEMENT — walk-in and registered customers, cross-channel history
# Customers are shared between the online store and the POS. A POS cashier can
# create a walk-in customer with just a name and phone; online orders keep
# collecting the delivery details. History combines online orders and in-store
# sales. Privacy: only the fields the business needs are stored.
# ============================================================================



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
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS s FROM orders WHERE customer_id = ? AND status NOT IN ('cancelled', 'returned')", (customer_id,))
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



@router.get("/api/v1/admin/customers/search")
def admin_search_customers(q: str = Query(..., min_length=1, max_length=120), admin: dict = Depends(_CUSTOMER_MANAGE)):
    like = f"%{q.strip()}%"
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT * FROM (
                   SELECT c.id, c.full_name, c.phone, c.email, c.wilaya_code, c.commune,
                          {_CUSTOMER_COUNT_SQL} AS orders_count, {_CUSTOMER_SPENT_SQL} AS total_spent_dzd
                   FROM customers c WHERE c.full_name LIKE ? OR c.phone LIKE ?
               ) AS x ORDER BY total_spent_dzd DESC, id DESC LIMIT 20""",
            (like, like),
        )
        return {"items": [dict(r) for r in cur.fetchall()]}



@router.get("/api/v1/admin/customers/{customer_id}")
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



@router.post("/api/v1/admin/customers", status_code=201)
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



@router.put("/api/v1/admin/customers/{customer_id}")
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
