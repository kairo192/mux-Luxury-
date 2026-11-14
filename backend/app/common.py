"""Helpers, constants and serializers shared by several routers."""
import csv
import io
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from fastapi import Response



# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _id_chunks(ids: List[int], size: int = 500):
    """Splits an id list for `IN (...)` queries (keeps every query well under the
    bound-parameter limits of SQLite and PostgreSQL)."""
    for i in range(0, len(ids), size):
        yield ids[i:i + size]



def _children_by_parent(cur, table: str, parent_col: str, parent_ids: List[int], columns: str = "*",
                        order_by: str = "id ASC") -> Dict[int, List[dict]]:
    """Loads the child rows of many parents in one query per 500 parents (instead
    of one query per parent: no N+1), grouped by parent id."""
    out: Dict[int, List[dict]] = {pid: [] for pid in parent_ids}
    for chunk in _id_chunks(list(dict.fromkeys(parent_ids))):
        marks = ",".join("?" for _ in chunk)
        cur.execute(
            f"SELECT {columns} FROM {table} WHERE {parent_col} IN ({marks}) ORDER BY {parent_col}, {order_by}",
            chunk,
        )
        for r in cur.fetchall():
            d = dict(r)
            out.setdefault(d[parent_col], []).append(d)
    return out



def serialize_categories_batch(conn, rows) -> List[dict]:
    """Categories with their attributes and options: 2 queries for the whole list
    (attributes of all categories, then options of all those attributes)."""
    cats = [dict(r) for r in rows]
    if not cats:
        return []
    cur = conn.cursor()
    attrs_by_cat = _children_by_parent(cur, "category_attributes", "category_id", [c["id"] for c in cats],
                                       order_by="display_order ASC, id ASC")
    attr_ids = [a["id"] for attrs in attrs_by_cat.values() for a in attrs]
    opts_by_attr = _children_by_parent(
        cur, "category_attribute_options", "attribute_id", attr_ids,
        columns="id, attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order",
        order_by="display_order ASC, id ASC",
    ) if attr_ids else {}
    for cat in cats:
        attrs = []
        for ad in attrs_by_cat.get(cat["id"], []):
            ad["options"] = [{k: v for k, v in o.items() if k != "attribute_id"} for o in opts_by_attr.get(ad["id"], [])]
            for flag in ("is_required", "allow_multiple", "is_visible_on_storefront", "is_filterable", "is_variant_axis"):
                ad[flag] = bool(ad[flag])
            attrs.append(ad)
        cat["is_active"] = bool(cat["is_active"])
        cat["show_on_homepage"] = bool(cat["show_on_homepage"])
        cat["attributes"] = attrs
    return cats



def serialize_category(conn, row: dict) -> dict:
    return serialize_categories_batch(conn, [row])[0]


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


# ============================================================================
# PUBLIC STOREFRONT ENDPOINTS (/api/v1/*)
# ============================================================================

_INTERNAL_SETTING_KEYS = {"system_initialized"}


def _is_protected_setting_key(key: str) -> bool:
    k = (key or "").strip().lower()
    return k in _INTERNAL_SETTING_KEYS or k.startswith("system_") or k.startswith("internal_") or k.startswith("session_revoked_ns:")


# ============================================================================
# ADMINISTRATIVE ENDPOINTS (/api/v1/admin/*)
# ============================================================================

def _int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(os.getenv(name, default))))
    except ValueError:
        return default


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


