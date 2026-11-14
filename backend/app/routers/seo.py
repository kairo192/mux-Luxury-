"""Search engines and link previews: product/category pages and sitemap."""
from fastapi import APIRouter
import re
from fastapi import Request, Response
from ..database import db_session
from .. import seo as _seo
from fastapi.responses import HTMLResponse as _HTMLResponse
from ..common import (
    serialize_product,
)

router = APIRouter()


# ============================================================================
# SEARCH ENGINES & LINK PREVIEWS (app/seo.py)
# nginx routes https://mus-luxury.com/produit/<slug> and /categorie/<slug> here,
# and /sitemap.xml. Public data only (published products, active categories).
# ============================================================================



def _seo_base(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return _seo.store_base_url(f"{proto}://{host}" if host else "")



@router.get("/api/v1/seo/render/{kind}/{slug}", response_class=_HTMLResponse, include_in_schema=False)
def seo_render_page(kind: str, slug: str, request: Request):
    base = _seo_base(request)
    path = f"/{kind}/{slug}"
    found = False
    if kind == "produit" and re.fullmatch(r"[a-z0-9-]{2,160}", slug or ""):
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT p.* FROM products p WHERE p.slug = ? AND p.status = 'published' AND p.deleted_at IS NULL",
                (slug,),
            )
            row = cur.fetchone()
            if row:
                product = serialize_product(conn, dict(row), include_private=False)
                cur.execute("SELECT * FROM categories WHERE id = ? AND deleted_at IS NULL", (product.get("category_id"),))
                cat = cur.fetchone()
                title, tags = _seo.product_page_tags(base, product, dict(cat) if cat else None)
                found = True
        redirect = f"/#/produit/{slug}"
    elif kind == "categorie" and re.fullmatch(r"[a-z0-9-]{2,120}", slug or ""):
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM categories WHERE slug = ? AND is_active = 1 AND deleted_at IS NULL", (slug,))
            cat = cur.fetchone()
            if cat:
                cur.execute(
                    "SELECT slug, name_fr FROM products WHERE category_id = ? AND status = 'published' "
                    "AND deleted_at IS NULL ORDER BY id DESC LIMIT 30",
                    (cat["id"],),
                )
                prods = [dict(r) for r in cur.fetchall()]
                title, tags = _seo.category_page_tags(base, dict(cat), prods)
                found = True
        redirect = f"/#/category/{slug}"
    else:
        redirect = "/"
    if not found:
        title, tags = _seo.not_found_tags(base, path)
    template = _seo.get_template()
    body = _seo.render_page(template, title, tags) if template else _seo.fallback_page(title, tags, redirect)
    return _HTMLResponse(
        body,
        status_code=200 if found else 404,
        headers={"Cache-Control": "public, max-age=300", "Vary": "Accept-Encoding"},
    )



@router.get("/api/v1/seo/sitemap.xml", include_in_schema=False)
def seo_sitemap(request: Request):
    base = _seo_base(request)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT slug, created_at, updated_at FROM categories WHERE is_active = 1 AND deleted_at IS NULL "
            "ORDER BY display_order, id"
        )
        cats = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT slug, created_at, updated_at FROM products WHERE status = 'published' AND deleted_at IS NULL "
            "ORDER BY id DESC LIMIT 45000"
        )
        prods = [dict(r) for r in cur.fetchall()]
    return Response(
        content=_seo.sitemap_xml(base, cats, prods),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
