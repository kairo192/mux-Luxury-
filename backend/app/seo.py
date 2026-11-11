"""
Mus Luxury — search-engine and social-preview support for the online shop.

The shop is a single-page app: its HTML is the same for every page and the
content is drawn by JavaScript. Google can run that JavaScript, but WhatsApp,
Facebook, Instagram and most other link previews cannot. So for the two
kinds of pages worth sharing and indexing:

    https://mus-luxury.com/produit/<slug>
    https://mus-luxury.com/categorie/<slug>

nginx sends the request here. We take the shop's real index.html and replace
the block between <!-- SEO:START --> and <!-- SEO:END --> with page-specific
tags (title, description, canonical URL, Open Graph / WhatsApp preview,
Twitter card, schema.org JSON-LD). The browser then runs the shop exactly as
on the home page, and the shop's JavaScript opens the product/category.

Also builds /sitemap.xml (home, categories, published products).
Never invents data: no ratings or reviews are emitted.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

SEO_BLOCK_RE = re.compile(r"<!-- SEO:START -->.*?<!-- SEO:END -->", re.S)
TITLE_RE = re.compile(r"<title>.*?</title>", re.S)

_TEMPLATE_CACHE: Dict[str, Any] = {"html": None, "at": 0.0}
_TEMPLATE_LOCK = threading.Lock()
TEMPLATE_TTL_SECONDS = 60

DEFAULT_DESCRIPTION = (
    "Mus Luxury — sacs, chaussures, accessoires et beauté. Livraison dans les 69 wilayas "
    "d'Algérie, paiement à la livraison."
)


def store_base_url(request_base: str = "") -> str:
    """Public address of the shop, without trailing slash."""
    base = os.getenv("PUBLIC_STORE_URL", "").strip() or request_base or "https://mus-luxury.com"
    return base.rstrip("/")


def absolute(base: str, url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = str(url)
    if url.startswith(("http://", "https://")):
        return url
    return base + (url if url.startswith("/") else "/" + url)


def _clip(text: Optional[str], limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _json_ld(data: Dict[str, Any]) -> str:
    # "</" must never appear inside a <script> block.
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{raw}</script>'


# ------------------------------------------------------------- template --

def _fetch_template() -> Optional[str]:
    url = os.getenv("STOREFRONT_INTERNAL_URL", "http://storefront").rstrip("/") + "/index.html"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 (internal URL from config)
            body = resp.read().decode("utf-8")
        return body if "<!-- SEO:START -->" in body else None
    except Exception:
        return None


def get_template() -> Optional[str]:
    """The shop's index.html, cached for 60 s. None if the shop is unreachable."""
    with _TEMPLATE_LOCK:
        if _TEMPLATE_CACHE["html"] and time.time() - _TEMPLATE_CACHE["at"] < TEMPLATE_TTL_SECONDS:
            return _TEMPLATE_CACHE["html"]
    fresh = _fetch_template()
    with _TEMPLATE_LOCK:
        if fresh:
            _TEMPLATE_CACHE.update(html=fresh, at=time.time())
        return _TEMPLATE_CACHE["html"]


# ------------------------------------------------------------ head tags --

def head_tags(
    *,
    title: str,
    description: str,
    canonical: str,
    image: Optional[str],
    og_type: str = "website",
    noindex: bool = False,
    extra_meta: Optional[List[Tuple[str, str]]] = None,
    json_ld: Optional[List[Dict[str, Any]]] = None,
) -> str:
    e = lambda v: html.escape(str(v), quote=True)  # noqa: E731
    lines = [
        "<!-- SEO:START -->",
        f'<meta name="description" content="{e(description)}" />',
        f'<link rel="canonical" href="{e(canonical)}" />',
        f'<meta name="robots" content="{"noindex, follow" if noindex else "index, follow, max-image-preview:large"}" />',
        '<meta property="og:site_name" content="Mus Luxury" />',
        '<meta property="og:locale" content="fr_DZ" />',
        f'<meta property="og:type" content="{e(og_type)}" />',
        f'<meta property="og:title" content="{e(title)}" />',
        f'<meta property="og:description" content="{e(description)}" />',
        f'<meta property="og:url" content="{e(canonical)}" />',
        f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}" />',
        f'<meta name="twitter:title" content="{e(title)}" />',
        f'<meta name="twitter:description" content="{e(description)}" />',
    ]
    if image:
        lines += [
            f'<meta property="og:image" content="{e(image)}" />',
            f'<meta name="twitter:image" content="{e(image)}" />',
        ]
    for prop, value in extra_meta or []:
        lines.append(f'<meta property="{e(prop)}" content="{e(value)}" />')
    for block in json_ld or []:
        lines.append(_json_ld(block))
    lines.append("<!-- SEO:END -->")
    return "\n  ".join(lines)


def render_page(template: str, title: str, tags: str) -> str:
    page = SEO_BLOCK_RE.sub(lambda _m: tags, template, count=1)
    return TITLE_RE.sub(lambda _m: f"<title>{html.escape(title)}</title>", page, count=1)


