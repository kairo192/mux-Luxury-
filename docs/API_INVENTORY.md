# API INVENTORY & SYNCHRONIZATION SPECIFICATION — MUS LUXURY (`LUXE`)

**Base Path:** `/api/v1`  
**Backend Entrypoint:** `backend/app/main.py`  
**Desktop CMS Client:** `apps/desktop-cms/src/api/adminClient.ts`  
**Public Storefront Client:** `apps/storefront/src/api/client.ts`

---

## 1. Public Storefront Endpoints (No Customer Account Required)

| Method & Path | Purpose | Auth / Permissions | Request Validation | Response Schema | Status Codes | Automated Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /api/v1/store/settings` | Returns public store settings (`store_name`, `whatsapp_contact_number: +213655534154`, `store_location: FVX6+GCJ Mus luxury, Ouled Yaïch`, `instagram_url`, `tiktok_url`, `colors`). | Public (None) | None | `Dict[str, Any]` | `200` | `test_01_public_settings_and_security_headers` |
| `GET /api/v1/store/layout` | Returns full storefront layout (settings, active homepage sections, active banners, and active categories with attributes). | Public (None) | None | `{ settings, homepage_sections, banners, categories }` | `200` | `test_08_desktop_cms_controls_entire_website_layout` |
| `GET /api/v1/categories` | Lists all active, non-archived categories ordered by `display_order` with nested `attributes` and `options`. | Public (None) | None | `{ items: Category[] }` | `200` | `test_05`, `test_27` |
| `GET /api/v1/categories/{slug}` | Retrieves a single active category and its dynamic attribute definitions by slug. | Public (None) | `slug: str` | `Category` | `200`, `404` | `test_05` |
| `GET /api/v1/brands` | Lists all active brands and logos. | Public (None) | None | `{ items: Brand[] }` | `200` | `test_27` |
| `GET /api/v1/products` | Lists published, non-archived products with filtering (`category`, `brand`, `q`, `min_price`, `max_price`, `in_stock_only`, dynamic `?attr_<key>=<val>`), sorting, and pagination. Never exposes `purchase_cost_dzd`. | Public (None) | Query parameters (`page >= 1`, `page_size <= 50`) | `{ items: PublicProduct[], total, page, page_size }` | `200`, `422` | `test_02`, `test_19`, `test_20` |
| `GET /api/v1/products/{slug}` | Retrieves a single published product with variants, effective prices, stock, and category attribute definitions. | Public (None) | `slug: str` | `PublicProduct` | `200`, `404` | `test_02`, `test_20`, `test_24`, `test_27` |
| `GET /api/v1/delivery-zones` | Lists all 69 Algerian Wilayas (`01` to `69`), their communes, and `home` / `stop_desk` rates in `DA`. | Public (None) | None | `{ items: DeliveryZone[] }` | `200` | `test_12_all_69_algerian_wilayas_configured` |
| `GET /api/v1/delivery-zones/calculate` | Calculates exact `home` or `stop_desk` fee for a Wilaya (`01`–`69`), promo discount, and final order total in `DA`. | Public (None) | `wilaya_code`, `delivery_method` (`home`\|`stop_desk`), `subtotal_dzd >= 0`, `coupon_code` | `{ wilaya_code, communes, home_rate, stop_desk_rate, subtotal_dzd, discount_dzd, delivery_fee_dzd, total_dzd }` | `200`, `400`, `404` | `test_22` |
| `POST /api/v1/coupons/validate` | Validates a promotional coupon code against a cart subtotal in `DA`. | Public (None) | `CouponValidateRequest` (`code`, `subtotal_dzd >= 0`) | `{ valid, code, discount_type, discount_dzd, new_subtotal_dzd }` | `200`, `400`, `404` | `test_20` |
| `POST /api/v1/orders` | Submits a Guest Cash-on-Delivery (`COD`) order. Ignores any client-submitted prices, locks variant stock with `BEGIN IMMEDIATE`, enforces `Idempotency-Key` / payload deduplication, and logs `inventory_movements`. | Public (Rate-limited: 15/min/IP) | `GuestOrderCreate` (Algerian phone regex, `wilaya_code`, `delivery_method`, `items`) + optional `Idempotency-Key` header | `{ order_id, order_reference, status, subtotal_dzd, discount_dzd, delivery_fee_dzd, total_dzd, items }` | `201`, `400`, `404`, `409`, `429` | `test_06`, `test_10`, `test_22`, `test_24`, `test_25`, `test_27` |
| `GET /api/v1/orders/track` | IDOR-safe guest order tracking requiring BOTH `reference` and matching `phone`. Strips `internal_notes`. | Public (None) | `reference: str`, `phone: str` | `PublicOrderView` | `200`, `404` | `test_10_coupons_and_idor_safe_guest_order_tracking` |

---

## 2. Administrative & Desktop CMS Endpoints (`/api/v1/admin/*`)

| Method & Path | Purpose | Auth / Permissions | Request Validation | Response Schema | Status Codes | Automated Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /api/v1/admin/auth/setup-status` | Checks if the primary Owner (`super_admin`) has been initialized in the database. | Public (Read-only status) | None | `{ is_initialized, requires_owner_setup, store_name }` | `200` | `test_14`, `test_15` |
| `POST /api/v1/admin/auth/initialize-owner` | One-time Owner provisioning (Name, Email, Password, WhatsApp recovery phone, Emergency phone). Permanently locks (`403`) once initialized. | First-run only (Rate-limited: 3/5min) | `OwnerInitializeInput` | `{ initialized, emergency_code_backup, access_token, user }` | `201`, `403`, `409`, `422` | `test_15_one_time_owner_initialization_lockout` |
| `POST /api/v1/admin/auth/login` | Authenticates administrator and issues signed Bearer token with role permissions. | Public (Rate-limited: 5/min/IP) | `LoginRequest` (`email`, `password`) | `{ access_token, token_type, user }` | `200`, `401`, `429` | `test_03`, `test_04`, `test_07` |
| `POST /api/v1/admin/auth/logout` | Revokes the active Bearer token immediately in `REVOKED_TOKENS`. | Bearer Token | None | `{ status: "logged_out" }` | `200`, `401` | `test_03` |
| `POST /api/v1/admin/auth/recovery/request` | Initiates WhatsApp Cloud API OTP recovery. Returns `503` if WhatsApp Cloud API credentials are not configured on server. | Public (Rate-limited: 3/5min) | `RecoveryRequestInput` (`phone`, `channel`) | `{ status, message }` | `200`, `429`, `503` | `test_09_whatsapp_recovery_honesty_and_single_use_otp` |
| `POST /api/v1/admin/auth/recovery/verify` | Verifies single-use WhatsApp OTP or Offline Emergency Code, rotates password hash, and invalidates code. | Public (Rate-limited: 5/5min) | `RecoveryVerifyInput` (`phone`, `verification_code`, `new_password >= 10 chars`) | `{ status: "password_updated", sessions_revoked: true }` | `200`, `400`, `429` | `test_09` |
| `GET /api/v1/admin/dashboard` | Real-time server-derived KPIs: active products, categories, low/out-of-stock variants, orders by status, revenue, recent orders, audit activity, sync health, and last backup. | Bearer (`dashboard:read`) | None | `DashboardSummary` | `200`, `401`, `403` | `test_23_dashboard_comprehensive_metrics_and_backup_status` |
| `GET /api/v1/admin/sync/delta` | Fetches missed orders, inventory movements, and current variant stocks recorded while the Desktop CMS PC was off. | Bearer (`dashboard:read`) | `since_order_id >= 0`, `since_movement_id >= 0` | `{ server_timestamp, latest_order_id, missed_orders_count, new_orders, new_movements, current_variant_stocks }` | `200`, `401` | `test_13`, `test_27` |
| `POST /api/v1/admin/categories` | Creates a custom category. | Bearer (`categories:write`) | `CategoryCreate` | `Category` | `201`, `409`, `422` | `test_05`, `test_27` |
| `PUT /api/v1/admin/categories/{category_id}` | Updates category metadata, visibility, or display ordering. | Bearer (`categories:write`) | `CategoryUpdateInput` | `Category` | `200`, `404` | `test_05` |
| `DELETE /api/v1/admin/categories/{category_id}` | Safely archives a category (`is_active=0`, `deleted_at`). | Bearer (`categories:write`) | `category_id: int` | `{ archived: true, category_id }` | `200`, `404` | `test_05` |
| `POST /api/v1/admin/category-attributes` | Adds a dynamic attribute (14 supported types) and options to a category. | Bearer (`categories:write`) | `CategoryAttributeCreate` | `Category` | `201`, `404`, `409`, `422` | `test_05`, `test_27` |
| `DELETE /api/v1/admin/category-attributes/{attr_id}` | Removes a category attribute; requires `force_migrate=true` if used by existing products. | Bearer (`categories:write`) | `force_migrate: bool` | `{ deleted: true, attribute_id, migrated_records }` | `200`, `404`, `409` | `test_05` |
| `POST /api/v1/admin/brands` | Creates a brand and brand logo. | Bearer (`products:write`) | `BrandCreateInput` | `Brand` | `201`, `409` | `test_27` |
| `GET /api/v1/admin/products` | Lists all products for the CMS (including `draft`, `archived`, and private `purchase_cost_dzd`). | Bearer (`products:write`) | `q`, `category_id`, `status`, `include_archived`, `page`, `page_size` | `{ items: AdminProduct[], total, page, page_size }` | `200`, `401`, `403` | `test_24` |
| `POST /api/v1/admin/products` | Creates a product, validates required category attributes when published, and creates initial variants. | Bearer (`products:write`) | `ProductCreate` | `AdminProduct` | `201`, `404`, `422` | `test_05`, `test_27` |
| `PUT /api/v1/admin/products/{product_id}` | Updates product fields, status, and dynamic attributes with `expected_version` optimistic concurrency control. | Bearer (`products:write`) | `ProductConcurrencyUpdate` | `AdminProduct` | `200`, `404`, `409` | `test_11`, `test_24`, `test_27` |
| `DELETE /api/v1/admin/products/{product_id}` | Safely archives a product (`status='archived'`, `deleted_at`) while preserving all historical `order_items`. | Bearer (`products:write`) | `product_id: int` | `{ archived: true, product_id, historical_order_items_preserved }` | `200`, `404` | `test_24` |
| `POST /api/v1/admin/products/bulk-status` | Bulk updates product statuses (`draft`, `published`, `archived`). | Bearer (`products:write`) | `BulkProductStatusInput` | `{ updated_count, status }` | `200`, `400` | `test_24` |
| `POST /api/v1/admin/products/{product_id}/generate-variants` | Cartesian variant matrix generator across category variant axes (`color`, `size`, etc.). | Bearer (`products:write`) | `VariantMatrixRequest` | `{ created, skipped_duplicates }` | `201`, `400`, `404` | `test_05`, `test_27` |
| `POST /api/v1/admin/variants/{variant_id}/adjust-stock` | Atomically adjusts variant stock (`change_qty`), prevents negative stock (`400`), and records audit trail in `inventory_movements`. | Bearer (`products:write`) | `StockAdjustmentInput` | `{ variant_id, sku, previous_qty, new_qty }` | `200`, `400`, `404` | `test_21` |
| `GET /api/v1/admin/inventory/movements` | Lists chronological inventory movement audit records. | Bearer (`products:write`) | `variant_id`, `limit` | `{ items: InventoryMovement[] }` | `200` | `test_27` |
| `GET /api/v1/admin/orders` | Lists customer orders and line items with optional status filter. | Bearer (`orders:write`) | `status: Optional[str]` | `{ items: Order[] }` | `200` | `test_06`, `test_27` |
| `PATCH /api/v1/admin/orders/{order_id}` | Updates order status enforcing terminal-state transition rules and automatically restoring variant stock when `cancelled` or `returned`. | Bearer (`orders:write`) | `OrderStatusUpdate` | `Order` | `200`, `400`, `404` | `test_06`, `test_25`, `test_27` |
| `GET /api/v1/admin/orders/{order_id}/invoice` | Generates structured Cash-on-Delivery (`COD`) invoice with immutable historical line-item prices and Mus Luxury boutique details. | Bearer (`orders:write`) | `order_id: int` | `OrderInvoice` | `200`, `404` | `test_24` |
| `GET /api/v1/admin/orders/export.csv` | Exports all orders as a UTF-8 CSV spreadsheet. | Bearer (`orders:write`) | None | `text/csv` | `200` | `test_25` |
| `PUT /api/v1/admin/delivery-zones/{wilaya_code}` | Updates a Wilaya's `home_fee_dzd`, `stop_desk_fee_dzd`, availability flags, estimated days, and communes. | Bearer (`content:write`) | `DeliveryZoneUpdateInput` | `{ updated: true, wilaya_code, home_fee_dzd, stop_desk_fee_dzd }` | `200`, `404` | `test_21`, `test_22` |
| `PUT /api/v1/admin/delivery-zones-bulk` | Bulk updates Home and Stop-Desk tariffs across multiple Wilayas. | Bearer (`content:write`) | `BulkWilayaRatesUpdate` | `{ updated_count }` | `200` | `test_22` |
| `GET /api/v1/admin/backups` | Lists backup records and SHA-256 checksums. | Bearer (`backups:write`) | None | `{ items: BackupRecord[] }` | `200` | `test_26` |
| `POST /api/v1/admin/backups` | Writes a compressed `.sql.gz` database dump to `backend/backups/` and records its SHA-256 digest. | Bearer (`backups:write`) | None | `BackupRecord` | `201`, `403` | `test_04`, `test_26` |
| `POST /api/v1/admin/backups/{backup_id}/verify-restore` | Verifies backup SHA-256 digest and executes a non-destructive restoration test in an isolated temporary database. | Bearer (`backups:write`) | `backup_id: int` | `{ backup_id, sha256_verified, isolated_restore_success, restored_counts }` | `200`, `400`, `404` | `test_26` |
| `POST /api/v1/admin/secure-action` | Verifies HMAC-SHA256 request signature (`X-Luxe-Signature`), timestamp freshness (`X-Luxe-Timestamp`), and single-use nonce (`X-Luxe-Nonce`). | Bearer + HMAC-SHA256 | Signed headers + raw body | `{ status: "verified_and_executed", admin_id, nonce }` | `200`, `401` | `test_16`, `test_17` |

| `GET /api/v1/health` | Live database connectivity & Wilaya/Category count healthcheck for Docker/Nginx monitoring. | Public (None) | None | `{ status: "ok", database: "connected", active_wilayas: 69, active_categories }` | `200`, `503` | `test_28_healthcheck_and_static_pages_crud` |
| `GET /api/v1/pages` | Lists all published static content pages (`la-maison`, `faq`, `returns`, `terms`). | Public (None) | None | `{ items: StaticPage[] }` | `200` | `test_28` |
| `GET /api/v1/pages/{slug}` | Retrieves a single published static content page by slug. | Public (None) | `slug: str` | `StaticPage` | `200`, `404` | `test_28` |
| `PUT /api/v1/admin/pages/{slug}` | Creates or updates a static content page and toggles `is_published`. | Bearer (`content:write`) | `StaticPageUpsertInput` | `StaticPage` | `200`, `422` | `test_28` |
| `POST /api/v1/admin/products/{product_id}/images` | Adds an image to a product's gallery and optionally sets it as `main_image_url`. | Bearer (`products:write`) | `ProductImageAddInput` | `ProductImage` | `201`, `404` | `test_29_product_image_gallery_upload_reorder_and_delete` |
| `PUT /api/v1/admin/products/{product_id}/images/reorder` | Reorders a product's gallery images and optionally updates `main_image_url`. | Bearer (`products:write`) | `ProductImageReorderInput` | `{ items: ProductImage[] }` | `200`, `404` | `test_29` |
| `DELETE /api/v1/admin/product-images/{image_id}` | Removes an image from a product's gallery. | Bearer (`products:write`) | `image_id: int` | `{ deleted: true, image_id }` | `200`, `404` | `test_29` |

### Additional WhatsApp Cloud API & Emergency Recovery Routes

| Method | Path | Auth | Permission | Purpose | Status Codes | Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/auth/recovery/status` | Public | None | Inspects WhatsApp Cloud API readiness, sandbox mode, and supported recovery channels | `200` | `test_34` |
| `POST` | `/api/v1/admin/auth/recovery/rotate-emergency-code` | Bearer Token | `settings:write` | Rotates and returns a fresh single-use offline emergency recovery code | `200, 401, 403` | `test_34` |
| `GET` | `/api/v1/webhooks/whatsapp` | Meta Token | `hub.verify_token` | Official Meta WhatsApp Cloud API webhook verification challenge | `200, 403` | `test_35` |
| `POST` | `/api/v1/webhooks/whatsapp` | HMAC-SHA256 | `X-Hub-Signature-256` | Receives and logs WhatsApp message delivery/read status callbacks | `200, 400, 401` | `test_35` |
