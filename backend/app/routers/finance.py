"""Purchases, suppliers, expenses, treasury and accounting."""
from fastapi import APIRouter
import secrets
import time
from typing import List, Optional
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from ..database import db_session
from ..deps import (
    log_audit,
    require_permission,
)
from ..common import (
    _UNIT_COST_SQL,
    _account_for_method,
    _boutique_info_from_settings,
    _children_by_parent,
    _excel_csv_response,
    _record_cash_movement,
    _scalar,
    _shop_now,
    _stock_losses_dzd,
)

router = APIRouter()


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
    movement_type: str = Field("inflow", regex=r"^(inflow|outflow|deposit|withdrawal)$")
    amount_dzd: int = Field(..., gt=0)
    # What the entry is (CMS → Trésorerie). Transfers move money between the
    # cash box and the bank and are recorded on both sides.
    category: Optional[str] = Field(None, max_length=40)
    description: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=255)
    source_reference: Optional[str] = None



# category → (label, [(account, movement), ...])
_TREASURY_ENTRY_KINDS = {
    "cash_in": ("Fond de caisse / alimentation", [("cash_box", "inflow")]),
    "capital_contribution": ("Apport du propriétaire", [(None, "inflow")]),
    "other_inflow": ("Autre entrée", [(None, "inflow")]),
    "cash_out": ("Retrait du propriétaire", [(None, "outflow")]),
    "minor_expense": ("Petite dépense boutique", [("cash_box", "outflow")]),
    "cash_adjustment": ("Régularisation d'écart de caisse", [("cash_box", "outflow")]),
    "other_outflow": ("Autre sortie", [(None, "outflow")]),
    "bank_deposit": ("Dépôt d'espèces à la banque", [("cash_box", "outflow"), ("bank_account", "inflow")]),
    "bank_withdrawal": ("Retrait à la banque vers la caisse", [("bank_account", "outflow"), ("cash_box", "inflow")]),
    "courier_remittance": ("Versement du livreur sur le compte", [("cash_box", "outflow"), ("bank_account", "inflow")]),
}



# --- SUPPLIER ENDPOINTS ---

@router.get("/api/v1/admin/suppliers")
def admin_list_suppliers(admin: dict = Depends(require_permission("finance:read"))):
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



@router.get("/api/v1/admin/suppliers/{supplier_id}")
def admin_get_supplier_detail(
    supplier_id: int,
    admin: dict = Depends(require_permission("finance:read")),
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


@router.post("/api/v1/admin/suppliers", status_code=201)
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


@router.put("/api/v1/admin/suppliers/{supplier_id}")
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


@router.delete("/api/v1/admin/suppliers/{supplier_id}")
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

@router.get("/api/v1/admin/purchases/{po_id}/document")
def admin_get_purchase_order_document(
    po_id: int,
    admin: dict = Depends(require_permission("finance:read")),
):
    """A4 purchase order document (bon de commande fournisseur): full supplier
    identity, boutique header, itemised table with quantities ordered vs
    received, and the money/payment summary."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT po.*, s.name AS supplier_name, s.company_name AS supplier_company,
                      s.contact_person AS supplier_contact, s.phone AS supplier_phone,
                      s.email AS supplier_email, s.address AS supplier_address, s.tax_id AS supplier_tax_id,
                      au.full_name AS created_by_name
               FROM purchase_orders po
               JOIN suppliers s ON s.id = po.supplier_id
               LEFT JOIN admin_users au ON au.id = po.created_by
               WHERE po.id = ?""",
            (po_id,),
        )
        po = cur.fetchone()
        if not po:
            raise HTTPException(status_code=404, detail="Bon de commande introuvable")
        d = dict(po)
        cur.execute(
            """SELECT poi.*,
                      pv.sku AS variant_sku, pv.title AS variant_title_live,
                      p.name_fr AS product_name_live
               FROM purchase_order_items poi
               LEFT JOIN product_variants pv ON pv.id = poi.variant_id
               LEFT JOIN products p ON p.id = poi.product_id
               WHERE poi.purchase_order_id = ? ORDER BY poi.id""",
            (po_id,),
        )
        d["items"] = [dict(r) for r in cur.fetchall()]
        d["total_items_ordered"] = sum(int(it["quantity_ordered"]) for it in d["items"])
        d["total_items_received"] = sum(int(it["quantity_received"]) for it in d["items"])
        d["outstanding_dzd"] = int(d["total_cost_dzd"]) - int(d["paid_amount_dzd"])
        d["boutique_info"] = _boutique_info_from_settings(conn)
        d["document_title"] = "Bon de commande fournisseur"
        return d