# ---------------------------------------------------------------- CSV ----
# Every CSV export opens directly in Excel (French Windows): UTF-8 with BOM
# so accents display, ";" as separator, French headers and values, short
# dates. Cells that would be read as formulas are neutralised.
_FR_CODES = {
    # orders
    "new": "Nouvelle", "pending_confirmation": "À confirmer", "confirmed": "Confirmée", "preparing": "En préparation",
    "ready_for_shipment": "Prête à expédier", "shipped": "Expédiée", "delivered": "Livrée", "cancelled": "Annulée",
    "returned": "Retournée", "home": "À domicile", "stop_desk": "Point relais", "cod": "Paiement à la livraison",
    # payments / accounts / treasury
    "cash": "Espèces", "card": "Carte", "transfer": "Virement", "bank_transfer": "Virement", "check": "Chèque",
    "other": "Autre", "paid": "Payée", "pending": "À régler", "unpaid": "À régler", "partial": "Partiellement payée",
    "cash_box": "Caisse", "bank_account": "Banque / CCP", "inflow": "Entrée", "outflow": "Sortie",
    "deposit": "Dépôt", "withdrawal": "Retrait",
    "pos_sale": "Vente magasin", "pos_refund": "Remboursement magasin", "cod_collection": "Commande livrée (COD)",
    "cod_refund": "Retour après livraison", "expense_payment": "Paiement dépense",
    "purchase_payment": "Paiement fournisseur", "manual_adjustment": "Mouvement manuel", "register_variance": "Écart de caisse",
    "expense_cancelled": "Annulation dépense",
    # stock movements
    "order_reserved": "Commande en ligne", "order_cancelled": "Commande annulée", "order_returned": "Commande retournée",
    "pos_sale_offline": "Vente hors ligne synchronisée", "physical_count_reconcile": "Inventaire physique",
    "cms_manual_adjustment": "Ajustement manuel", "stock_write_off": "Sortie de stock",
    "variant_created": "Création de la variante", "create_variant": "Création de la variante",
    "variant_edit": "Modification de la variante", "purchase_received": "Réception fournisseur",
    "writeoff_damaged": "Démarque — endommagé", "writeoff_lost": "Démarque — perte/vol",
    "writeoff_return_to_supplier": "Retour fournisseur", "writeoff_promotional_giveaway": "Cadeau / promo",
    "writeoff_stocktake_correction": "Correction d'inventaire",
    # expense categories
    "loyer": "Loyer & local", "rent": "Loyer & local", "salaires": "Salaires", "electricite_eau": "Électricité, gaz & eau",
    "internet_tel": "Internet & télécoms", "packaging": "Emballages", "publicite_marketing": "Publicité",
    "transport_logistique": "Transport & coursiers", "maintenance": "Maintenance", "abonnements_logiciels": "Logiciels",
    "autre": "Autres charges",
}



def _fr(code: Any) -> str:
    c = "" if code is None else str(code)
    return _FR_CODES.get(c, c.replace("_", " "))



def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    stripped = text.lstrip()
    # Formula injection: =, -, @, tab/CR, or a "+" that is not an Algerian phone.
    if stripped.startswith(("=", "-", "@", "\t", "\r")) or (stripped.startswith("+") and not re.match(r"^\+213\d+$", stripped)):
        return "'" + text
    return text



def _csv_date(value: Any) -> str:
    """Stored UTC timestamp -> shop local 'YYYY-MM-DD HH:MM'; plain dates unchanged."""
    text = str(value or "").replace("T", " ")
    return _shop_time_text(text) if len(text) >= 19 else text[:16]



def _excel_csv_response(filename: str, header: List[str], rows: Iterable[Iterable[Any]]) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



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
    # Shop contacts edited in CMS → Contenu (the same ones the website shows).
    shop: Dict[str, str] = {}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT setting_key, setting_value FROM store_settings WHERE setting_key IN "
            "('store_name', 'store_phone', 'store_location', 'whatsapp_contact_number', 'instagram_url', 'tiktok_url')"
        )
        shop = {r["setting_key"]: str(r["setting_value"] or "").strip().strip('"') for r in cur.fetchall()}
    except Exception:
        shop = {}
    return {
        "name": commercial or legal or shop.get("store_name") or _BOUTIQUE_INFO["name"],
        "legal_name": legal or commercial or shop.get("store_name") or _BOUTIQUE_INFO["name"],
        "address": (f.get("fiscal_address") or "").strip() or shop.get("store_location") or _BOUTIQUE_INFO["address"],
        "phone": (f.get("fiscal_phone") or "").strip() or shop.get("store_phone") or _BOUTIQUE_INFO["phone"],
        "whatsapp": shop.get("whatsapp_contact_number") or _BOUTIQUE_INFO["whatsapp"],
        "instagram": shop.get("instagram_url") or "",
        "tiktok": shop.get("tiktok_url") or "",
        "currency": _BOUTIQUE_INFO["currency"],
        "nif": f.get("fiscal_nif") or "",
        "nis": f.get("fiscal_nis") or "",
        "rc": f.get("fiscal_rc") or "",
        "article": f.get("fiscal_article") or "",
        "footer_line": (f.get("receipt_footer_line") or "").strip(),
    }



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




def _doc_prefix(cur, key: str, default: str) -> str:
    """Receipt / document prefix chosen in CMS → Paramètres fiscaux
    (letters and digits only, so references stay safe in URLs and files)."""
    cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", (key,))
    row = cur.fetchone()
    raw = str((row["setting_value"] if row else "") or "").strip().strip('"').upper()
    clean = re.sub(r"[^A-Z0-9]", "", raw)[:10]
    return clean or default



