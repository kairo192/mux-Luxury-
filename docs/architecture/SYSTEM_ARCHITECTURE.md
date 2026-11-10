# Mus Luxury (`LUXE`) — Production System Architecture & Technical Specification

## 1. Executive Summary & Topology Overview

Mus Luxury is an enterprise-grade luxury e-commerce and point-of-sale ecosystem engineered specifically for the Algerian retail market (`DZD`). The system is architected around a strict **3-Tier topology** with distinct security boundaries, authoritative server validation, and durable offline point-of-sale operations.

```text
                                 INTERNET
                                    │
                                    │ HTTPS (TLS 1.3 / HSTS)
                                    ▼
                    ┌──────────────────────────────┐
                    │      NGINX REVERSE PROXY     │
                    │      (infrastructure/nginx)  │
                    │   Ports 80 -> 443 Redirect   │
                    │  Rate Limiting, CSP, Uploads │
                    └───────┬──────────────┬───────┘
                            │              │
              ┌─────────────┘              └─────────────┐
              ▼                                          ▼
┌───────────────────────────┐              ┌───────────────────────────┐
│     PUBLIC STOREFRONT     │              │    FASTAPI CLOUD API      │
│     (apps/storefront)     │              │     (backend/app)         │
│ React 18 + Vite (SPA)     │              │ Python 3.11 + Uvicorn     │
│ 69-Wilaya COD Checkout    │              │ RBAC, PBKDF2-HMAC-SHA256  │
│ Zero Admin / CMS Code     │              │ HMAC-SHA256 Anti-Replay   │
└───────────────────────────┘              └─────────────┬─────────────┘
                                                         │
                                                         │ Private Docker Bridge
                                                         │ (backend_net: internal)
                                                         ▼
                                           ┌───────────────────────────┐
                                           │    POSTGRESQL 16 (PROD)   │
                                           │   Dual-Engine Relational  │
                                           │   41 Relational Tables    │
                                           │   Strict Foreign Keys     │
                                           └───────────────────────────┘
                                                         ▲
                                                         │ HTTPS REST + Bearer JWT
                                                         │ + HMAC Nonce Signature
                                           ┌─────────────┴─────────────┐
                                           │    WINDOWS DESKTOP CMS    │
                                           │    (apps/desktop-cms)     │
                                           │ Tauri 2.0 (Rust MSVC)     │
                                           │ Windows Credential Mgr    │
                                           │ SQLite Embedded POS Mirror│
                                           │ ESC/POS & ZPL Direct Spool│
                                           └───────────────────────────┘
```

---

## 2. Canonical Production Domains

All services, CORS origins, and mobile web clients resolve strictly against official domains:
- **Public Boutique Storefront:** `https://mus-luxury.com` and `https://www.mus-luxury.com`
- **Central API Gateway:** `https://api.mus-luxury.com/api/v1`
- **Zero Legacy Domains:** All obsolete `.dz` and `musluxury.dz` domains have been eliminated.

---

## 3. Database Architecture (41 Relational Tables)

The storage tier maintains 100% schema parity across **PostgreSQL 16** (production) and **SQLite 3** (local development and automated test suites). Foreign keys, constraints, and optimistic locking (`version`) prevent inconsistent states or negative inventory.

### Table Inventory by Domain:

#### A. RBAC & Identity (4 tables)
1. `roles`: Role definitions (`super_admin`, `catalog_editor`, `order_staff`, `analyst`).
2. `permissions`: Granular permission scopes (`products:write`, `categories:write`, `orders:write`, `content:write`, `settings:write`, `backups:write`, `dashboard:read`).
3. `role_permissions`: Many-to-many role-permission mapping.
4. `admin_users`: Administrative accounts with PBKDF2-HMAC-SHA256 password hashes (600,000 iterations).

#### B. Dynamic Catalog & Attribute Matrix (9 tables)
5. `brands`: Luxury brands with vector insignia and country of origin.
6. `categories`: 14 luxury product categories (`sacs`, `chaussures`, `chale`, `maquillage`, `chapeau`, `casquette`, `les-lunettes`, `les-montres`, `accessoires`, etc.).
7. `category_attributes`: Dynamic attributes with type constraints (`text`, `number`, `select`, `multiselect`, `color`, `dimensions`, `boolean`).
8. `category_attribute_options`: Allowed option values and hex swatches.
9. `products`: Master product entities with private `purchase_cost_dzd`, public `selling_price_dzd`, and optimistic concurrency `version`.
10. `product_images`: Ordered image galleries per product.
11. `product_attribute_values`: Dynamic category specifications per product.
12. `product_variants`: Purchasable SKU variants with `stock_qty >= 0` check constraint and barcode.
13. `variant_attribute_values`: Variant axes (`Couleur`, `Taille`, `Pointure`, `Calibre`).

