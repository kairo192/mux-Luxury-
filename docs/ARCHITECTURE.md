# Mus Luxury (LUXE) — Production System Architecture & Trust Boundaries

## 1. Three-Tier Production Topology

The Mus Luxury (`luxe-ecommerce`) platform is engineered around a strict 3-tier architecture with explicit trust boundaries:

```
+-----------------------------------------------------------------------------------+
| TIER 1A: PUBLIC E-COMMERCE STOREFRONT (apps/storefront/)                          |
| - Customer-facing web boutique (FR / AR RTL / EN)                                 |
| - Zero admin routes, zero CMS code, zero database credentials                     |
| - Guest Cash-on-Delivery (COD) checkout across all 69 Algerian Wilayas (01..69)   |
+-----------------------------------------+-----------------------------------------+
                                          | HTTPS REST (/api/v1/* public routes)
                                          v
+-----------------------------------------------------------------------------------+
| TIER 2: REVERSE PROXY & FASTAPI BACKEND (infrastructure/nginx/ + backend/app/)    |
| - Nginx 1.27 TLS 1.3 Reverse Proxy (Rate-limiting zones, CSP, HSTS, /uploads/)    |
| - Python 3.11 FastAPI Authoritative Service (`backend/app/main.py`)               |
| - PBKDF2-HMAC-SHA256 (310,000 iterations), JWT + `iat_ns` revocation, RBAC        |
| - HMAC-SHA256 Anti-Replay Request Signing (`X-Luxe-Signature`, `X-Luxe-Nonce`)    |
| - Magic-Byte Image Verification (`JPEG`, `PNG`, `WEBP`, polyglot script blocking) |
| - Anti-Retour COD Scoring Engine & Phone Blacklist (`customer_phone_blacklist`)   |
+-----------------------------------------+-----------------------------------------+
                                          | Internal Docker Network (`backend_net`)
                                          v
+-----------------------------------------------------------------------------------+
| TIER 3: AUTHORITATIVE DATABASE & STORAGE (PostgreSQL 16 / SQLite WAL + Volumes)   |
| - 28-Table Relational Schema (`001_initial_schema_postgres.sql` & `.sql`)         |
| - Dual-Engine Runtime Adapter (`backend/app/database.py`)                         |
| - Isolated SHA-256 Verified Backups (`/var/lib/luxe/backups`)                     |
+-----------------------------------------+-----------------------------------------+
                                          ^
                                          | HTTPS REST + Bearer JWT + HMAC Signing
+-----------------------------------------+-----------------------------------------+
| TIER 1B: WINDOWS DESKTOP CMS (apps/desktop-cms/ — Tauri 2 + Rust + React 18)      |
| - Standalone Windows `.exe` / `.msi` native application                           |
| - Windows Credential Manager (`wincred` / `keyring` + `tauri-plugin-store`)       |
| - Zero tokens in `window.localStorage`                                            |
| - 8 Keep-Alive Workspace Tabs + Persistent Drafts (`draftStorage.ts`)             |
| - Client-Side Error Sanitizer, Modal Message Boxes & Offline Mutation Queue       |
+-----------------------------------------------------------------------------------+
```

## 2. Database Schema (28 Tables with 100% SQLite & PostgreSQL 16 Parity)
1. `roles` — Role definitions (`super_admin`, `catalog_editor`, `order_staff`, `analyst`).
2. `permissions` — Granular permission scopes (`products:write`, `categories:write`, `orders:write`, `content:write`, `settings:write`, `backups:write`, `dashboard:read`).
3. `role_permissions` — Many-to-many role-permission assignments.
4. `admin_users` — Administrator accounts with PBKDF2-HMAC-SHA256 hashes and verified Algerian WhatsApp/emergency phones.
5. `brands` — Luxury brand entities and logos.
6. `categories` — Dynamic product categories (`sacs`, `chaussures`, `chale`, `maquillage`, `chapeau`, `casquette`, `les-lunettes`, `les-montres`, `accessoires`).
7. `category_attributes` — 14-type dynamic attribute definitions per category (`is_variant_axis`, `is_filterable`, `is_required`).
8. `category_attribute_options` — Allowed option values and hex color swatches per attribute.
9. `products` — Master product records with `purchase_cost_dzd` (private), `selling_price_dzd`, and optimistic concurrency `version`.
10. `product_images` — Ordered multi-image galleries per product/variant.
11. `product_attribute_values` — Non-variant dynamic specification values per product.
12. `product_variants` — Purchasable SKU variants with `stock_qty >= 0` constraint and optional `price_override_dzd`.
13. `variant_attribute_values` — Variant axis values (`Couleur`, `Taille`, `Pointure`, `Calibre`, etc.).
14. `delivery_zones` - All 69 Algerian Wilayas (`01 Adrar` through `69 El Abiodh Sidi Cheikh`) with their full official commune lists (1,541 communes, loi n° 26-06).
15. `delivery_rates` — Per-Wilaya `home` (À Domicile) and `stop_desk` (Bureau Relais) tariffs in DA.
16. `customers` — Guest checkout contact and lifetime spend aggregation.
17. `orders` — Authoritative COD orders with `idempotency_hash` and `stock_deducted` state flag.
18. `order_items` — Immutable line-item snapshots (`product_name`, `variant_title`, `unit_price_dzd`, `quantity`).
19. `inventory_movements` — Immutable stock ledger tracking every reservation, cancellation restoration, and manual adjustment.
20. `homepage_sections` — CMS-controlled storefront layout visibility and order.
21. `banners` — Editorial hero and promotional collection banners.
22. `static_pages` — Trilingual boutique content pages (`about`, `faq`, `returns`, `terms`).
23. `audit_logs` — Tamper-evident administrative action log (`admin_user_id`, `action`, `entity_type`, `entity_id`, `details_json`).
24. `backup_records` — Compressed `.sql.gz` backup catalog with SHA-256 checksums and isolated restoration status.
25. `store_settings` — Boutique configuration (`store_phone: 0655534154`, `store_location: FVX6+GCJ Mus luxury, Ouled Yaïch`, `free_delivery_threshold_dzd: 25000`).
26. `admin_recovery_codes` — Single-use, rate-limited SHA-256 hashed WhatsApp OTP and offline emergency recovery codes.
27. `coupons` — Percentage and fixed-DA promotional codes with `min_order_dzd`, `max_discount_dzd`, and `usage_limit`.
28. `customer_phone_blacklist` — Anti-Retour COD phone blacklist and return-rate enforcement table.
