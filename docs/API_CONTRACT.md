# Mus Luxury (LUXE) — Complete API Contract & Endpoint Inventory

Machine-readable OpenAPI 3.0 specification: `docs/openapi.json` (also served at `/api/v1/openapi.json`).

## 1. Public Storefront Endpoints (No Authentication Required)
| Method | Route | Consumer | Rate Limit | Request / Query Schema | Response Contract & Security Rules | Verified By |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Docker / Nginx / CMS | 15 req/s | None | `{ status, database, active_wilayas: 69, active_categories, timestamp }` | `test_28`, `test_58` |
| `GET` | `/api/v1/ready` | Docker / K8s Readiness | 15 req/s | None | `{ ready: true, status: "ready", database, storage_writable, active_wilayas: 69 }` | `test_62` |
| `GET` | `/api/v1/store/settings` | Storefront | 15 req/s | None | Public boutique settings (`store_phone: 0655534154`, `store_location`, `free_delivery_threshold_dzd`) | `test_01` |
| `GET` | `/api/v1/store/layout` | Storefront & CMS | 15 req/s | None | `{ settings, homepage_sections, banners }` | `test_08` |
| `GET` | `/api/v1/categories` | Storefront & CMS | 15 req/s | None | Active categories with 14-type `attributes` and `options` | `test_05`, `test_20` |
| `GET` | `/api/v1/categories/{slug}` | Storefront | 15 req/s | Path `slug` | Single category schema + attributes (`404` if inactive/missing) | `test_05`, `test_20` |
| `GET` | `/api/v1/brands` | Storefront & CMS | 15 req/s | None | `{ items: [{ id, name, slug, logo_url }] }` | `test_27` |
| `GET` | `/api/v1/products` | Storefront | 15 req/s | `category`, `brand`, `q`, `min_price`, `max_price`, `in_stock_only`, `sort`, `page`, `page_size` | Published products only; **strictly omits `purchase_cost_dzd`** | `test_02`, `test_19`, `test_63` |
| `GET` | `/api/v1/products/{slug}` | Storefront | 15 req/s | Path `slug` | Full PDP with variants, gallery images, and dynamic attributes; omits `purchase_cost_dzd` | `test_02`, `test_20` |
| `GET` | `/api/v1/delivery-zones` | Storefront & CMS | 15 req/s | None | All 69 Algerian Wilayas (`01`–`69`) with `home` and `stop_desk` rates in DA | `test_12` |
| `GET` | `/api/v1/delivery-zones/calculate` | Storefront | 15 req/s | `wilaya_code`, `delivery_method` (`home`\|`stop_desk`), `subtotal_dzd`, `coupon_code` | Server-calculated delivery fee, discount, and `total_dzd` | `test_22`, `test_63` |
| `POST` | `/api/v1/coupons/validate` | Storefront | 15 req/s | `{ code, subtotal_dzd }` | Validates active coupon, `min_order_dzd`, and `usage_limit` (`400`/`404` on invalid) | `test_20`, `test_43` |
| `POST` | `/api/v1/orders` | Storefront Guest COD | 15 req/min/IP | `GuestOrderCreate` + `Idempotency-Key` header | Recalculates server price, blocks COD blacklisted phones (`403`), locks stock (`409`), returns `order_reference` & WhatsApp links (`201`) | `test_06`, `test_30`, `test_40`, `test_42`, `test_43` |
| `GET` | `/api/v1/orders/track` | Storefront | 30 req/min/IP | `reference`, `phone` | IDOR-safe order status lookup requiring matching `reference` + normalized `phone` | `test_10`, `test_42` |
| `GET` | `/api/v1/pages` & `/api/v1/pages/{slug}` | Storefront & CMS | 15 req/s | Optional `slug` | Published static pages (`about`, `faq`, `returns`, `terms`) | `test_28`, `test_49` |
| `GET` | `/uploads/{filename}` | Storefront & CMS | 15 req/s | `^img_[a-f0-9]{16}\.(jpg\|png\|webp)$` | Serves verified uploaded image with `X-Content-Type-Options: nosniff` | `test_47` |

