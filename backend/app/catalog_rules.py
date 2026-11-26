"""Catalogue rules shared by the Products screen (routers/catalog.py) and the
Shop items screen (routers/store.py): colour / size variants, barcodes
(validation, uniqueness, shop EAN-13 codes) and what the online shop needs
before an article is published."""
import hashlib
import re
import secrets
from typing import Dict, Optional

from fastapi import HTTPException, status


def build_variant_signature(attributes: Dict[str, str], sku_fallback: str = "") -> str:
    if attributes:
        return "|".join(f"{k}:{attributes[k]}" for k in sorted(attributes.keys()))
    return f"sku:{sku_fallback}"


def load_category_attributes_with_options(conn, category_id: int) -> Dict[str, dict]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM category_attributes WHERE category_id = ?", (category_id,))
    attrs = {r["attr_key"]: dict(r) for r in cur.fetchall()}
    if not attrs:
        return attrs
    attr_ids = [a["id"] for a in attrs.values()]
    placeholders = ",".join("?" for _ in attr_ids)
    cur.execute(
        f"SELECT attribute_id, value FROM category_attribute_options WHERE attribute_id IN ({placeholders})",
        attr_ids,
    )
    options_by_attr: Dict[int, set] = {}
    for row in cur.fetchall():
        options_by_attr.setdefault(row["attribute_id"], set()).add(str(row["value"]).strip())
    for attr in attrs.values():
        attr["option_values"] = options_by_attr.get(attr["id"], set())
    return attrs


def validate_variant_attributes(
    cat_attrs: Dict[str, dict],
    attributes: Dict[str, str],
    allow_empty: bool = True,
    allow_custom_values: bool = False,
) -> Dict[str, str]:
    """
    Rejects unknown attributes, non-axis attributes and (unless custom values are allowed)
    option values that do not belong to the category definition. Returns the trimmed map.
    """
    axes = {k: a for k, a in cat_attrs.items() if a.get("is_variant_axis")}
    cleaned: Dict[str, str] = {}
    for raw_key, raw_val in (attributes or {}).items():
        key = str(raw_key).strip()
        if key not in cat_attrs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Caractéristique '{key}' inconnue pour cette catégorie",
            )
        if key not in axes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{key}' ne sert pas à créer des déclinaisons dans cette catégorie",
            )
        val = str(raw_val).strip()
        if not val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Valeur vide pour '{key}'",
            )
        allowed = cat_attrs[key].get("option_values") or set()
        if allowed and val not in allowed and not allow_custom_values:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Valeur '{val}' non valable pour '{key}'. Valeurs possibles : {', '.join(sorted(allowed))}",
            )
        cleaned[key] = val
    if not cleaned and axes and not allow_empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one variant attribute value is required for this category",
        )
    return cleaned


def ensure_variant_attribute_options(conn, cat_attrs: Dict[str, dict], attributes: Dict[str, str]) -> None:
    """
    Registers a custom axis value as a reusable option so dropdowns, filters and the CMS
    stay consistent. Existing options are untouched.
    """
    cur = conn.cursor()
    for key, val in attributes.items():
        attr = cat_attrs.get(key)
        if not attr:
            continue
        allowed = attr.get("option_values") or set()
        if val in allowed:
            continue
        cur.execute(
            "SELECT COALESCE(MAX(display_order), 0) AS mx FROM category_attribute_options WHERE attribute_id = ?",
            (attr["id"],),
        )
        next_order = int(cur.fetchone()["mx"] or 0) + 1
        cur.execute(
            """INSERT INTO category_attribute_options
               (attribute_id, value, label_fr, label_ar, label_en, display_order)
               VALUES (?, ?, ?, '', '', ?)""",
            (attr["id"], val, val, next_order),
        )
        allowed.add(val)
        attr["option_values"] = allowed


def replace_variant_attribute_values(conn, variant_id: int, cat_attrs: Dict[str, dict], attributes: Dict[str, str]) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM variant_attribute_values WHERE variant_id = ?", (variant_id,))
    for key, val in attributes.items():
        cur.execute(
            "INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)",
            (variant_id, cat_attrs[key]["id"], val),
        )


def auto_variant_sku(conn, product_sku: str, attributes: Dict[str, str], signature: str) -> str:
    if attributes:
        parts = [re.sub(r"[^A-Z0-9]", "", str(attributes[k]).upper())[:4] for k in sorted(attributes)]
        base = f"{product_sku}-{'-'.join(parts)}"
    else:
        base = f"{product_sku}-STD"
    cur = conn.cursor()
    cur.execute("SELECT id FROM product_variants WHERE sku = ?", (base,))
    if cur.fetchone():
        base = f"{base}-{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:4].upper()}"
    return base


def _assert_publishable(cur, product_id: int, category_id: int) -> None:
    """Same rule as creating a published product: every required (non-axis)
    characteristic of the category has a saved value."""
    cur.execute(
        """SELECT ca.label_fr FROM category_attributes ca
           WHERE ca.category_id = ? AND ca.is_required = 1 AND ca.is_variant_axis = 0
             AND NOT EXISTS (SELECT 1 FROM product_attribute_values pav
                              WHERE pav.product_id = ? AND pav.attribute_id = ca.id
                                AND TRIM(COALESCE(pav.value_text, '')) <> '')
           ORDER BY ca.display_order ASC, ca.id ASC""",
        (category_id, product_id),
    )
    missing = [r["label_fr"] for r in cur.fetchall()]
    if missing:
        cur.execute("SELECT sku FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Publication impossible ({row['sku'] if row else product_id}) : caractéristiques obligatoires manquantes : {', '.join(missing)}",
        )


