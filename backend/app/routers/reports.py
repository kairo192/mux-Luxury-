"""Dashboards, sales/stock/expense reports and the audit log."""
from fastapi import APIRouter
import os
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query
from ..database import db_session
from ..deps import (
    require_permission,
)
from ..common import (
    SHOP_TZ,
    _UNIT_COST_SQL,
    _UTC_FMT,
    _children_by_parent,
    _csv_date,
    _excel_csv_response,
    _fr,
    _get_open_register,
    _register_runtime_totals,
    _scalar,
    _shop_now,
    _stock_losses_dzd,
)

router = APIRouter()



@router.get("/api/v1/admin/dashboard")
def admin_dashboard(admin: dict = Depends(require_permission("dashboard:read"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt, COALESCE(SUM(total_dzd), 0) AS rev FROM orders WHERE status NOT IN ('cancelled', 'returned')")
        ord_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status IN ('new', 'pending_confirmation')")
        pending_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE status = 'published' AND deleted_at IS NULL")
        pub_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM categories WHERE is_active = 1 AND deleted_at IS NULL")
        cat_cnt = cur.fetchone()["cnt"]
        # Stock figures count the variants (size / colour) of products that are
        # still in the catalogue — archived or deleted products are left out.
        live_variant = (
            "FROM product_variants v JOIN products p ON p.id = v.product_id "
            "WHERE v.is_active = 1 AND p.deleted_at IS NULL AND p.status != 'archived'"
        )
        cur.execute(f"SELECT COUNT(*) AS cnt {live_variant}")
        active_variant_cnt = cur.fetchone()["cnt"]
        cur.execute(f"SELECT COUNT(*) AS cnt {live_variant} AND v.stock_qty > 0 AND v.stock_qty <= COALESCE(v.low_stock_threshold, 3)")
        low_stock_only_cnt = cur.fetchone()["cnt"]
        cur.execute(f"SELECT COUNT(*) AS cnt {live_variant} AND v.stock_qty <= COALESCE(v.low_stock_threshold, 3)")
        low_stock_cnt = cur.fetchone()["cnt"]
        cur.execute(f"SELECT COUNT(*) AS cnt {live_variant} AND v.stock_qty <= 0")
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
        recent_orders = [dict(r) for r in cur.fetchall()]
        items_by_order = _children_by_parent(cur, "order_items", "order_id", [o["id"] for o in recent_orders])
        for od in recent_orders:
            od["items"] = items_by_order.get(od["id"], [])

        cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10")
        recent_activity = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM backup_records ORDER BY id DESC LIMIT 1")
        last_bkp_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS cnt FROM backup_records WHERE status = 'failed'")
        failed_bkp_cnt = cur.fetchone()["cnt"]

        # Real day-by-day revenue for the dashboard chart (last 30 days, same
        # orders as the revenue card: everything except cancelled/returned).
        # Shop days (Algeria), not UTC days: grouped by UTC hour, then mapped.
        shop_today = _shop_now().date()
        since_utc, _ = _utc_range_for_days((shop_today - timedelta(days=29)).isoformat(), shop_today.isoformat())
        cur.execute(
            """SELECT substr(created_at, 1, 13) AS hour, COUNT(*) AS cnt, COALESCE(SUM(total_dzd), 0) AS rev
               FROM orders
               WHERE status NOT IN ('cancelled', 'returned') AND created_at >= ?
               GROUP BY substr(created_at, 1, 13)""",
            (since_utc,),
        )
        by_day: Dict[str, tuple] = {}
        for r in cur.fetchall():
            d = _shop_day_of(r["hour"])
            rev0, cnt0 = by_day.get(d, (0, 0))
            by_day[d] = (rev0 + int(r["rev"]), cnt0 + int(r["cnt"]))
        revenue_by_day = []
        for i in range(30):
            day = (shop_today - timedelta(days=29 - i)).isoformat()
            rev, cnt = by_day.get(day, (0, 0))
            revenue_by_day.append({"date": day, "revenue_dzd": rev, "orders": cnt})

        # Money figures only for roles allowed to see finances (owner,
        # administrator); a cashier or read-only account gets the operations.
        can_see_money = "finance:read" in admin.get("perms", [])
        return {
            "finance_visible": can_see_money,
            "revenue_by_day": revenue_by_day if can_see_money else [],
            "total_orders": ord_row["cnt"],
            "total_revenue_dzd": ord_row["rev"] if can_see_money else None,
            "pending_orders": pending_cnt,
            "published_products": pub_cnt,
            "total_active_products": pub_cnt,
            "total_categories": cat_cnt,
            "active_variants": active_variant_cnt,
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
            "all_orders_count": sum(int(v or 0) for v in orders_by_status.values()),
            "database_engine": "postgres" if os.getenv("LUXE_DB_ENGINE", "").strip().lower() == "postgres" else "sqlite",
        }


@router.get("/api/v1/admin/reports")
def admin_analytics_reports(admin: dict = Depends(require_permission("finance:read"))):
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



# French names for the audit log (CMS → Journal d'audit). Codes stay in the
# database; the screen and its search use these names.
_AUDIT_ACTION_FR: Dict[str, str] = {
    "add_category_attribute": "Ajout d'une caractéristique de catégorie",
    "add_product_image": "Ajout d'une photo produit",
    "adjust_variant_stock": "Correction de stock",
    "admin_login": "Connexion au CMS",
    "apply_inventory_count": "Inventaire validé",
    "archive_category": "Catégorie archivée",
    "archive_product": "Produit archivé",
    "assign_barcode": "Code-barres attribué",
    "bulk_product_status": "Statut de plusieurs produits modifié",
    "bulk_update_delivery_zones": "Tarifs de livraison modifiés (lot)",
    "bulk_update_variants": "Déclinaisons modifiées (lot)",
    "cancel_inventory_count": "Inventaire annulé",
    "clear_barcode": "Code-barres retiré",
    "close_register": "Clôture de caisse",
    "create_admin_user": "Utilisateur créé",
    "create_attribute_option": "Valeur de caractéristique ajoutée",
    "create_banner": "Bannière créée",
    "create_brand": "Marque créée",
    "create_category": "Catégorie créée",
    "create_coupon": "Code promo créé",
    "create_customer": "Client créé",
    "create_device": "Appareil ajouté",
    "create_expense": "Dépense enregistrée",
    "create_product": "Produit créé",
    "create_purchase_order": "Bon de commande fournisseur créé",
    "create_supplier": "Fournisseur créé",
    "create_variant": "Déclinaison créée",
    "database_backup": "Sauvegarde de la base",
    "download_backup": "Copie de sauvegarde enregistrée sur le PC",
    "import_backup": "Sauvegarde renvoyée depuis le PC",
    "deactivate_coupon": "Code promo désactivé",
    "deactivate_variant": "Déclinaison désactivée",
    "delete_attribute_option": "Valeur de caractéristique supprimée",
    "delete_banner": "Bannière supprimée",
    "delete_category_attribute": "Caractéristique de catégorie supprimée",
    "delete_category_permanent": "Catégorie supprimée définitivement",
    "delete_device": "Appareil supprimé",
    "delete_expense": "Dépense supprimée",
    "delete_product": "Produit supprimé",
    "delete_product_image": "Photo produit supprimée",
    "delete_variant": "Déclinaison supprimée",
    "first_time_owner_initialized": "Compte propriétaire créé (1re configuration)",
    "generate_variants": "Déclinaisons générées",
    "open_inventory_count": "Inventaire ouvert",
    "open_register": "Ouverture de caisse",
    "pay_expense": "Dépense payée",
    "pos_refund": "Remboursement magasin",
    "pos_sale": "Vente magasin",
    "pos_sale_offline_sync": "Vente hors ligne synchronisée",
    "receive_purchase_order": "Réception fournisseur",
    "remove_cod_blacklist": "Numéro retiré de la liste noire",
    "remove_legacy_demo_content": "Suppression des exemples (ancienne version)",
    "reorder_categories": "Ordre des catégories modifié",
    "reorder_product_images": "Ordre des photos modifié",
    "reset_admin_password": "Mot de passe réinitialisé",
    "reset_admin_password_server": "Mot de passe réinitialisé (commande serveur)",
    "restore_category": "Catégorie restaurée",
    "set_default_device": "Appareil par défaut choisi",
    "stock_write_off": "Mise au rebut (stock)",
    "test_device": "Test d'appareil",
    "treasury_backfill": "Trésorerie reconstituée depuis les ventes",
    "treasury_manual_entry": "Mouvement de trésorerie manuel",
    "update_admin_user": "Utilisateur modifié",
    "update_attribute_option": "Valeur de caractéristique modifiée",
    "update_banner": "Bannière modifiée",
    "update_category": "Catégorie modifiée",
    "update_category_attribute": "Caractéristique de catégorie modifiée",
    "update_customer": "Client modifié",
    "update_delivery_zone": "Tarif de livraison modifié",
    "update_device": "Appareil modifié",
    "update_fiscal_settings": "Paramètres fiscaux modifiés",
    "update_homepage_section": "Section de la page d'accueil modifiée",
    "update_order_status": "Statut de commande modifié",
    "update_product_synced": "Produit modifié",
    "update_store_settings": "Paramètres de la boutique modifiés",
    "update_variant": "Déclinaison modifiée",
    "notify_customer_whatsapp": "Message WhatsApp préparé pour le client",
    "whatsapp_webhook_status": "Statut d'un message WhatsApp reçu",
    "upsert_cod_blacklist": "Numéro ajouté à la liste noire",
    "upsert_static_page": "Page d'information modifiée",
}

_AUDIT_ENTITY_FR: Dict[str, str] = {
    "admin_user": "Utilisateur", "banner": "Bannière", "brand": "Marque", "cash_movement": "Trésorerie",
    "cash_register_session": "Session de caisse", "category": "Catégorie", "category_attribute": "Caractéristique",
    "category_attribute_option": "Valeur de caractéristique", "coupon": "Code promo", "customer": "Client",
    "customer_phone_blacklist": "Liste noire", "database": "Base de données", "delivery_zone": "Livraison",
    "device": "Appareil", "expense": "Dépense", "homepage_section": "Page d'accueil", "inventory_count": "Inventaire",
    "order": "Commande", "pos_sale": "Vente magasin", "product": "Produit", "product_image": "Photo produit",
    "product_variant": "Déclinaison", "purchase_order": "Achat fournisseur", "static_page": "Page d'information",
    "store_settings": "Paramètres", "supplier": "Fournisseur", "system": "Système", "whatsapp_message": "Message WhatsApp", "treasury": "Trésorerie",
}



def _audit_label(table: Dict[str, str], code: Optional[str]) -> str:
    c = str(code or "")
    return table.get(c) or c.replace("_", " ")



@router.get("/api/v1/admin/audit-logs")
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
        needle = q.strip()
        like = f"%{needle}%"
        clauses = ["al.action LIKE ?", "al.entity_id LIKE ?", "al.details_json LIKE ?", "au.email LIKE ?", "au.full_name LIKE ?"]
        params.extend([like] * len(clauses))
        # Searching in French ("connexion", "caisse"…) finds the matching codes.
        folded = needle.lower()
        codes = [c for c, lbl in _AUDIT_ACTION_FR.items() if folded in lbl.lower()]
        if codes:
            clauses.append("al.action IN (" + ",".join("?" for _ in codes) + ")")
            params.extend(codes)
        ents = [c for c, lbl in _AUDIT_ENTITY_FR.items() if folded in lbl.lower()]
        if ents:
            clauses.append("al.entity_type IN (" + ",".join("?" for _ in ents) + ")")
            params.extend(ents)
        where.append("(" + " OR ".join(clauses) + ")")
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
            d["action_label"] = _audit_label(_AUDIT_ACTION_FR, d.get("action"))
            d["entity_label"] = _audit_label(_AUDIT_ENTITY_FR, d.get("entity_type"))
            items.append(d)
        return {"items": items, "count": len(items)}



@router.get("/api/v1/admin/audit-logs/facets")
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
            "actions": sorted(({"code": k, "label": _audit_label(_AUDIT_ACTION_FR, k), "count": v}
                               for k, v in actions_set.items()), key=lambda a: a["label"].lower()),
            "entity_types": sorted(({"code": k, "label": _audit_label(_AUDIT_ENTITY_FR, k), "count": v}
                                    for k, v in entities_set.items()), key=lambda a: a["label"].lower()),
        }



@router.get("/api/v1/admin/dashboard/business")
def admin_business_dashboard(admin: dict = Depends(require_permission("finance:read"))):
    now = datetime.now(timezone.utc)
    shop_now = _shop_now().replace(tzinfo=None)
    # "Today" / "this month" are the shop's (Algeria), converted to stored UTC.
    today_start = _shop_local_to_utc(shop_now.replace(hour=0, minute=0, second=0, microsecond=0))
    month_start = _shop_local_to_utc(shop_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    month_start_date = shop_now.strftime("%Y-%m-01")

    with db_session() as conn:
        cur = conn.cursor()

        def online(period_clause: str, params=()):
            cur.execute(
                f"SELECT COUNT(*) AS c, COALESCE(SUM(total_dzd),0) AS r FROM orders WHERE status NOT IN ('cancelled', 'returned') {period_clause}",
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
                WHERE o.status NOT IN ('cancelled', 'returned') AND o.created_at >= ?""", (month_start,))
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
        losses_month = _stock_losses_dzd(cur, month_start)
        margin_pct = round((gross_margin / revenue_month) * 100, 1) if revenue_month > 0 else 0.0

        margin_month = {
            "revenue_dzd": revenue_month,
            "cogs_dzd": cogs_month,
            "gross_margin_dzd": gross_margin,
            "gross_margin_percent": margin_pct,
            "operating_expenses_dzd": opex_month,
            "stock_losses_dzd": losses_month,
            "net_profit_dzd": gross_margin - opex_month - losses_month,
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
            """SELECT variant_id, MAX(product_name) AS product_name, MAX(sku) AS sku, SUM(q) AS qty FROM (
                 SELECT variant_id, product_name, sku, quantity AS q
                 FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status NOT IN ('cancelled', 'returned')
                 UNION ALL
                 SELECT variant_id, product_name, sku, quantity AS q
                 FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id WHERE ps.sale_type = 'sale'
               ) AS sold GROUP BY variant_id ORDER BY qty DESC LIMIT 8"""
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



# ============================================================================
# SALES REPORTS — date-ranged reporting for the owner/accountant.
# All figures are derived from real records (orders + pos_sales/items).
# Revenue is net of in-store refunds. Online cancelled orders are excluded.
# ============================================================================

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")



def _shop_local_to_utc(local_naive: datetime) -> str:
    """Shop wall-clock time -> stored UTC text."""
    return local_naive.replace(tzinfo=SHOP_TZ).astimezone(timezone.utc).strftime(_UTC_FMT)



def _utc_range_for_days(date_from: str, date_to: str) -> tuple:
    """Shop days [date_from .. date_to] -> UTC [start, end) for `created_at >= ? AND created_at < ?`."""
    d0 = datetime.strptime(date_from, "%Y-%m-%d")
    d1 = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    return _shop_local_to_utc(d0), _shop_local_to_utc(d1)



def _shop_day_of(utc_text: Any) -> str:
    """Stored UTC timestamp (or an 'YYYY-MM-DD HH' hour bucket) -> shop day."""
    s = str(utc_text or "").replace("T", " ")
    if len(s) < 10:
        return s
    try:
        if len(s) == 13:  # hour bucket from substr(created_at, 1, 13)
            dt = datetime.strptime(s, "%Y-%m-%d %H")
        else:
            dt = datetime.strptime(s[:19], _UTC_FMT) if len(s) >= 19 else datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return s[:10]
    return dt.replace(tzinfo=timezone.utc).astimezone(SHOP_TZ).strftime("%Y-%m-%d")



def _parse_date_or_422(s: str, field: str) -> str:
    if not s or not _DATE_RE.match(s):
        raise HTTPException(status_code=422, detail=f"{field}: date attendue au format YYYY-MM-DD")
    return s



def _sales_report_data(conn, date_from: str, date_to: str) -> dict:
    cur = conn.cursor()
    start, end = _utc_range_for_days(date_from, date_to)  # shop days -> UTC [start, end)

    # Per-day online revenue & count
    cur.execute(
        """SELECT substr(created_at, 1, 13) AS hour,
                  COUNT(*) AS c, COALESCE(SUM(total_dzd), 0) AS r
           FROM orders
           WHERE status NOT IN ('cancelled', 'returned') AND created_at >= ? AND created_at < ?
           GROUP BY substr(created_at, 1, 13)""",
        (start, end),
    )
    # Grouped by UTC hour, folded into SHOP days (a 00:30 order in Algiers
    # belongs to that day, not to the previous UTC day).
    online_by_day: Dict[str, Dict[str, int]] = {}
    for r in cur.fetchall():
        d = online_by_day.setdefault(_shop_day_of(r["hour"]), {"count": 0, "revenue_dzd": 0})
        d["count"] += int(r["c"])
        d["revenue_dzd"] += int(r["r"])

    # Per-day in-store (sales minus refunds)
    cur.execute(
        """SELECT substr(created_at, 1, 13) AS hour, sale_type,
                  COUNT(*) AS c, COALESCE(SUM(total_dzd), 0) AS r
           FROM pos_sales
           WHERE created_at >= ? AND created_at < ?
           GROUP BY substr(created_at, 1, 13), sale_type""",
        (start, end),
    )
    instore_by_day: Dict[str, Dict[str, int]] = {}
    for r in cur.fetchall():
        d = instore_by_day.setdefault(_shop_day_of(r["hour"]), {"sales_count": 0, "sales_revenue_dzd": 0, "refunds_dzd": 0, "refunds_count": 0})
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
        """SELECT variant_id, MAX(product_name) AS product_name, MAX(sku) AS sku, SUM(q) AS qty, SUM(r) AS rev FROM (
             SELECT oi.variant_id, oi.product_name, oi.sku, oi.quantity AS q, oi.line_total_dzd AS r
             FROM order_items oi JOIN orders o ON o.id = oi.order_id
             WHERE o.status NOT IN ('cancelled', 'returned') AND o.created_at >= ? AND o.created_at < ?
             UNION ALL
             SELECT psi.variant_id, psi.product_name, psi.sku, psi.quantity AS q, psi.line_total_dzd AS r
             FROM pos_sale_items psi JOIN pos_sales ps ON ps.id = psi.sale_id
             WHERE ps.sale_type = 'sale' AND ps.created_at >= ? AND ps.created_at < ?
           ) AS sold GROUP BY variant_id ORDER BY qty DESC LIMIT 20""",
        (start, end, start, end),
    )
    top_products = [{"variant_id": r["variant_id"], "product_name": r["product_name"], "sku": r["sku"],
                     "qty_sold": int(r["qty"]), "revenue_dzd": int(r["rev"])} for r in cur.fetchall()]

    # Payment-method breakdown (in-store only — online is always COD)
    cur.execute(
        """SELECT pp.method, COUNT(*) AS c, COALESCE(SUM(CASE WHEN ps.sale_type = 'sale' THEN pp.amount_dzd ELSE -pp.amount_dzd END), 0) AS total
           FROM pos_payments pp JOIN pos_sales ps ON ps.id = pp.sale_id
           WHERE ps.created_at >= ? AND ps.created_at < ?
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
# TREASURY REPORT — date-ranged cash flow by account & source, plus CSV export.
# ============================================================================


def _treasury_report_data(conn, date_from: str, date_to: str) -> dict:
    cur = conn.cursor()
    start, end = _utc_range_for_days(date_from, date_to)  # shop days -> UTC [start, end)

    # Per-source inflow/outflow by account
    cur.execute(
        """SELECT account_type, movement_type, source_type,
                  COUNT(*) AS c,
                  COALESCE(SUM(amount_dzd), 0) AS total
           FROM cash_movements
           WHERE created_at >= ? AND created_at < ?
           GROUP BY account_type, movement_type, source_type
           ORDER BY total DESC""",
        (start, end),
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Per-account summary + net
    accounts: Dict[str, Dict[str, int]] = {}
    for r in rows:
        a = accounts.setdefault(r["account_type"], {"inflow": 0, "outflow": 0})
        if r["movement_type"] in ("inflow", "deposit"):
            a["inflow"] += int(r["total"])
        elif r["movement_type"] in ("outflow", "withdrawal"):
            a["outflow"] += int(r["total"])

    # Per-day net (for a mini-trend)
    cur.execute(
        """SELECT substr(created_at, 1, 13) AS hour,
                  COALESCE(SUM(CASE WHEN movement_type IN ('inflow','deposit') THEN amount_dzd ELSE -amount_dzd END), 0) AS net
           FROM cash_movements
           WHERE created_at >= ? AND created_at < ?
           GROUP BY substr(created_at, 1, 13)""",
        (start, end),
    )
    net_by_day: Dict[str, int] = {}
    for r in cur.fetchall():
        day = _shop_day_of(r["hour"])
        net_by_day[day] = net_by_day.get(day, 0) + int(r["net"])
    by_day = [{"day": d, "net_dzd": v} for d, v in sorted(net_by_day.items())]

    # List of movements for the detail table and CSV
    cur.execute(
        """SELECT cm.*, au.full_name AS admin_name
           FROM cash_movements cm
           LEFT JOIN admin_users au ON au.id = cm.recorded_by
           WHERE cm.created_at >= ? AND cm.created_at < ?
           ORDER BY cm.id DESC LIMIT 2000""",
        (start, end),
    )
    items = [dict(r) for r in cur.fetchall()]

    total_in = sum(a["inflow"] for a in accounts.values())
    total_out = sum(a["outflow"] for a in accounts.values())
    return {
        "period": {"from": date_from, "to": date_to},
        "totals": {
            "count": len(items),
            "inflow_dzd": total_in,
            "outflow_dzd": total_out,
            "net_dzd": total_in - total_out,
        },
        "by_account": [
            {"account_type": acc, "inflow_dzd": v["inflow"], "outflow_dzd": v["outflow"], "net_dzd": v["inflow"] - v["outflow"]}
            for acc, v in accounts.items()
        ],
        "by_source": rows,
        "by_day": by_day,
        "items": items,
    }



@router.get("/api/v1/admin/reports/treasury")
def admin_treasury_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _treasury_report_data(conn, date_from, date_to)



@router.get("/api/v1/admin/reports/treasury.csv")
def admin_treasury_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _treasury_report_data(conn, date_from, date_to)

    t = data["totals"]
    rows = [[_csv_date(it["created_at"]), _fr(it["account_type"]), _fr(it["movement_type"]), _fr(it["source_type"]),
             it.get("source_reference") or "", it["description"], it["amount_dzd"], it.get("admin_name") or ""]
            for it in data["items"]]
    rows += [[], ["TOTAL entrées", "", "", "", "", "", t["inflow_dzd"], ""],
             ["TOTAL sorties", "", "", "", "", "", t["outflow_dzd"], ""], ["Flux net", "", "", "", "", "", t["net_dzd"], ""]]
    return _excel_csv_response(f"tresorerie_{date_from}_{date_to}.csv",
                               ["Date", "Compte", "Sens", "Origine", "Référence", "Libellé", "Montant (DA)", "Saisi par"], rows)



# ============================================================================
# INVENTORY MOVEMENTS REPORT — date-ranged movements list with CSV export.
# Returns the raw ledger entries plus a per-reason summary so the owner can
# spot anomalies (unusual damaged / refund / write-off spikes).
# ============================================================================


def _inventory_movements_data(conn, date_from: str, date_to: str, variant_id: Optional[int] = None) -> dict:
    cur = conn.cursor()
    start, end = _utc_range_for_days(date_from, date_to)  # shop days -> UTC [start, end)
    params: List[Any] = [start, end]
    where = ["im.created_at >= ? AND im.created_at < ?"]
    if variant_id is not None:
        where.append("im.variant_id = ?")
        params.append(variant_id)
    where_sql = " AND ".join(where)

    cur.execute(
        f"""SELECT im.*, pv.sku, pv.title AS variant_title, p.name_fr AS product_name,
                   au.full_name AS admin_name
            FROM inventory_movements im
            JOIN product_variants pv ON pv.id = im.variant_id
            JOIN products p ON p.id = pv.product_id
            LEFT JOIN admin_users au ON au.id = im.admin_user_id
            WHERE {where_sql}
            ORDER BY im.id DESC
            LIMIT 2000""",
        tuple(params),
    )
    items = [dict(r) for r in cur.fetchall()]

    # Per-reason summary (net change + absolute units moved)
    cur.execute(
        f"""SELECT reason,
                   COUNT(*) AS c,
                   COALESCE(SUM(change_qty), 0) AS net,
                   COALESCE(SUM(ABS(change_qty)), 0) AS gross
            FROM inventory_movements im
            WHERE {where_sql}
            GROUP BY reason
            ORDER BY gross DESC""",
        tuple(params),
    )
    by_reason = [{"reason": r["reason"], "count": int(r["c"]),
                  "net_change": int(r["net"]), "gross_units": int(r["gross"])} for r in cur.fetchall()]

    total_units_in = sum(it["change_qty"] for it in items if it["change_qty"] > 0)
    total_units_out = sum(-it["change_qty"] for it in items if it["change_qty"] < 0)
    return {
        "period": {"from": date_from, "to": date_to},
        "variant_id": variant_id,
        "totals": {
            "count": len(items),
            "units_in": total_units_in,
            "units_out": total_units_out,
            "net_change": total_units_in - total_units_out,
        },
        "by_reason": by_reason,
        "items": items,
    }



@router.get("/api/v1/admin/reports/inventory-movements")
def admin_inventory_movements_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    variant_id: Optional[int] = Query(None),
    admin: dict = Depends(require_permission("inventory:write")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _inventory_movements_data(conn, date_from, date_to, variant_id)



@router.get("/api/v1/admin/reports/inventory-movements.csv")
def admin_inventory_movements_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    variant_id: Optional[int] = Query(None),
    admin: dict = Depends(require_permission("inventory:write")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _inventory_movements_data(conn, date_from, date_to, variant_id)

    t = data["totals"]
    rows = [[_csv_date(it["created_at"]), it["sku"], it["product_name"], it["variant_title"],
             it["change_qty"], it["previous_qty"], it["new_qty"], _fr(it["reason"]), it.get("admin_name") or ""]
            for it in data["items"]]
    rows += [[], ["TOTAL", "", "", "", t["net_change"], "", "", f"{t['count']} mouvement(s)", ""]]
    return _excel_csv_response(f"mouvements_stock_{date_from}_{date_to}.csv",
                               ["Date", "SKU", "Produit", "Variante", "Variation", "Avant", "Après", "Motif", "Par"], rows)



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



@router.get("/api/v1/admin/reports/expenses")
def admin_expense_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _expenses_report_data(conn, date_from, date_to)



@router.get("/api/v1/admin/reports/expenses.csv")
def admin_expense_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _expenses_report_data(conn, date_from, date_to)

    rows = [[it["expense_date"], _fr(it["category"]), it["description"], it.get("recipient") or "",
             _fr(it["payment_method"]), _fr(it["payment_status"]), it["amount_dzd"], it.get("receipt_reference") or ""]
            for it in data["items"]]
    rows += [[], ["TOTAL", "", "", "", "", "", data["totals"]["total_dzd"], ""]]
    return _excel_csv_response(f"depenses_{date_from}_{date_to}.csv",
                               ["Date", "Catégorie", "Description", "Bénéficiaire", "Paiement", "Statut", "Montant (DA)", "N° de reçu"], rows)



@router.get("/api/v1/admin/reports/sales")
def admin_sales_report(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        return _sales_report_data(conn, date_from, date_to)



@router.get("/api/v1/admin/reports/sales.csv")
def admin_sales_report_csv(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    admin: dict = Depends(require_permission("finance:read")),
):
    date_from = _parse_date_or_422(date_from, "from")
    date_to = _parse_date_or_422(date_to, "to")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from doit être <= to")
    with db_session() as conn:
        data = _sales_report_data(conn, date_from, date_to)

    t = data["totals"]
    rows = [[d["day"], d["online_count"], d["online_revenue_dzd"], d["in_store_count"], d["in_store_revenue_dzd"],
             d["in_store_refunds_count"], d["in_store_refunds_dzd"], d["net_revenue_dzd"]] for d in data["by_day"]]
    rows += [[], ["TOTAL", t["online_count"], t["online_revenue_dzd"], t["in_store_count"], t["in_store_revenue_dzd"],
                  t["in_store_refunds_count"], t["in_store_refunds_dzd"], t["net_revenue_dzd"]]]
    return _excel_csv_response(f"ventes_{date_from}_{date_to}.csv",
                               ["Jour", "Commandes en ligne", "CA en ligne (DA)", "Ventes magasin", "CA magasin (DA)",
                                "Remboursements", "Remboursé (DA)", "CA net (DA)"], rows)
