"""Shop content and settings: banners, home page blocks, pages, delivery zones, fiscal settings, messages."""
from fastapi import APIRouter
import json
import re
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..whatsapp import list_recent_whatsapp_outbox
from ..deps import (
    log_audit,
    require_any_permission,
    require_permission,
)
from ..common import (
    _FISCAL_KEYS,
    _is_protected_setting_key,
    _read_fiscal_settings,
)

router = APIRouter()




def _ensure_safe_url_or_text(val: str, field_name: str = "value") -> str:
    s = str(val or "").strip()
    if re.search(r"(<\s*/?\s*(script|iframe|svg|object|embed)|javascript\s*:|vbscript\s*:|data\s*:\s*text/html|on\w+\s*=)", s, re.IGNORECASE):
        raise HTTPException(status_code=422, detail=f"Contenu refusé dans « {field_name} » : code ou lien dangereux (script, javascript:, …)")
    return s


# ---------------------------------------------------------------------------
# ADMIN-FACING BACKUP ENDPOINTS — REMOVED (owner request)
# The three endpoints formerly here (`/admin/backups` GET/POST and
# `/admin/backups/{id}/verify-restore`) are gone from the HTTP surface.
# Backups still run — automatically — but as operational infrastructure:
#   - Nightly encrypted dump by cron (infrastructure/backups/backup_postgres_and_media.sh)
#   - Pre-migration dump by release-deploy.sh before every CD deploy
#   - Manual restore via infrastructure/backups/restore_backup.sh
# The CMS no longer exposes a 'Backups' page; operators manage them over SSH.
# ---------------------------------------------------------------------------


# PUBLIC STOREFRONT LAYOUT ENDPOINT & DESKTOP CMS WEBSITE CONTROL ENDPOINTS
# The Tauri 2 Desktop CMS controls 100% of the public website via these APIs.
# ============================================================================

class BannerCreateUpdate(BaseModel):
    # hero = big banner at the top of the home page; promo_grid = promotion
    # cards on the home page. No invented defaults: every field comes from
    # the CMS form.
    position: str = Field("promo_grid", regex=r"^(hero|promo_grid|seasonal)$")
    title_fr: str = Field(..., min_length=1, max_length=160)
    title_ar: Optional[str] = Field("", max_length=160)
    title_en: Optional[str] = Field("", max_length=160)
    subtitle_fr: Optional[str] = Field("", max_length=300)
    subtitle_ar: Optional[str] = Field("", max_length=300)
    subtitle_en: Optional[str] = Field("", max_length=300)
    cta_text_fr: Optional[str] = Field("", max_length=60)
    # Shop address the banner opens: /categorie/<slug>, /produit/<slug>,
    # #/boutique, or a full https:// link.
    cta_link: Optional[str] = Field("", max_length=400)
    image_url: Optional[str] = Field("", max_length=400)
    is_active: bool = True
    display_order: int = 1


class HomepageSectionUpdate(BaseModel):
    title_fr: Optional[str] = None
    is_active: bool
    display_order: int = 1
    config: Dict[str, Any] = {}


class StoreSettingsUpdate(BaseModel):
    settings: Dict[str, Any]


@router.get("/api/v1/admin/banners")
def admin_list_banners(admin: dict = Depends(require_permission("content:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM banners ORDER BY display_order ASC, id ASC")
        return {"items": [dict(r) for r in cur.fetchall()]}


@router.post("/api/v1/admin/banners", status_code=201)
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
               (position, title_fr, title_ar, title_en, subtitle_fr, subtitle_ar, subtitle_en,
                cta_text_fr, cta_link, image_url, is_active, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.position, payload.title_fr.strip(), payload.title_ar or "", payload.title_en or "",
                payload.subtitle_fr or "", payload.subtitle_ar or "", payload.subtitle_en or "",
                payload.cta_text_fr or "", (payload.cta_link or "").strip(),
                (payload.image_url or "").strip(), 1 if payload.is_active else 0, payload.display_order
            )
        )
        bid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_banner", "banner", str(bid), {"title_fr": payload.title_fr})
        cur.execute("SELECT * FROM banners WHERE id = ?", (bid,))
        return dict(cur.fetchone())


@router.put("/api/v1/admin/banners/{banner_id}")
def admin_update_banner(
    banner_id: int,
    payload: BannerCreateUpdate,
    admin: dict = Depends(require_permission("content:write"))
):
    for field in ("title_fr", "title_ar", "title_en", "subtitle_fr", "subtitle_ar", "subtitle_en", "cta_text_fr", "cta_link", "image_url"):
        _ensure_safe_url_or_text(getattr(payload, field) or "", field)
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM banners WHERE id = ?", (banner_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Bannière introuvable")
        cur.execute(
            """UPDATE banners SET position = ?, title_fr = ?, title_ar = ?, title_en = ?,
                   subtitle_fr = ?, subtitle_ar = ?, subtitle_en = ?, cta_text_fr = ?, cta_link = ?,
                   image_url = ?, is_active = ?, display_order = ?
               WHERE id = ?""",
            (
                payload.position, payload.title_fr.strip(), payload.title_ar or "", payload.title_en or "",
                payload.subtitle_fr or "", payload.subtitle_ar or "", payload.subtitle_en or "",
                payload.cta_text_fr or "", (payload.cta_link or "").strip(), (payload.image_url or "").strip(),
                1 if payload.is_active else 0, payload.display_order, banner_id,
            ),
        )
        log_audit(conn, int(admin["sub"]), "update_banner", "banner", str(banner_id), {"title_fr": payload.title_fr})
        cur.execute("SELECT * FROM banners WHERE id = ?", (banner_id,))
        return dict(cur.fetchone())



