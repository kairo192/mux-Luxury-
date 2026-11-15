"""Stock: movements, adjustments, counts and write-offs."""
from fastapi import APIRouter
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..deps import (
    log_audit,
    require_permission,
)
from ..common import (
    _doc_prefix,
    _id_chunks,
)

router = APIRouter()



@router.get("/api/v1/admin/inventory/movements")
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



@router.get("/api/v1/admin/inventory/counts")
def admin_list_counts(
    limit: int = Query(30, ge=1, le=200),
    admin: dict = Depends(require_permission("inventory:write")),
):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory_counts ORDER BY id DESC LIMIT ?", (limit,))
        return {"items": [dict(r) for r in cur.fetchall()]}



@router.post("/api/v1/admin/inventory/counts", status_code=201)
def admin_open_count(payload: CountOpenInput, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        ref = ""
        count_id = None
        for _attempt in range(3):
            ref = f"{_doc_prefix(cur, 'receipt_prefix_inventory', 'INV')}-{int(time.time()) % 100000:05d}-{secrets.token_hex(2).upper()}"
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



@router.get("/api/v1/admin/inventory/counts/{count_id}")
def admin_get_count(count_id: int, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session() as conn:
        return _count_payload(conn, count_id)



@router.put("/api/v1/admin/inventory/counts/{count_id}/lines")
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



@router.delete("/api/v1/admin/inventory/counts/{count_id}/lines/{line_id}")
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



@router.post("/api/v1/admin/inventory/counts/{count_id}/apply")
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
            "SELECT id, variant_id, expected_qty, counted_qty FROM inventory_count_items WHERE count_id = ?",
            (count_id,),
        )
        lines = [dict(r) for r in cur.fetchall()]
        if not lines:
            raise HTTPException(status_code=400, detail="Aucune ligne à appliquer")

        applied = 0
        for line in lines:
            # Apply the DIFFERENCE the count found (counted − stock the system
            # showed when the item was counted) to the live stock. Sales or
            # receptions made between counting and applying are therefore kept:
            # counted 5 of 5, then 1 sold → stays 4 (setting it to 5 would
            # "un-sell" the item).
            # Lock the row first (PostgreSQL row lock / SQLite write lock): no
            # sale can slip in between reading the stock and writing it.
            cur.execute("UPDATE product_variants SET stock_qty = stock_qty WHERE id = ?", (line["variant_id"],))
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (line["variant_id"],))
            v = cur.fetchone()
            if not v:
                continue
            prev_q = int(v["stock_qty"])
            diff = int(line["counted_qty"]) - int(line["expected_qty"])
            new_q = max(0, prev_q + diff)
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



@router.get("/api/v1/admin/inventory/write-off-reasons")
def admin_writeoff_reasons(admin: dict = Depends(require_permission("inventory:write"))):
    labels = {
        "damaged": "Produit endommagé",
        "lost": "Perte / vol",
        "return_to_supplier": "Retour fournisseur",
        "promotional_giveaway": "Cadeau / promo",
        "stocktake_correction": "Correction d'inventaire",
    }
    return {"items": [{"code": c, "label": labels[c]} for c in sorted(_WRITEOFF_REASONS)]}



@router.post("/api/v1/admin/inventory/write-off", status_code=201)
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
# LOW STOCK ALERTS — actionable reorder view with incoming-stock awareness.
# For each variant at or below its low_stock_threshold we show the current
# stock, the quantity on order (from non-cancelled purchase orders that are
# not fully received) and the typical 30-day velocity. The CMS uses this to
# help the owner decide what to reorder and how much.
# ============================================================================


@router.get("/api/v1/admin/inventory/low-stock")
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
        # 30-day velocity = units sold across both channels in the last 30 days
        # (web orders not cancelled/returned + till sales - till refunds), for all
        # listed variants in two grouped queries instead of one query per variant.
        sold: Dict[int, int] = {}
        for chunk in _id_chunks([r["variant_id"] for r in rows]):
            marks = ",".join("?" for _ in chunk)
            cur.execute(
                f"""SELECT oi.variant_id AS vid, COALESCE(SUM(oi.quantity), 0) AS q
                    FROM order_items oi JOIN orders o ON o.id = oi.order_id
                    WHERE oi.variant_id IN ({marks}) AND o.status NOT IN ('cancelled', 'returned')
                      AND o.created_at >= ?
                    GROUP BY oi.variant_id""",
                (*chunk, thirty_days_ago),
            )
            for r in cur.fetchall():
                sold[r["vid"]] = sold.get(r["vid"], 0) + int(r["q"])
            cur.execute(
                f"""SELECT psi.variant_id AS vid,
                           COALESCE(SUM(CASE ps.sale_type WHEN 'sale' THEN psi.quantity
                                                          WHEN 'refund' THEN -psi.quantity ELSE 0 END), 0) AS q
                    FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                    WHERE psi.variant_id IN ({marks}) AND ps.created_at >= ?
                    GROUP BY psi.variant_id""",
                (*chunk, thirty_days_ago),
            )
            for r in cur.fetchall():
                sold[r["vid"]] = sold.get(r["vid"], 0) + int(r["q"])
        for row in rows:
            row["velocity_30d"] = sold.get(row["variant_id"], 0)
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



@router.post("/api/v1/admin/inventory/counts/{count_id}/cancel")
def admin_cancel_count(count_id: int, admin: dict = Depends(require_permission("inventory:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, reference FROM inventory_counts WHERE id = ?", (count_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")
        if c["status"] != "open":
            raise HTTPException(status_code=409, detail="Inventaire déjà appliqué")
        cur.execute("UPDATE inventory_counts SET status = 'cancelled' WHERE id = ? AND status = 'open'", (count_id,))
        if cur.rowcount != 1:  # applied by a request that finished in between
            raise HTTPException(status_code=409, detail="Inventaire déjà appliqué")
        log_audit(conn, int(admin["sub"]), "cancel_inventory_count", "inventory_count", str(count_id), {"reference": c["reference"]})
        return _count_payload(conn, count_id)