def _record_cash_movement(cur, *, account: str, movement: str, amount: int, source_type: str,
                          reference: str, description: str, user_id: Optional[int]) -> None:
    """Treasury (Trésorerie): money that really entered or left the cash box
    or the bank. Called where the money moves: till sales/refunds, delivered
    cash-on-delivery orders, expense and supplier payments, manual entries."""
    amount = int(amount or 0)
    if amount <= 0:
        return
    cur.execute(
        """INSERT INTO cash_movements (account_type, movement_type, amount_dzd, source_type, source_reference, description, recorded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (account, movement, amount, source_type, reference, description[:255], user_id),
    )



def _account_for_method(method: str) -> str:
    """Cash goes to the cash box; card, transfer, cheque, CCP… to the bank."""
    return "cash_box" if (method or "cash") == "cash" else "bank_account"



# ============================================================================
# BUSINESS DASHBOARD — unified overview across in-store (POS) and online sales.
# Every figure is computed from real records (orders, pos_sales, variants,
# devices, purchase_orders, expenses). Revenue, gross margin and net profit are
# reported as distinct numbers and never presented as interchangeable.
# ============================================================================

# Unit cost expression shared by COGS/valuation queries (variant cost, else product cost).
_UNIT_COST_SQL = "COALESCE(pv.purchase_cost_dzd, p.purchase_cost_dzd, 0)"


# Stock that left (or came back) without a sale: write-offs (damaged, lost,
# gift, correction) and the gaps found by a physical count, valued at cost.
# A return to the supplier is not a loss (the supplier credits it).
_STOCK_LOSS_REASONS_SQL = (
    "(substr(im.reason, 1, 9) = 'writeoff_' AND im.reason != 'writeoff_return_to_supplier')"
    " OR im.reason = 'physical_count_reconcile'"
)



def _stock_losses_dzd(cur, since_utc: Optional[str] = None) -> int:
    """Value at cost of stock lost (positive) minus stock found (count surplus)."""
    where = f"({_STOCK_LOSS_REASONS_SQL})" + (" AND im.created_at >= ?" if since_utc else "")
    return -_scalar(cur, f"""SELECT COALESCE(SUM(im.change_qty * {_UNIT_COST_SQL}), 0) AS v
        FROM inventory_movements im
        JOIN product_variants pv ON pv.id = im.variant_id JOIN products p ON p.id = pv.product_id
        WHERE {where}""", (since_utc,) if since_utc else ())



def _scalar(cur, sql: str, params=(), key: str = "v") -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    return int(row[key]) if row and row[key] is not None else 0


# ============================================================================
# USERS, ROLES & PERMISSIONS — multi-user retail staff management
# Only holders of settings:write (the owner / super admin) can manage staff.
# Permissions are enforced on the backend; the UI only reflects them. Guards
# protect against locking the business out (last active super admin, self
# deactivation). Role, status and password changes revoke the target's sessions
# so they take effect immediately, and every change is written to the audit log.
# ============================================================================

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")



# ----------------------------------------------------------------------------
# Shop time zone. Timestamps are stored in UTC (no zone marker); days, "today"
# and "this month" are the SHOP's days (Algeria: UTC+1, no daylight saving).
# ----------------------------------------------------------------------------
def _load_shop_tz():
    name = os.getenv("SHOP_TIMEZONE", "Africa/Algiers").strip() or "Africa/Algiers"
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # no tz database on this machine: Algeria is a fixed UTC+1
        return timezone(timedelta(hours=1), "UTC+01:00")



SHOP_TZ = _load_shop_tz()

_UTC_FMT = "%Y-%m-%d %H:%M:%S"



def _shop_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(SHOP_TZ)



def _shop_time_text(utc_text: Any) -> str:
    """Stored UTC timestamp -> 'YYYY-MM-DD HH:MM' in shop time (CSV exports)."""
    s = str(utc_text or "").replace("T", " ")
    try:
        dt = datetime.strptime(s[:19], _UTC_FMT)
    except ValueError:
        return s
    return dt.replace(tzinfo=timezone.utc).astimezone(SHOP_TZ).strftime("%Y-%m-%d %H:%M")



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


# Where installed desktop CMS apps ask for updates (staff login required; see
# app/routers/system.py). Reported to the apps by /api/v1/pos/compatibility.
CMS_UPDATE_BASE_URL = "https://api.mus-luxury.com/api/v1/admin/updates/cms"
CMS_UPDATE_MANIFEST_URL = f"{CMS_UPDATE_BASE_URL}/latest.json"