def fallback_page(title: str, tags: str, redirect_to: str) -> str:
    """Used only if the shop's index.html cannot be fetched: link previews still
    work, and people are sent to the same page through the in-app route."""
    target = html.escape(redirect_to, quote=True)
    return (
        "<!DOCTYPE html><html lang=\"fr\"><head><meta charset=\"UTF-8\" />"
        f"<title>{html.escape(title)}</title>\n  {tags}\n"
        f'<meta http-equiv="refresh" content="0;url={target}" /></head>'
        f'<body><a href="{target}">{html.escape(title)}</a></body></html>'
    )


# --------------------------------------------------------- page builders --

def _breadcrumbs(base: str, trail: List[Tuple[str, str]]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": base + path}
            for i, (name, path) in enumerate([("Accueil", "/")] + trail)
        ],
    }


def product_page_tags(base: str, product: Dict[str, Any], category: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    name = product.get("name_fr") or "Article"
    slug = product.get("slug")
    canonical = f"{base}/produit/{slug}"
    price = product.get("selling_price_dzd")
    variants = product.get("variants") or []
    in_stock = any(int(v.get("stock_qty") or 0) > 0 for v in variants) if variants else True
    brand = (product.get("brand") or {}).get("name") if isinstance(product.get("brand"), dict) else None
    images = [absolute(base, product.get("main_image_url"))]
    for im in product.get("images") or product.get("gallery_images") or []:
        url = im.get("image_url") if isinstance(im, dict) else im
        images.append(absolute(base, url))
    images = [u for i, u in enumerate(images) if u and u not in images[:i]]

    price_txt = f"{int(price):,}".replace(",", " ") + " DA" if price is not None else ""
    # The SEO title / description typed in the CMS ("SEO & Livraison" tab) win.
    description = _clip(
        product.get("seo_description")
        or product.get("description_fr")
        or f"{name}{' — ' + price_txt if price_txt else ''}. Livraison 69 wilayas, paiement à la livraison."
    )
    title = (product.get("seo_title") or "").strip() or f"{name} — Mus Luxury"

    offer: Dict[str, Any] = {
        "@type": "Offer",
        "url": canonical,
        "priceCurrency": "DZD",
        "availability": "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock",
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {"@type": "Organization", "name": "Mus Luxury"},
    }
    if price is not None:
        offer["price"] = str(int(price))
    product_ld: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "description": description,
        "sku": product.get("sku"),
        "url": canonical,
        "offers": offer,
    }
    if images:
        product_ld["image"] = images
    if brand:
        product_ld["brand"] = {"@type": "Brand", "name": brand}
    if category:
        product_ld["category"] = category.get("name_fr")

    trail = []
    if category:
        trail.append((category.get("name_fr") or "", f"/categorie/{category.get('slug')}"))
    trail.append((name, f"/produit/{slug}"))

    extra = [("product:price:currency", "DZD")]
    if price is not None:
        extra.insert(0, ("product:price:amount", str(int(price))))
    extra.append(("product:availability", "in stock" if in_stock else "out of stock"))

    tags = head_tags(
        title=title,
        description=description,
        canonical=canonical,
        image=images[0] if images else absolute(base, "/assets/mus_luxury_logo.png"),
        og_type="product",
        extra_meta=extra,
        json_ld=[product_ld, _breadcrumbs(base, trail)],
    )
    return title, tags


def category_page_tags(base: str, category: Dict[str, Any], products: List[Dict[str, Any]]) -> Tuple[str, str]:
    name = category.get("name_fr") or "Collection"
    slug = category.get("slug")
    canonical = f"{base}/categorie/{slug}"
    description = _clip(
        category.get("description_fr")
        or f"{name} — {len(products)} article(s) Mus Luxury. Livraison 69 wilayas, paiement à la livraison."
    )
    title = f"{name} — Mus Luxury"
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": f"{base}/produit/{p['slug']}", "name": p.get("name_fr")}
            for i, p in enumerate(products[:30])
        ],
    }
    tags = head_tags(
        title=title,
        description=description,
        canonical=canonical,
        image=absolute(base, category.get("image_url")) or absolute(base, "/assets/mus_luxury_logo.png"),
        json_ld=[item_list, _breadcrumbs(base, [(name, f"/categorie/{slug}")])],
    )
    return title, tags


def not_found_tags(base: str, path: str) -> Tuple[str, str]:
    title = "Article introuvable — Mus Luxury"
    tags = head_tags(
        title=title,
        description=DEFAULT_DESCRIPTION,
        canonical=base + path,
        image=absolute(base, "/assets/mus_luxury_logo.png"),
        noindex=True,
    )
    return title, tags


# --------------------------------------------------------------- sitemap --

def sitemap_xml(base: str, categories: List[Dict[str, Any]], products: List[Dict[str, Any]]) -> str:
    def url(loc: str, lastmod: Optional[str], priority: str) -> str:
        lm = f"<lastmod>{html.escape(str(lastmod)[:10])}</lastmod>" if lastmod else ""
        return f"<url><loc>{html.escape(loc)}</loc>{lm}<priority>{priority}</priority></url>"

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             url(base + "/", None, "1.0")]
    for c in categories:
        parts.append(url(f"{base}/categorie/{c['slug']}", c.get("updated_at") or c.get("created_at"), "0.8"))
    for p in products:
        parts.append(url(f"{base}/produit/{p['slug']}", p.get("updated_at") or p.get("created_at"), "0.6"))
    parts.append("</urlset>")
    return "\n".join(parts)