## 2. Administrative & Security Endpoints (Bearer JWT + RBAC Permission Required)
| Method | Route | Required Permission | Purpose & Security Controls | Verified By |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/auth/setup-status` | Public Bootstrap Check | Returns `{ requires_owner_setup: bool }` from PostgreSQL/SQLite | `test_14` |
| `POST` | `/api/v1/admin/auth/initialize-owner` | One-Time Lock (`403` after setup) | Creates primary owner in DB and permanently locks setup across all PCs | `test_15` |
| `POST` | `/api/v1/admin/auth/login` | Rate-Limited (`5 req/min/IP`) | Verifies PBKDF2-HMAC-SHA256 password and issues signed JWT with `iat_ns` | `test_03`, `test_48` |
| `POST` | `/api/v1/admin/auth/logout` | Authenticated Admin | Revokes active Bearer token immediately in `REVOKED_TOKENS` | `test_03` |
| `GET` | `/api/v1/admin/auth/recovery/status` | Public Recovery Check | Reports honest WhatsApp Cloud API configuration status & `0655534154` | `test_09`, `test_34` |
| `POST` | `/api/v1/admin/auth/recovery/request` | Rate-Limited (`3 req/5m/IP`) | Dispatches 6-digit single-use WhatsApp OTP (`503` if unconfigured) | `test_09`, `test_34` |
| `POST` | `/api/v1/admin/auth/recovery/verify` | Rate-Limited (`5 req/5m/IP`) | Verifies single-use OTP/Emergency code, rotates password, **and revokes all prior user sessions** | `test_09`, `test_34`, `test_61` |
| `POST` | `/api/v1/admin/auth/recovery/rotate-emergency-code` | `settings:write` | Generates a new single-use offline emergency code | `test_34`, `test_45` |
| `POST` | `/api/v1/admin/secure-action` | Authenticated + HMAC Headers | Verifies `X-Luxe-Signature`, `X-Luxe-Timestamp` (300s window), and `X-Luxe-Nonce` anti-replay | `test_16`, `test_17` |
| `GET` | `/api/v1/admin/dashboard` & `/api/v1/admin/reports` | `dashboard:read` | Real-time revenue, profit (`selling - purchase_cost`), stock alerts, and Wilaya breakdown | `test_21`, `test_23` |
| `GET` | `/api/v1/admin/sync/delta` | `dashboard:read` | Delta sync of missed orders and stock movements after PC restart | `test_13` |
| `GET/POST/PUT/DELETE` | `/api/v1/admin/categories*` & `/category-attributes*` | `categories:write` | Full CRUD for categories and 14-type dynamic attributes with migration protection (`409`) | `test_05`, `test_27` |
| `GET/POST/PUT/DELETE` | `/api/v1/admin/products*`, `/brands`, `/variants/*` | `products:write` | Product CRUD, optimistic concurrency (`expected_version` -> `409`), variant matrix, gallery, stock adjustment | `test_11`, `test_24`, `test_29` |
| `POST` | `/api/v1/admin/upload` | `products:write` | Magic-byte binary inspection (`JPEG`/`PNG`/`WEBP`, max 5 MB), path traversal & script blocking | `test_07`, `test_18`, `test_47` |
| `GET/PATCH` | `/api/v1/admin/orders*`, `/invoice`, `/export.csv` | `orders:write` | Order state machine, stock restoration on cancel/return, printable invoice, formula-safe CSV export | `test_25`, `test_44` |
| `POST/GET` | `/api/v1/admin/orders/{id}/notify-whatsapp`, `/communications/outbox` | `orders:write` | Dispatches 4 Algerian COD customer WhatsApp templates and returns outbox log | `test_59` |
| `GET/POST/DELETE` | `/api/v1/admin/cod-risk/*` | `orders:write` | Real-time phone return-rate scoring (`Anti-Retour COD`) and phone blacklist management | `test_40` |
| `PUT` | `/api/v1/admin/delivery-zones/{code}` & `-bulk` | `content:write` | Updates single or all 69 Wilayas Home & Stop-Desk fees in DA | `test_21`, `test_22` |
| `GET/POST/PUT` | `/api/v1/admin/banners`, `/homepage-sections/*`, `/coupons`, `/pages/*` | `content:write` | Full CMS control over storefront layout, banners, coupons, and static pages | `test_08`, `test_28` |
| `PUT` | `/api/v1/admin/settings` | `settings:write` | Updates global store settings (`store_phone`, `whatsapp_contact_number`, `store_location`) | `test_08` |
| `GET/POST` | `/api/v1/admin/backups*` & `/verify-restore` | `backups:write` | Creates `.sql.gz` backup with SHA-256 checksum and runs non-destructive isolated restore test | `test_26` |
| `GET` | `/api/v1/admin/audit-logs` | `dashboard:read` | Returns administrative audit trail (`audit_logs`) with actor email and JSON details | `test_62` |