@router.get("/api/v1/admin/purchases")
def admin_list_purchases(admin: dict = Depends(require_permission("finance:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT po.*, s.name AS supplier_name, s.phone AS supplier_phone, s.company_name AS supplier_company
               FROM purchase_orders po
               JOIN suppliers s ON s.id = po.supplier_id
               ORDER BY po.id DESC"""
        )
        pos = [dict(r) for r in cur.fetchall()]
        items_by_po = _children_by_parent(cur, "purchase_order_items", "purchase_order_id", [d["id"] for d in pos])
        for d in pos:
            d["items"] = items_by_po.get(d["id"], [])
        return {"items": pos}


@router.post("/api/v1/admin/purchases", status_code=201)
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
            # Stock lives per variant (colour / size): every line must say
            # which one is received. Without it, receiving would credit an
            # arbitrary variant.
            variant_id = it.variant_id
            if variant_id:
                cur.execute("SELECT * FROM product_variants WHERE id = ? AND product_id = ?", (variant_id, it.product_id))
                v = cur.fetchone()
                if not v:
                    raise HTTPException(status_code=400, detail=f"La variante choisie n'appartient pas à « {p['name_fr']} ».")
            else:
                cur.execute("SELECT * FROM product_variants WHERE product_id = ? AND is_active = 1 ORDER BY id", (it.product_id,))
                variants = cur.fetchall()
                if len(variants) != 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Choisissez la variante (couleur / taille) de « {p['name_fr']} » à commander.",
                    )
                v = variants[0]
                variant_id = int(v["id"])
            variant_title = v["title"]
            sku = v["sku"]
            line_tot = it.quantity * it.unit_cost_dzd
            subtotal += line_tot
            enriched_items.append({
                "product_id": it.product_id,
                "variant_id": variant_id,
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


@router.get("/api/v1/admin/purchases/{po_id}/labels")
def admin_purchase_order_labels(
    po_id: int,
    admin: dict = Depends(require_permission("dashboard:read")),
):
    """Returns the exact label batch to print for a PO: one entry per variant,
    with `copies` set to the quantity received (or ordered if nothing received
    yet). The Desktop CMS pipes this straight into `pos_print_labels` after a
    PO is receipted so every unit that just arrived gets a sticky barcode.

    Variants without a barcode are returned with `barcode: null`; the UI must
    assign one (generate internal or scan the supplier's) before printing.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
        po = cur.fetchone()
        if not po:
            raise HTTPException(status_code=404, detail="Bon de commande introuvable")

        cur.execute(
            """SELECT poi.id, poi.product_id, poi.variant_id,
                      poi.quantity_ordered, poi.quantity_received,
                      pv.sku AS variant_sku, pv.title AS variant_title,
                      pv.barcode AS variant_barcode,
                      p.name_fr AS product_name,
                      p.selling_price_dzd
               FROM purchase_order_items poi
               LEFT JOIN product_variants pv ON pv.id = poi.variant_id
               LEFT JOIN products p ON p.id = poi.product_id
               WHERE poi.purchase_order_id = ? ORDER BY poi.id""",
            (po_id,),
        )
        rows = cur.fetchall()
        boutique = _boutique_info_from_settings(conn)

    store_name = (boutique.get("name") or "Mus Luxury").strip() or "Mus Luxury"
    labels = []
    for r in rows:
        d = dict(r)
        qty = int(d.get("quantity_received") or 0) or int(d.get("quantity_ordered") or 0)
        if qty <= 0:
            continue
        price = int(d.get("selling_price_dzd") or 0)
        labels.append({
            "variant_id": d.get("variant_id"),
            "product_id": d.get("product_id"),
            "header": store_name,
            "product_name": (d.get("product_name") or "").strip() or "Produit",
            "variant_title": (d.get("variant_title") or "").strip() or "",
            "sku": (d.get("variant_sku") or "").strip() or f"V{d.get('variant_id') or ''}",
            "price_text": f"{price:,} DA".replace(",", " "),
            "barcode_value": (d.get("variant_barcode") or ""),
            "barcode_kind": ("ean13" if (d.get("variant_barcode") or "").isdigit() and len(d.get("variant_barcode") or "") == 13 else "code128"),
            "copies": qty,
            "needs_barcode": not bool(d.get("variant_barcode")),
        })
    return {
        "po_id": po_id,
        "reference": dict(po).get("reference"),
        "labels": labels,
        "total_copies": sum(int(x["copies"]) for x in labels),
        "variants_without_barcode": sum(1 for x in labels if x["needs_barcode"]),
    }



@router.post("/api/v1/admin/purchases/{po_id}/receive")
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
        # The status change is the FIRST write, guarded by the old status: of
        # two requests sent together, the second changes no row and stops here
        # (stock, supplier balance and ledger are written once).
        cur.execute(
            "UPDATE purchase_orders SET status = 'received', received_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND status <> 'received'",
            (po_id,),
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=400, detail="Ce bon de commande a déjà été réceptionné en stock")

        cur.execute("SELECT * FROM purchase_order_items WHERE purchase_order_id = ?", (po_id,))
        items = [dict(it) for it in cur.fetchall()]

        today_str = _shop_today()
        # Landed cost: shipping and tax of the order are spread over the lines
        # in proportion to their value, so the product cost (and the margins)
        # include them — the same total that is booked to stock in the journal.
        extra_cost = int(po["shipping_dzd"] or 0) + int(po["tax_dzd"] or 0)
        goods_value = sum(int(it["quantity_ordered"]) * int(it["unit_cost_dzd"]) for it in items)
        total_units = sum(int(it["quantity_ordered"]) for it in items) or 1

        def landed_unit_cost(it) -> int:
            unit = int(it["unit_cost_dzd"])
            if extra_cost <= 0:
                return unit
            if goods_value > 0:
                return int(round(unit + extra_cost * unit / goods_value))
            return int(round(unit + extra_cost / total_units))

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
                # Added in place (not "read, then write the total"): a sale
                # made at the same moment is never undone by the receipt.
                cur.execute(
                    "UPDATE product_variants SET stock_qty = stock_qty + ? WHERE id = ?",
                    (it["quantity_ordered"], v_row["id"]),
                )
                cur.execute("SELECT stock_qty FROM product_variants WHERE id = ?", (v_row["id"],))
                new_stock = int(cur.fetchone()["stock_qty"])
                old_stock = new_stock - int(it["quantity_ordered"])
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
            # Weighted average cost (PMP) with the landed unit cost. Units already
            # in stock keep their cost; an oversold (negative) stock counts as 0.
            new_unit = landed_unit_cost(it)
            qty_in = int(it["quantity_ordered"])
            before_qty = max(total_stk - qty_in, 0)
            if before_qty + qty_in > 0:
                weighted_unit_cost = int(round((before_qty * curr_cost + qty_in * new_unit) / (before_qty + qty_in)))
            else:
                weighted_unit_cost = new_unit
            cur.execute("UPDATE products SET purchase_cost_dzd = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (weighted_unit_cost, it["product_id"]))
            # A variant with its own cost keeps its own weighted average (the
            # cost used for its margin is "variant cost, else product cost").
            if v_row:
                cur.execute("SELECT purchase_cost_dzd FROM product_variants WHERE id = ?", (v_row["id"],))
                v_cost = cur.fetchone()["purchase_cost_dzd"]
                if v_cost is not None:
                    v_before = max(int(old_stock), 0)
                    v_new = int(round((v_before * int(v_cost) + qty_in * new_unit) / (v_before + qty_in)))
                    cur.execute("UPDATE product_variants SET purchase_cost_dzd = ? WHERE id = ?", (v_new, v_row["id"]))
            cur.execute("UPDATE purchase_order_items SET quantity_received = quantity_ordered WHERE id = ?", (it["id"],))

        # Update purchase order status
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


@router.post("/api/v1/admin/purchases/{po_id}/pay")
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
            "UPDATE purchase_orders SET payment_status = 'paid', paid_amount_dzd = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND payment_status <> 'paid'",
            (po["total_cost_dzd"], po_id)
        )
        if cur.rowcount != 1:  # paid by a request sent at the same moment
            raise HTTPException(status_code=400, detail="Ce bon de commande est déjà payé")
        cur.execute(
            "UPDATE suppliers SET balance_dzd = balance_dzd - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (pay_amount, po["supplier_id"])
        )

        # Cash Movement (Outflow) — one mapping for treasury and ledger:
        # cash from the cash box, cheque / transfer from the bank.
        acc_type = _account_for_method(payment_method)
        cur.execute(
            """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
               VALUES (?, 'outflow', ?, 'purchase_payment', ?, ?, ?)""",
            (acc_type, pay_amount, po["reference"], f"Paiement fournisseur ({po['reference']})", int(admin["sub"]))
        )

        # Double-entry ledger: Debit 4010 (Fournisseurs) / Credit 5300 (Caisse) or 5120 (Banque)
        today_str = _shop_today()
        credit_acc, credit_name = _ledger_account(acc_type)
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



def _ledger_account(account_type: str) -> tuple:
    """Ledger account matching a treasury account (one mapping for both)."""
    return ("5120", "Banque") if account_type == "bank_account" else ("5300", "Caisse Boutique")


def _post_expense_payment(cur, expense_id: int, description: str, amount: int, payment_method: str,
                          entry_date: str, user_id: int) -> None:
    """Money leaves the cash box or the bank for an expense: treasury outflow
    plus the balanced ledger entries (debit 6100 / credit cash or bank)."""
    acc_type = _account_for_method(payment_method)
    _record_cash_movement(cur, account=acc_type, movement="outflow", amount=amount, source_type="expense_payment",
                          reference=f"EXP-{expense_id}", description=f"Dépense: {description}", user_id=user_id)
    credit_acc, credit_name = _ledger_account(acc_type)
    cur.execute(
        """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
           VALUES (?, 'OD', ?, '6100', 'Charges et Dépenses d''Exploitation', ?, ?, 0, ?)""",
        (f"EXP-{expense_id}-D", entry_date, description, amount, f"EXP-{expense_id}"),
    )
    cur.execute(
        """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
           VALUES (?, 'OD', ?, ?, ?, ?, 0, ?, ?)""",
        (f"EXP-{expense_id}-C", entry_date, credit_acc, credit_name, description, amount, f"EXP-{expense_id}"),
    )


# --- OPERATING EXPENSES (DÉPENSES & FRAIS GÉNÉRAUX) ---

@router.get("/api/v1/admin/expenses")
def admin_list_expenses(
    category: Optional[str] = None,
    admin: dict = Depends(require_permission("finance:read"))
):
    with db_session() as conn:
        cur = conn.cursor()
        if category:
            cur.execute("SELECT * FROM expenses WHERE category = ? ORDER BY expense_date DESC, id DESC", (category,))
        else:
            cur.execute("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC")
        return {"items": [dict(r) for r in cur.fetchall()]}


@router.post("/api/v1/admin/expenses", status_code=201)
def admin_create_expense(
    payload: ExpenseCreateInput,
    admin: dict = Depends(require_permission("settings:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        exp_date = payload.expense_date or _shop_today()
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
            _post_expense_payment(cur, exp_id, payload.description, int(payload.amount_dzd),
                                  payload.payment_method, exp_date, int(admin["sub"]))

        log_audit(conn, int(admin["sub"]), "create_expense", "expense", str(exp_id), {
            "description": payload.description,
            "amount_dzd": payload.amount_dzd,
            "category": payload.category
        })
        cur.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,))
        return dict(cur.fetchone())


@router.delete("/api/v1/admin/expenses/{expense_id}")
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
        # Delete the row only in the state just read: if it was paid (or
        # removed) in between, nothing is deleted and the request stops, so the
        # reversal below always matches what was really removed.
        cur.execute("DELETE FROM expenses WHERE id = ? AND payment_status = ?", (expense_id, exp["payment_status"]))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail="Cette dépense vient d'être modifiée. Rechargez la liste.")
        if exp["payment_status"] == "paid":
            # The money was taken out of the treasury when it was paid: put
            # it back with a visible correcting entry (history is kept), and
            # reverse the ledger entries the same way (originals stay).
            acc_type = _account_for_method(exp["payment_method"])
            _record_cash_movement(cur, account=acc_type, movement="inflow",
                                  amount=int(exp["amount_dzd"]), source_type="expense_cancelled",
                                  reference=f"EXP-{expense_id}", description=f"Annulation dépense: {exp['description']}",
                                  user_id=int(admin["sub"]))
            cash_acc, cash_name = _ledger_account(acc_type)
            label = f"Annulation dépense: {exp['description']}"
            amount = int(exp["amount_dzd"])
            today_str = _shop_today()
            cur.execute(
                """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
                   VALUES (?, 'OD', ?, ?, ?, ?, ?, 0, ?)""",
                (f"EXP-{expense_id}-RD", today_str, cash_acc, cash_name, label, amount, f"EXP-{expense_id}"),
            )
            cur.execute(
                """INSERT INTO accounting_ledger (entry_number, journal_code, entry_date, account_code, account_name, label, debit_dzd, credit_dzd, source_document)
                   VALUES (?, 'OD', ?, '6100', 'Charges et Dépenses d''Exploitation', ?, 0, ?, ?)""",
                (f"EXP-{expense_id}-RC", today_str, label, amount, f"EXP-{expense_id}"),
            )
        log_audit(conn, int(admin["sub"]), "delete_expense", "expense", str(expense_id), {"description": exp["description"]})
        return {"deleted": True, "expense_id": expense_id}



@router.post("/api/v1/admin/expenses/{expense_id}/pay")
def admin_pay_expense(
    expense_id: int,
    payment_method: str = Query("cash", regex=r"^(cash|bank_transfer|check|card)$"),
    admin: dict = Depends(require_permission("settings:write")),
):
    """An expense recorded as "à régler" is paid now: status → paid and the
    money leaves the cash box or the bank."""
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        exp = cur.fetchone()
        if not exp:
            raise HTTPException(status_code=404, detail="Dépense introuvable")
        if exp["payment_status"] == "paid":
            raise HTTPException(status_code=400, detail="Cette dépense est déjà payée.")
        cur.execute(
            "UPDATE expenses SET payment_status = 'paid', payment_method = ? WHERE id = ? AND payment_status <> 'paid'",
            (payment_method, expense_id),
        )
        if cur.rowcount != 1:  # paid by a request sent at the same moment
            raise HTTPException(status_code=400, detail="Cette dépense est déjà payée.")
        # Same treasury movement AND ledger entries as an expense recorded as paid.
        _post_expense_payment(cur, expense_id, exp["description"], int(exp["amount_dzd"]),
                              payment_method, _shop_today(), int(admin["sub"]))
        log_audit(conn, int(admin["sub"]), "pay_expense", "expense", str(expense_id), {"amount_dzd": int(exp["amount_dzd"])})
        cur.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        return dict(cur.fetchone())



# --- CASH REGISTER & TREASURY (CAISSE & TRÉSORERIE) ---

@router.get("/api/v1/admin/treasury/summary")
def admin_get_treasury_summary(admin: dict = Depends(require_permission("finance:read"))):
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
        cur.execute("SELECT COALESCE(SUM(total_dzd), 0) AS s FROM orders WHERE status IN ('confirmed', 'preparing', 'ready_for_shipment', 'shipped')")
        pending_cod = int(cur.fetchone()["s"])

        # Total Delivered Orders Cash Collected
        cur.execute("SELECT COALESCE(SUM(total_dzd), 0) AS s FROM orders WHERE status = 'delivered'")
        collected_orders_dzd = int(cur.fetchone()["s"])

        # Total Supplier Debts
        cur.execute("SELECT COALESCE(SUM(balance_dzd), 0) AS s FROM suppliers")
        supplier_debts = int(cur.fetchone()["s"])

        # Inventory Value at Purchase Cost
        cur.execute(
            f"""SELECT COALESCE(SUM(pv.stock_qty * {_UNIT_COST_SQL}), 0) AS s
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


@router.get("/api/v1/admin/treasury/movements")
def admin_list_cash_movements(
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(require_permission("finance:read"))
):
    with db_session() as conn:
        cur = conn.cursor()
        # Running balance per account (bank / cash) computed by the database
        # (window function, PostgreSQL and SQLite) and only the last `limit`
        # rows returned — not every movement since opening loaded into Python.
        cur.execute(
            """SELECT * FROM (
                   SELECT cm.*, au.full_name AS created_by,
                          SUM(CASE WHEN cm.movement_type IN ('outflow', 'withdrawal')
                                   THEN -cm.amount_dzd ELSE cm.amount_dzd END)
                            OVER (PARTITION BY CASE WHEN cm.account_type = 'bank_account' THEN 1 ELSE 0 END
                                  ORDER BY cm.id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance_after_dzd
                   FROM cash_movements cm LEFT JOIN admin_users au ON au.id = cm.recorded_by
               ) AS x ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        rows = []
        for r in cur.fetchall():
            m = dict(r)
            m["balance_after_dzd"] = int(m.get("balance_after_dzd") or 0)
            m["created_by"] = m.get("created_by") or ("Système" if not m.get("recorded_by") else None)
            rows.append(m)
        return {"items": rows}


@router.post("/api/v1/admin/treasury/movements", status_code=201)
def admin_record_cash_movement(
    payload: CashMovementCreateInput,
    admin: dict = Depends(require_permission("settings:write"))
):
    kind = _TREASURY_ENTRY_KINDS.get(payload.category or "")
    if payload.category and not kind:
        raise HTTPException(status_code=422, detail="Type de mouvement de trésorerie inconnu.")
    label = kind[0] if kind else "Mouvement manuel"
    text = " — ".join(x for x in [label, (payload.description or payload.notes or "").strip()] if x)
    legs = kind[1] if kind else [(payload.account_type, payload.movement_type)]
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        ids = []
        for account, movement in legs:
            cur.execute(
                """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
                   VALUES (?, ?, ?, 'manual_adjustment', ?, ?, ?)""",
                (account or payload.account_type, movement, payload.amount_dzd,
                 payload.source_reference, text[:255], int(admin["sub"])),
            )
            ids.append(cur.lastrowid)
        log_audit(conn, int(admin["sub"]), "treasury_manual_entry", "cash_movement", str(ids[0]),
                  {"category": payload.category, "amount_dzd": payload.amount_dzd, "legs": len(ids)})
        return {"created": True, "movement_id": ids[0], "movement_ids": ids}



# --- COMPTABILITÉ & CALCUL DES BÉNÉFICES (P&L, MARGINS & LEDGER) ---

@router.get("/api/v1/admin/accounting/pnl")
def admin_get_pnl_statement(admin: dict = Depends(require_permission("finance:read"))):
    """
    Compte de résultat since the shop opened, BOTH channels:
      revenue  = online merchandise + delivery fees + in-store sales − in-store refunds
      COGS     = units sold × purchase cost (variant cost, else product cost)
      gross    = revenue − COGS;  net = gross − operating expenses (paid or
                 not) − stock losses (write-offs, count gaps, at cost)
    Online sales = orders neither cancelled nor returned (a returned COD parcel
    was never paid). Same rules as the business dashboard and sales report.
    """
    with db_session() as conn:
        cur = conn.cursor()
        sold = "status NOT IN ('cancelled', 'returned')"
        cur.execute(
            f"""SELECT COUNT(*) AS count,
                      COALESCE(SUM(total_dzd - delivery_fee_dzd), 0) AS merch_dzd,  -- after coupons
                      COALESCE(SUM(delivery_fee_dzd), 0) AS delivery_fee_dzd,
                      COALESCE(SUM(total_dzd), 0) AS total_dzd
               FROM orders WHERE {sold}"""
        )
        online = dict(cur.fetchone())
        cur.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(total_dzd), 0) AS total_dzd
               FROM orders WHERE status = 'delivered'"""
        )
        delivered = dict(cur.fetchone())
        pos = {}
        for kind in ("sale", "refund"):
            cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd), 0) AS t FROM pos_sales WHERE sale_type = ?", (kind,))
            r = cur.fetchone()
            pos[kind] = (int(r["c"]), int(r["t"]))

        online_cogs = _scalar(cur, f"""SELECT COALESCE(SUM(oi.quantity * {_UNIT_COST_SQL}), 0) AS v
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
            JOIN product_variants pv ON pv.id = oi.variant_id JOIN products p ON p.id = pv.product_id
            WHERE o.{sold}""")
        delivered_cogs = _scalar(cur, f"""SELECT COALESCE(SUM(oi.quantity * {_UNIT_COST_SQL}), 0) AS v
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
            JOIN product_variants pv ON pv.id = oi.variant_id JOIN products p ON p.id = pv.product_id
            WHERE o.status = 'delivered'""")
        pos_cogs = {}
        for kind in ("sale", "refund"):
            pos_cogs[kind] = _scalar(cur, f"""SELECT COALESCE(SUM(psi.quantity * {_UNIT_COST_SQL}), 0) AS v
                FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                JOIN product_variants pv ON pv.id = psi.variant_id JOIN products p ON p.id = pv.product_id
                WHERE ps.sale_type = ?""", (kind,))
        units_online = _scalar(cur, f"""SELECT COALESCE(SUM(oi.quantity), 0) AS v FROM order_items oi
            JOIN orders o ON o.id = oi.order_id WHERE o.{sold}""")
        units_store = _scalar(cur, """SELECT COALESCE(SUM(CASE WHEN ps.sale_type = 'sale' THEN psi.quantity ELSE -psi.quantity END), 0) AS v
            FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id""")

        # Charges are counted when incurred, paid or still "à régler" — the same
        # rule as revenue (orders count before the COD cash arrives) and as the
        # Analytique screen and the expense report. The unpaid part is shown apart.
        total_expenses = _scalar(cur, "SELECT COALESCE(SUM(amount_dzd), 0) AS v FROM expenses")
        unpaid_expenses = _scalar(cur, "SELECT COALESCE(SUM(amount_dzd), 0) AS v FROM expenses WHERE payment_status = 'pending'")
        cur.execute("SELECT category, COALESCE(SUM(amount_dzd), 0) AS total_dzd, COUNT(*) AS count FROM expenses GROUP BY category")
        expenses_by_cat = [dict(r) for r in cur.fetchall()]

        inv_val = _scalar(cur, f"""SELECT COALESCE(SUM(pv.stock_qty * {_UNIT_COST_SQL}), 0) AS v
            FROM product_variants pv JOIN products p ON p.id = pv.product_id
            WHERE pv.is_active = 1 AND p.deleted_at IS NULL AND p.status != 'archived' AND pv.stock_qty > 0""")

        stock_losses = _stock_losses_dzd(cur)

        online_merch = int(online["merch_dzd"])
        delivery_fees = int(online["delivery_fee_dzd"])
        store_net = pos["sale"][1] - pos["refund"][1]
        merchandise = online_merch + store_net            # what the goods sold for
        total_revenue = merchandise + delivery_fees        # everything collected
        cogs = online_cogs + pos_cogs["sale"] - pos_cogs["refund"]
        # Delivery fees collected are revenue (courier invoices are entered as
        # expenses) — same figure as the business dashboard.
        gross_profit = total_revenue - cogs
        gross_pct = round(gross_profit / total_revenue * 100, 1) if total_revenue > 0 else 0.0
        net_profit = gross_profit - total_expenses - stock_losses
        net_pct = round(net_profit / total_revenue * 100, 1) if total_revenue > 0 else 0.0
        delivered_profit = int(delivered["total_dzd"]) - delivered_cogs

        return {
            "gross_revenue_dzd": merchandise,
            "delivery_revenue_dzd": delivery_fees,
            "total_revenue_dzd": total_revenue,
            "cogs_dzd": cogs,
            "gross_profit_dzd": gross_profit,
            "gross_margin_percent": gross_pct,
            "operating_expenses_dzd": total_expenses,
            "operating_expenses_unpaid_dzd": unpaid_expenses,
            "stock_losses_dzd": stock_losses,
            "net_operating_profit_dzd": net_profit,
            "net_margin_percent": net_pct,
            "orders_count": int(online["count"]),
            "in_store_sales_count": pos["sale"][0],
            "units_sold": units_online + units_store,
            "inventory_valuation_dzd": inv_val,
            "period": "since_opening",
            "revenue": {
                "online_merchandise_dzd": online_merch,
                "in_store_net_dzd": store_net,
                "in_store_refunds_dzd": pos["refund"][1],
                "subtotal_merchandise_dzd": merchandise,
                "delivery_fees_dzd": delivery_fees,
                "total_sales_dzd": total_revenue,
                "orders_count": int(online["count"]),
                "delivered_sales_dzd": int(delivered["total_dzd"]),
                "delivered_orders_count": int(delivered["count"]),
            },
            "cogs": {
                "cogs_all_orders_dzd": cogs,
                "cogs_online_dzd": online_cogs,
                "cogs_in_store_dzd": pos_cogs["sale"] - pos_cogs["refund"],
                "cogs_delivered_orders_dzd": delivered_cogs,
            },
            "margins": {
                "gross_profit_all_dzd": gross_profit,
                "gross_margin_pct_all": gross_pct,
                "gross_profit_delivered_dzd": delivered_profit,
            },
            "operating_expenses": {
                "total_expenses_dzd": total_expenses,
                "breakdown_by_category": expenses_by_cat,
            },
            "net_results": {
                "net_profit_all_dzd": net_profit,
                "net_margin_pct_all": net_pct,
            },
        }



@router.get("/api/v1/admin/accounting/products-profitability")
def admin_get_products_profitability(
    include_archived: bool = Query(True),
    admin: dict = Depends(require_permission("finance:read"))
):
    """
    Returns unit margins, markups, total sales and total profits generated by each product.
    """
    with db_session() as conn:
        cur = conn.cursor()
        where_clause = "" if include_archived else "WHERE p.deleted_at IS NULL"
        # Units and revenue from BOTH channels; online = orders neither
        # cancelled nor returned, in-store = sales minus refunds.
        cur.execute(
            f"""SELECT p.id, p.sku, p.name_fr, p.selling_price_dzd,
                      COALESCE(p.purchase_cost_dzd, 0) AS purchase_cost_dzd,
                      p.status,
                      COALESCE(s.units, 0) AS units_sold,
                      COALESCE(s.revenue, 0) AS total_revenue_dzd,
                      COALESCE(s.cost, 0) AS cost_sold
               FROM products p
               LEFT JOIN (
                   SELECT pv.product_id, SUM(x.q) AS units, SUM(x.r) AS revenue, SUM(x.q * {_UNIT_COST_SQL}) AS cost
                   FROM (
                       SELECT oi.variant_id, oi.quantity AS q, oi.line_total_dzd AS r
                       FROM order_items oi JOIN orders o ON o.id = oi.order_id
                       WHERE o.status NOT IN ('cancelled', 'returned')
                       UNION ALL
                       SELECT psi.variant_id,
                              CASE WHEN ps.sale_type = 'refund' THEN -psi.quantity ELSE psi.quantity END,
                              CASE WHEN ps.sale_type = 'refund' THEN -psi.line_total_dzd ELSE psi.line_total_dzd END
                       FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
                   ) AS x
                   JOIN product_variants pv ON pv.id = x.variant_id
                   JOIN products p ON p.id = pv.product_id
                   GROUP BY pv.product_id
               ) AS s ON s.product_id = p.id
               {where_clause}
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
            total_cost_sold = int(d.pop("cost_sold") or 0)
            total_profit = int(d["total_revenue_dzd"]) - total_cost_sold
            d["unit_profit_dzd"] = unit_profit
            d["gross_margin_pct"] = gross_margin_pct
            d["markup_pct"] = markup_pct
            d["total_cost_sold_dzd"] = total_cost_sold
            d["total_profit_dzd"] = total_profit
            items.append(d)
        return {"items": items}


@router.get("/api/v1/admin/accounting/ledger")
def admin_list_accounting_ledger(
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(require_permission("finance:read"))
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


@router.get("/api/v1/admin/accounting/export.csv")
def admin_export_accounting_csv(
    part: str = Query("pnl", regex=r"^(pnl|products|ledger)$"),
    admin: dict = Depends(require_permission("finance:read")),
):
    """Excel-ready CSV of the Comptabilité tab being viewed."""
    stamp = _shop_today()
    if part == "pnl":
        d = admin_get_pnl_statement(admin)
        rows = [
            ["Ventes en ligne (articles)", d["revenue"]["online_merchandise_dzd"]],
            ["Ventes magasin (net des remboursements)", d["revenue"]["in_store_net_dzd"]],
            ["Frais de livraison facturés", d["delivery_revenue_dzd"]],
            ["Chiffre d'affaires", d["total_revenue_dzd"]],
            ["Coût d'achat des articles vendus", -int(d["cogs_dzd"])],
            ["Marge brute", d["gross_profit_dzd"]],
            ["Marge brute (%)", d["gross_margin_percent"]],
            ["Charges d'exploitation", -int(d["operating_expenses_dzd"])],
            ["  dont charges encore à régler", -int(d.get("operating_expenses_unpaid_dzd") or 0)],
            ["Pertes et écarts de stock (au coût)", -int(d.get("stock_losses_dzd") or 0)],
            ["Bénéfice net d'exploitation", d["net_operating_profit_dzd"]],
            ["Bénéfice net (%)", d["net_margin_percent"]],
            ["Commandes en ligne comptées", d["orders_count"]],
            ["Ventes magasin comptées", d["in_store_sales_count"]],
            ["Valeur du stock au coût d'achat", d["inventory_valuation_dzd"]],
        ]
        return _excel_csv_response(f"compte_de_resultat_{stamp}.csv", ["Poste", "Montant (DA)"], rows)
    if part == "products":
        items = admin_get_products_profitability(True, admin)["items"]
        rows = [[it["name_fr"], it["sku"], it["purchase_cost_dzd"], it["selling_price_dzd"], it["unit_profit_dzd"],
                 it["gross_margin_pct"], it["units_sold"], it["total_revenue_dzd"], it["total_cost_sold_dzd"],
                 it["total_profit_dzd"]] for it in items]
        return _excel_csv_response(
            f"rentabilite_produits_{stamp}.csv",
            ["Produit", "Réf. (SKU)", "Coût d'achat (DA)", "Prix de vente (DA)", "Marge unitaire (DA)", "Marge (%)",
             "Unités vendues", "Chiffre d'affaires (DA)", "Coût des ventes (DA)", "Bénéfice (DA)"], rows)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM accounting_ledger ORDER BY entry_date, id")
        rows = [[str(r["entry_date"])[:10], r["entry_number"], r["journal_code"], r["account_code"], r["account_name"],
                 r["label"], int(r["debit_dzd"] or 0), int(r["credit_dzd"] or 0), r["source_document"] or ""]
                for r in cur.fetchall()]
    return _excel_csv_response(
        f"journal_achats_depenses_{stamp}.csv",
        ["Date", "N° écriture", "Journal", "Compte", "Intitulé du compte", "Libellé", "Débit (DA)", "Crédit (DA)", "Pièce"],
        rows)



def _shop_today() -> str:
    return _shop_now().strftime("%Y-%m-%d")