@router.delete("/api/v1/admin/banners/{banner_id}")
def admin_delete_banner(
    banner_id: int,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM banners WHERE id = ?", (banner_id,))
        b = cur.fetchone()
        if not b:
            raise HTTPException(status_code=404, detail="Bannière introuvable")
        cur.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
        log_audit(conn, int(admin["sub"]), "delete_banner", "banner", str(banner_id), {"title_fr": b["title_fr"]})
        return {"deleted": True, "banner_id": banner_id}


# The home page blocks the shop knows how to draw (key → titles, default order).
STANDARD_HOMEPAGE_SECTIONS = {
    "hero_banner": ("Bannière principale", "البانر الرئيسي", "Main banner", 1),
    "trust_bar": ("Barre de confiance (4 garanties)", "شريط الثقة", "Trust bar", 2),
    "categories_grid": ("Grille des catégories", "شبكة الفئات", "Categories grid", 3),
    "featured_products": ("Produits en vedette", "المنتجات المميزة", "Featured products", 4),
    "promo_banners": ("Cartes promotionnelles", "العروض", "Promotion cards", 5),
}



@router.get("/api/v1/admin/homepage-sections")
def admin_list_homepage_sections(admin: dict = Depends(require_permission("content:write"))):
    """Every standard section, with its saved state (visible + order) or the default."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM homepage_sections")
        saved = {r["section_key"]: dict(r) for r in cur.fetchall()}
    items = []
    for key, (t_fr, _t_ar, _t_en, order) in STANDARD_HOMEPAGE_SECTIONS.items():
        row = saved.get(key)
        items.append({
            "section_key": key,
            "title_fr": (row or {}).get("title_fr") or t_fr,
            "is_active": bool(row["is_active"]) if row else True,
            "display_order": int(row["display_order"]) if row else order,
        })
    items.sort(key=lambda x: x["display_order"])
    return {"items": items}



@router.put("/api/v1/admin/homepage-sections/{section_key}")
def admin_update_homepage_section(
    section_key: str,
    payload: HomepageSectionUpdate,
    admin: dict = Depends(require_permission("content:write"))
):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM homepage_sections WHERE section_key = ?", (section_key,))
        sec = cur.fetchone()
        if not sec and section_key in STANDARD_HOMEPAGE_SECTIONS:
            t_fr, t_ar, t_en, order = STANDARD_HOMEPAGE_SECTIONS[section_key]
            cur.execute(
                "INSERT INTO homepage_sections (section_key, title_fr, title_ar, title_en, is_active, display_order, config_json) "
                "VALUES (?, ?, ?, ?, 1, ?, '{}')",
                (section_key, t_fr, t_ar, t_en, order),
            )
            cur.execute("SELECT * FROM homepage_sections WHERE section_key = ?", (section_key,))
            sec = cur.fetchone()
        if not sec:
            raise HTTPException(status_code=404, detail="Section de la page d'accueil introuvable")
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


@router.put("/api/v1/admin/settings")
def admin_update_store_settings(
    payload: StoreSettingsUpdate,
    admin: dict = Depends(require_permission("settings:write"))
):
    for k, v in payload.settings.items():
        if _is_protected_setting_key(k):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Le réglage système '{k}' ne peut pas être modifié ici"
            )
        if k == "pos_tax_rate_percent":
            # Same rule as the fiscal settings screen: a whole number, 0 to 100 %.
            try:
                rate = int(str(v).strip())
            except ValueError:
                rate = -1
            if not 0 <= rate <= 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Le taux de TVA doit être compris entre 0 et 100 %",
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


class DeliveryZoneUpdateInput(BaseModel):
    home_fee_dzd: int = Field(..., ge=0)
    stop_desk_fee_dzd: int = Field(..., ge=0)
    home_supported: bool = True
    stop_desk_supported: bool = True
    estimated_days: str = "24h - 48h"
    communes: Optional[List[str]] = None
    is_active: bool = True


@router.put("/api/v1/admin/delivery-zones/{wilaya_code}")
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


class StaticPageUpsertInput(BaseModel):
    title_fr: str = Field(..., min_length=2, max_length=200)
    title_ar: Optional[str] = ""
    title_en: Optional[str] = ""
    content_fr: str = Field(..., min_length=5)
    content_ar: Optional[str] = ""
    content_en: Optional[str] = ""
    is_published: bool = True


@router.put("/api/v1/admin/pages/{slug}")
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



@router.get("/api/v1/admin/communications/outbox")
def admin_list_communications_outbox(
    limit: int = Query(30, ge=1, le=100),
    admin: dict = Depends(require_permission("orders:write")),
):
    items = list_recent_whatsapp_outbox(limit=limit)
    # The shop's own number comes from CMS → Contenu → Coordonnées.
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", ("whatsapp_contact_number",))
        row = cur.fetchone()
    digits = re.sub(r"\D", "", str((row["setting_value"] if row else "") or "").strip('"'))
    if digits.startswith("0"):
        digits = "213" + digits[1:]
    local = ("0" + digits[3:]) if digits.startswith("213") else digits
    return {
        "items": items,
        "count": len(items),
        "mode": "manual_link",
        "boutique_whatsapp_e164": ("+" + digits) if digits else "",
        "boutique_whatsapp_local": local,
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



def _upsert_setting(cur, key: str, value: str) -> None:
    cur.execute(
        """INSERT INTO store_settings (setting_key, setting_value, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP""",
        (key, value),
    )



@router.get("/api/v1/admin/fiscal/settings")
def admin_get_fiscal_settings(admin: dict = Depends(require_any_permission(["settings:write", "dashboard:read"]))):
    with db_session() as conn:
        return _read_fiscal_settings(conn)



@router.put("/api/v1/admin/fiscal/settings")
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