#### C. Algerian Wilayas & COD Logistics (4 tables)
14. `delivery_zones`: All 69 Algerian Wilayas (`01 Adrar` through `69 El Abiodh Sidi Cheikh`) with 1,541 communes (Loi n° 26-06).
15. `delivery_rates`: Per-Wilaya `home` (À Domicile) and `stop_desk` (Bureau Relais) tariffs in DZD.
16. `customers`: Customer records, phone normalization, order history, and lifetime spend.
17. `customer_phone_blacklist`: Anti-Retour COD return-rate tracking and fraud mitigation.

#### D. Orders & Stock Movements (3 tables)
18. `orders`: Authoritative COD orders with `idempotency_hash` and `stock_deducted` state flag.
19. `order_items`: Immutable line-item snapshots (`product_name`, `variant_title`, `unit_price_dzd`, `quantity`).
20. `inventory_movements`: Immutable stock ledger tracking reservations, cancellations, returns, and write-offs.

#### E. Editorial & Storefront Content (4 tables)
21. `homepage_sections`: Dynamic homepage arrangement and visibility.
22. `banners`: Editorial hero and promotion banners.
23. `static_pages`: Content pages (`about`, `faq`, `returns`, `terms`) in FR/AR/EN.
24. `coupons`: Promotional discount codes with minimum order limits and usage limits.

#### F. Audit & Security (3 tables)
25. `audit_logs`: Tamper-evident admin action log (`admin_user_id`, `action`, `entity_type`, `entity_id`, `details_json`).
26. `backup_records`: Backup catalog with SHA-256 checksums and isolated restore status.
27. `store_settings`: Configuration key-value store (`store_phone`, `store_location`, `free_delivery_threshold_dzd`).
28. `admin_recovery_codes`: Single-use emergency recovery codes (rate-limited, hashed).

#### G. Point of Sale (POS) & Cash Register (6 tables)
29. `devices`: Registered POS hardware terminals, thermal receipt printers, and barcode scanners.
30. `cash_register_sessions`: Cash register shift sessions with opening float, cash drops, and closing reconciliations.
31. `pos_sales`: In-store POS sale records linked to terminal sessions and cashiers.
32. `pos_sale_items`: POS line items with barcode scanning timestamps and item discounts.
33. `pos_payments`: Multi-tender payment breakdown (Cash, CIB/Edahabia, Bank Transfer).
34. `cash_movements`: Cash float adjustments, payouts, and cash drops with supervisor sign-off.

#### H. Suppliers & Purchasing (3 tables)
35. `suppliers`: Supplier directory, contact information, payment terms, and outstanding balances.
36. `purchase_orders`: Inbound procurement orders, status lifecycle, and supplier invoices.
37. `purchase_order_items`: Line-item purchase receipts updating stock intake and weighted average costs.

#### I. Accounting & Financial Ledger (2 tables)
38. `expenses`: Operating expense records categorized by ledger codes (Rent, Salaries, Utilities, Supplies).
39. `accounting_ledger`: Double-entry accounting ledger balancing cash, receivables, sales, inventory, and payables.

#### J. Physical Inventory Count (2 tables)
40. `inventory_counts`: Physical stock audit cycles and discrepancy sessions.
41. `inventory_count_items`: Expected stock vs counted stock with variance adjustments.

---

## 4. Hardware Peripherals Integration

The desktop POS communicates natively with hardware peripherals without browser dialogs:
- **Thermal Receipt Printing:** Native byte-level ESC/POS generation (`apps/desktop-cms/src-tauri/src/pos_hardware/escpos.rs`) over Windows raw printer spooler.
- **Cash Drawer:** Kick drawer command (`ESC p 0 25 250`) sent directly through thermal printer RJ11 port.
- **Barcode Label Printing:** Native ZPL II command generation (`apps/desktop-cms/src-tauri/src/pos_hardware/zpl.rs`) supporting 50x30mm jewelry and apparel labels.
- **Barcode Scanner:** Keyboard wedge support with configurable suffix (`Enter`) and fast catalog lookup loop.

---

## 5. Security Architecture & Trust Boundaries

1. **OS Keychain Token Isolation:** The Tauri desktop application stores all admin authentication tokens in the Windows Credential Manager (`com.musluxury.cms.wincred`) via Rust FFI. Zero credentials exist in `localStorage`.
2. **Server-Side Authorization:** Every price, coupon, stock quantity, and tax calculation is enforced by the FastAPI backend. Frontend calculations are strictly advisory.
3. **Emergency Owner Recovery:** WhatsApp password recovery endpoints are permanently removed. Owner password resets require authenticated VPS access via the server CLI:
   ```bash
   python3 backend/scripts/emergency_reset_owner.py --email admin@mus-luxury.com --new-password <SecurePass>
   ```
4. **Anti-Replay Nonce Verification:** Critical administrative commands require cryptographic HMAC-SHA256 signatures with millisecond timestamp skew verification (`SIGNATURE_MAX_SKEW_SECONDS=300`) and unique nonces (`X-Luxe-Nonce`).