# GS1 reserves prefixes 02 and 20-29 for in-store / restricted distribution.
# We mint internal EAN-13 codes under "20" so they never collide with real
# manufacturer GTINs and are never presented as registered GS1 identifiers.
_INTERNAL_EAN_PREFIX = "20"


def ean_check_digit(body: str) -> int:
    """Mod-10 check digit for EAN-13 (12 digits) or EAN-8 (7 digits).
    Weights alternate 1,3,... starting at weight 1 for the leftmost digit of a
    12-digit body (EAN-13) and 3 for a 7-digit body (EAN-8)."""
    digits = [int(c) for c in body]
    # Rightmost body digit always carries weight 3.
    weights = [3 if (len(digits) - 1 - i) % 2 == 0 else 1 for i in range(len(digits))]
    total = sum(d * w for d, w in zip(digits, weights))
    return (10 - (total % 10)) % 10


def upca_check_digit(body11: str) -> int:
    """Mod-10 check digit for UPC-A (11-digit body). Odd positions (1st, 3rd…) weight 3."""
    digits = [int(c) for c in body11]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits))
    return (10 - (total % 10)) % 10


def detect_symbology(code: str) -> str:
    c = code.strip()
    if c.isdigit():
        if len(c) == 13:
            return "ean13"
        if len(c) == 12:
            return "upca"
        if len(c) == 8:
            return "ean8"
        return "numeric"
    return "code128"


def validate_barcode(code: str) -> dict:
    """Returns {valid, symbology, normalized, reason}. Verifies the check digit
    for fixed-length retail symbologies; Code 128 accepts printable ASCII."""
    c = (code or "").strip()
    if not c:
        return {"valid": False, "symbology": None, "normalized": "", "reason": "Code vide"}
    sym = detect_symbology(c)
    if sym == "ean13":
        ok = ean_check_digit(c[:12]) == int(c[12])
        return {"valid": ok, "symbology": "ean13", "normalized": c, "reason": None if ok else "Chiffre de contrôle EAN-13 invalide"}
    if sym == "ean8":
        ok = ean_check_digit(c[:7]) == int(c[7])
        return {"valid": ok, "symbology": "ean8", "normalized": c, "reason": None if ok else "Chiffre de contrôle EAN-8 invalide"}
    if sym == "upca":
        ok = upca_check_digit(c[:11]) == int(c[11])
        return {"valid": ok, "symbology": "upca", "normalized": c, "reason": None if ok else "Chiffre de contrôle UPC-A invalide"}
    if sym == "numeric":
        return {"valid": False, "symbology": "numeric", "normalized": c, "reason": "Longueur numérique non standard (attendu 8, 12 ou 13 chiffres)"}
    # code128: printable ASCII, reasonable length
    if len(c) > 48 or any(ord(ch) < 32 or ord(ch) > 126 for ch in c):
        return {"valid": False, "symbology": "code128", "normalized": c, "reason": "Caractères non imprimables ou code trop long"}
    return {"valid": True, "symbology": "code128", "normalized": c, "reason": None}


def _barcode_in_use(conn, code: str, exclude_variant_id: Optional[int] = None,
                    own_product_id: Optional[int] = None, for_product: bool = False) -> Optional[str]:
    """Returns a human description of where `code` is already used, or None if free.

    A code may be shared inside ONE article: a product and its own variants (a
    scan still finds that article). `own_product_id` is the article being
    written; `for_product=True` when the code goes on the product itself (then
    any of its variants may carry it), else on the variant `exclude_variant_id`
    (then its product may carry it, but no other variant)."""
    cur = conn.cursor()
    cur.execute("SELECT id, sku FROM products WHERE barcode = ? AND deleted_at IS NULL AND id != ?",
                (code, own_product_id if own_product_id is not None else -1))
    p = cur.fetchone()
    if p:
        return f"produit SKU {p['sku']}"
    if for_product and own_product_id is not None:
        cur.execute("SELECT id, sku FROM product_variants WHERE barcode = ? AND product_id != ?", (code, own_product_id))
    elif exclude_variant_id is not None:
        cur.execute("SELECT id, sku FROM product_variants WHERE barcode = ? AND id != ?", (code, exclude_variant_id))
    else:
        cur.execute("SELECT id, sku FROM product_variants WHERE barcode = ?", (code,))
    v = cur.fetchone()
    if v:
        return f"variante SKU {v['sku']}"
    return None


def _generate_internal_ean13(conn) -> str:
    """Mints a unique internal EAN-13 under the restricted-distribution prefix 20."""
    cur = conn.cursor()
    for _ in range(50):
        body = _INTERNAL_EAN_PREFIX + "".join(str(secrets.randbelow(10)) for _ in range(10))  # 12 digits
        code = body + str(ean_check_digit(body))
        cur.execute("SELECT 1 FROM products WHERE barcode = ? UNION SELECT 1 FROM product_variants WHERE barcode = ?", (code, code))
        if not cur.fetchone():
            return code
    raise HTTPException(status_code=500, detail="Impossible de générer un code-barres unique, réessayez")
