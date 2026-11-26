# API endpoints (generated)

Generated from the code by `backend/scripts/generate_api_docs.py`; a test fails when it is out of date,
so do not edit by hand. Request and response shapes: `openapi.json` (same folder). What the main
endpoints do, with examples: `API_INVENTORY.md` and `API_CONTRACT.md`.

179 endpoints. *Access*: public, any staff login, or the permission a staff role must have.

## `backend/app/routers/public.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/store/settings` | public | `get_store_settings` |
| GET | `/api/v1/categories` | public | `list_public_categories` |
| GET | `/api/v1/categories/{slug}` | public | `get_public_category` |
| GET | `/api/v1/brands` | public | `list_public_brands` |
| GET | `/api/v1/delivery-zones` | public | `list_delivery_zones` |
| GET | `/api/v1/products` | public | `list_public_products` |
| GET | `/api/v1/products/{slug}` | public | `get_public_product` |
| POST | `/api/v1/orders` | public | `create_guest_order` |
| PUT | `/api/v1/admin/categories-reorder` | `categories:write` | `admin_reorder_categories` |
| GET | `/uploads/{filename}` | public | `serve_uploaded_image` |
| GET | `/api/v1/store/layout` | public | `get_public_storefront_layout` |
| GET | `/api/v1/orders/track` | public | `track_guest_order` |
| POST | `/api/v1/coupons/validate` | public | `validate_public_coupon` |
| GET | `/api/v1/delivery-zones/calculate` | public | `calculate_delivery_and_order_preview` |
| PUT | `/api/v1/admin/delivery-zones-bulk` | `content:write` | `admin_bulk_update_delivery_zones` |
| GET | `/api/v1/health` | public | `api_healthcheck` |
| GET | `/health` | public | `api_healthcheck` |
| GET | `/api/v1/pos/compat` | public | `pos_compat` |
| GET | `/api/v1/pages` | public | `list_public_static_pages` |
| GET | `/api/v1/pages/{slug}` | public | `get_public_static_page` |
| GET | `/api/v1/ready` | public | `api_readiness_check` |

## `backend/app/routers/auth.py`

| Method | Path | Access | Function |
|---|---|---|---|
| POST | `/api/v1/admin/auth/login` | public | `admin_login` |
| POST | `/api/v1/admin/auth/logout` | staff login | `admin_logout` |
| GET | `/api/v1/admin/auth/setup-status` | public | `get_admin_setup_status` |
| POST | `/api/v1/admin/auth/initialize-owner` | public | `initialize_primary_owner` |
| POST | `/api/v1/admin/secure-action` | staff login | `execute_cryptographically_signed_action` |
| GET | `/api/v1/admin/roles` | `settings:write` | `admin_list_roles` |
| GET | `/api/v1/admin/users` | `settings:write` | `admin_list_users` |
| POST | `/api/v1/admin/users` | `settings:write` | `admin_create_user` |
| PUT | `/api/v1/admin/users/{user_id}` | `settings:write` | `admin_update_user` |
| POST | `/api/v1/admin/users/{user_id}/reset-password` | `settings:write` | `admin_reset_user_password` |

## `backend/app/routers/catalog.py`

| Method | Path | Access | Function |
|---|---|---|---|
| POST | `/api/v1/admin/categories` | `categories:write` | `create_custom_category` |
| POST | `/api/v1/admin/category-attributes` | `categories:write` | `add_category_attribute` |
| DELETE | `/api/v1/admin/category-attributes/{attr_id}` | `categories:write` | `delete_category_attribute` |
| POST | `/api/v1/admin/products` | `products:write` | `create_dynamic_product` |
| POST | `/api/v1/admin/products/{product_id}/generate-variants` | `products:write` | `generate_product_variants_matrix` |
| POST | `/api/v1/admin/products/{product_id}/variants` | `products:write` | `admin_create_variant` |
| PUT | `/api/v1/admin/variants/{variant_id}` | `products:write` | `admin_update_variant` |
| DELETE | `/api/v1/admin/variants/{variant_id}` | `products:write` | `admin_delete_variant` |
| POST | `/api/v1/admin/variants/bulk-update` | `products:write` | `admin_bulk_update_variants` |
| GET | `/api/v1/admin/categories` | `categories:write` or `products:write` | `admin_list_categories` |
| PUT | `/api/v1/admin/category-attributes/{attr_id}` | `categories:write` | `admin_update_category_attribute` |
| POST | `/api/v1/admin/category-attributes/{attr_id}/options` | `categories:write` | `admin_create_attribute_option` |
| PUT | `/api/v1/admin/attribute-options/{option_id}` | `categories:write` | `admin_update_attribute_option` |
| DELETE | `/api/v1/admin/attribute-options/{option_id}` | `categories:write` | `admin_delete_attribute_option` |
| POST | `/api/v1/admin/upload` | `products:write` | `upload_product_image` |
| PUT | `/api/v1/admin/products/{product_id}` | `products:write` | `update_product_with_conflict_detection` |
| POST | `/api/v1/admin/variants/{variant_id}/adjust-stock` | `products:write` | `admin_adjust_variant_stock` |
| GET | `/api/v1/admin/products` | `products:write` | `admin_list_products` |
| DELETE | `/api/v1/admin/products/{product_id}` | `products:write` | `admin_safe_delete_or_archive_product` |
| POST | `/api/v1/admin/products/bulk-status` | `products:write` | `admin_bulk_update_product_status` |
| POST | `/api/v1/admin/brands` | `products:write` | `admin_create_brand` |
| PUT | `/api/v1/admin/categories/{category_id}` | `categories:write` | `admin_update_category` |
| POST | `/api/v1/admin/categories/{category_id}/restore` | `categories:write` | `admin_restore_category` |
| DELETE | `/api/v1/admin/categories/{category_id}` | `categories:write` | `admin_archive_category` |
| POST | `/api/v1/admin/products/{product_id}/images` | `products:write` | `admin_add_product_image` |
| PUT | `/api/v1/admin/products/{product_id}/images/reorder` | `products:write` | `admin_reorder_product_images` |
| DELETE | `/api/v1/admin/product-images/{image_id}` | `products:write` | `admin_delete_product_image` |
| GET | `/api/v1/admin/barcodes/validate` | `products:write` or `pos:read` or `inventory:write` | `admin_validate_barcode` |
| POST | `/api/v1/admin/barcodes/generate` | `products:write` | `admin_generate_barcodes` |
| POST | `/api/v1/admin/variants/{variant_id}/assign-barcode` | `products:write` | `admin_assign_variant_barcode` |
| DELETE | `/api/v1/admin/variants/{variant_id}/barcode` | `products:write` | `admin_clear_variant_barcode` |
| GET | `/api/v1/admin/variants/{variant_id}/label` | `products:write` or `pos:read` or `inventory:write` | `admin_variant_label` |

## `backend/app/routers/content.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/banners` | `content:write` | `admin_list_banners` |
| POST | `/api/v1/admin/banners` | `content:write` | `admin_create_banner` |
| PUT | `/api/v1/admin/banners/{banner_id}` | `content:write` | `admin_update_banner` |
| DELETE | `/api/v1/admin/banners/{banner_id}` | `content:write` | `admin_delete_banner` |
| GET | `/api/v1/admin/homepage-sections` | `content:write` | `admin_list_homepage_sections` |
| PUT | `/api/v1/admin/homepage-sections/{section_key}` | `content:write` | `admin_update_homepage_section` |
| PUT | `/api/v1/admin/settings` | `settings:write` | `admin_update_store_settings` |
| PUT | `/api/v1/admin/delivery-zones/{wilaya_code}` | `content:write` | `admin_update_delivery_zone` |
| PUT | `/api/v1/admin/pages/{slug}` | `content:write` | `admin_upsert_static_page` |
| GET | `/api/v1/admin/communications/outbox` | `orders:write` | `admin_list_communications_outbox` |
| GET | `/api/v1/admin/fiscal/settings` | `settings:write` or `dashboard:read` | `admin_get_fiscal_settings` |
| PUT | `/api/v1/admin/fiscal/settings` | `settings:write` | `admin_update_fiscal_settings` |

## `backend/app/routers/finance.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/suppliers` | `finance:read` | `admin_list_suppliers` |
| GET | `/api/v1/admin/suppliers/{supplier_id}` | `finance:read` | `admin_get_supplier_detail` |
| POST | `/api/v1/admin/suppliers` | `products:write` | `admin_create_supplier` |
| PUT | `/api/v1/admin/suppliers/{supplier_id}` | `products:write` | `admin_update_supplier` |
| DELETE | `/api/v1/admin/suppliers/{supplier_id}` | `products:write` | `admin_delete_supplier` |
| GET | `/api/v1/admin/purchases/{po_id}/document` | `finance:read` | `admin_get_purchase_order_document` |
| GET | `/api/v1/admin/purchases` | `finance:read` | `admin_list_purchases` |
| POST | `/api/v1/admin/purchases` | `products:write` | `admin_create_purchase_order` |
| GET | `/api/v1/admin/purchases/{po_id}/labels` | `dashboard:read` | `admin_purchase_order_labels` |
| POST | `/api/v1/admin/purchases/{po_id}/receive` | `products:write` | `admin_receive_purchase_order` |
| POST | `/api/v1/admin/purchases/{po_id}/pay` | `products:write` | `admin_pay_purchase_order` |
| GET | `/api/v1/admin/expenses` | `finance:read` | `admin_list_expenses` |
| POST | `/api/v1/admin/expenses` | `settings:write` | `admin_create_expense` |
| DELETE | `/api/v1/admin/expenses/{expense_id}` | `settings:write` | `admin_delete_expense` |
| POST | `/api/v1/admin/expenses/{expense_id}/pay` | `settings:write` | `admin_pay_expense` |
| GET | `/api/v1/admin/treasury/summary` | `finance:read` | `admin_get_treasury_summary` |
| GET | `/api/v1/admin/treasury/movements` | `finance:read` | `admin_list_cash_movements` |
| POST | `/api/v1/admin/treasury/movements` | `settings:write` | `admin_record_cash_movement` |
| GET | `/api/v1/admin/accounting/pnl` | `finance:read` | `admin_get_pnl_statement` |
| GET | `/api/v1/admin/accounting/products-profitability` | `finance:read` | `admin_get_products_profitability` |
| GET | `/api/v1/admin/accounting/ledger` | `finance:read` | `admin_list_accounting_ledger` |
| GET | `/api/v1/admin/accounting/export.csv` | `finance:read` | `admin_export_accounting_csv` |

## `backend/app/routers/inventory.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/inventory/movements` | `products:write` | `admin_list_inventory_movements` |
| GET | `/api/v1/admin/inventory/counts` | `inventory:write` | `admin_list_counts` |
| POST | `/api/v1/admin/inventory/counts` | `inventory:write` | `admin_open_count` |
| GET | `/api/v1/admin/inventory/counts/{count_id}` | `inventory:write` | `admin_get_count` |
| PUT | `/api/v1/admin/inventory/counts/{count_id}/lines` | `inventory:write` | `admin_upsert_count_line` |
| DELETE | `/api/v1/admin/inventory/counts/{count_id}/lines/{line_id}` | `inventory:write` | `admin_delete_count_line` |
| POST | `/api/v1/admin/inventory/counts/{count_id}/apply` | `inventory:write` | `admin_apply_count` |
| GET | `/api/v1/admin/inventory/write-off-reasons` | `inventory:write` | `admin_writeoff_reasons` |
| POST | `/api/v1/admin/inventory/write-off` | `inventory:write` | `admin_stock_write_off` |
| GET | `/api/v1/admin/inventory/low-stock` | `inventory:write` | `admin_low_stock_report` |
| POST | `/api/v1/admin/inventory/counts/{count_id}/cancel` | `inventory:write` | `admin_cancel_count` |

## `backend/app/routers/orders.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/orders` | `orders:write` | `list_admin_orders` |
| PATCH | `/api/v1/admin/orders/{order_id}` | `orders:write` | `update_order_status` |
| POST | `/api/v1/admin/coupons` | `content:write` | `create_coupon` |
| GET | `/api/v1/admin/coupons` | `content:write` | `admin_list_coupons` |
| DELETE | `/api/v1/admin/coupons/{coupon_id}` | `content:write` | `admin_deactivate_coupon` |
| GET | `/api/v1/admin/customers` | `orders:write` or `pos:sell` | `admin_list_customers` |
| GET | `/api/v1/admin/orders/export.csv` | `orders:write` | `admin_export_orders_csv` |
| GET | `/api/v1/admin/orders/{order_id}/delivery-note` | `orders:write` | `admin_get_order_delivery_note` |
| GET | `/api/v1/admin/orders/{order_id}/invoice` | `orders:write` | `admin_get_order_invoice` |
| GET | `/api/v1/admin/cod-risk/check` | `orders:write` | `admin_check_phone_cod_risk` |
| GET | `/api/v1/admin/cod-risk/blacklist` | `orders:write` | `admin_list_cod_blacklist` |
| POST | `/api/v1/admin/cod-risk/blacklist` | `orders:write` | `admin_upsert_cod_blacklist` |
| DELETE | `/api/v1/admin/cod-risk/blacklist/{phone}` | `orders:write` | `admin_remove_cod_blacklist` |
| POST | `/api/v1/admin/orders/{order_id}/notify-whatsapp` | `orders:write` | `admin_notify_order_customer_whatsapp` |
| GET | `/api/v1/admin/customers/search` | `orders:write` or `pos:sell` | `admin_search_customers` |
| GET | `/api/v1/admin/customers/{customer_id}` | `orders:write` or `pos:sell` | `admin_get_customer` |
| POST | `/api/v1/admin/customers` | `orders:write` or `pos:sell` | `admin_create_customer` |
| PUT | `/api/v1/admin/customers/{customer_id}` | `orders:write` | `admin_update_customer` |

## `backend/app/routers/pos.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/sync/delta` | `dashboard:read` | `admin_delta_sync` |
| POST | `/api/v1/admin/pos/register/open` | `register:manage` | `pos_open_register` |
| GET | `/api/v1/admin/pos/register/current` | `pos:read` | `pos_current_register` |
| POST | `/api/v1/admin/pos/register/close` | `register:manage` | `pos_close_register` |
| GET | `/api/v1/admin/pos/register/sessions` | `pos:read` | `pos_list_register_sessions` |
| GET | `/api/v1/admin/pos/catalog/snapshot` | `pos:read` | `pos_catalog_snapshot` |
| GET | `/api/v1/admin/pos/catalog/deltas` | `pos:read` | `pos_catalog_deltas` |
| GET | `/api/v1/admin/pos/lookup` | `pos:read` | `pos_lookup` |
| POST | `/api/v1/admin/pos/sales` | `pos:sell` | `pos_create_sale` |
| GET | `/api/v1/admin/pos/sales` | `pos:read` | `pos_list_sales` |
| GET | `/api/v1/admin/pos/sales/{sale_id}` | `pos:read` | `pos_get_sale` |
| GET | `/api/v1/admin/pos/sales/{sale_id}/invoice` | `pos:read` | `pos_get_sale_invoice` |
| POST | `/api/v1/admin/pos/sales/{sale_id}/refund` | `pos:refund` | `pos_refund_sale` |
| GET | `/api/v1/admin/devices` | `devices:read` | `admin_list_devices` |
| POST | `/api/v1/admin/devices` | `devices:write` | `admin_create_device` |
| PUT | `/api/v1/admin/devices/{device_id}` | `devices:write` | `admin_update_device` |
| DELETE | `/api/v1/admin/devices/{device_id}` | `devices:write` | `admin_delete_device` |
| POST | `/api/v1/admin/devices/{device_id}/set-default` | `devices:write` | `admin_set_default_device` |
| POST | `/api/v1/admin/devices/{device_id}/test` | `devices:write` | `admin_test_device` |
| POST | `/api/v1/admin/pos/sync` | `pos:sell` | `pos_offline_sync` |

## `backend/app/routers/reports.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | `dashboard:read` | `admin_dashboard` |
| GET | `/api/v1/admin/reports` | `finance:read` | `admin_analytics_reports` |
| GET | `/api/v1/admin/audit-logs` | `settings:write` | `admin_list_audit_logs` |
| GET | `/api/v1/admin/audit-logs/facets` | `settings:write` | `admin_audit_log_facets` |
| GET | `/api/v1/admin/dashboard/business` | `finance:read` | `admin_business_dashboard` |
| GET | `/api/v1/admin/reports/treasury` | `finance:read` | `admin_treasury_report` |
| GET | `/api/v1/admin/reports/treasury.csv` | `finance:read` | `admin_treasury_report_csv` |
| GET | `/api/v1/admin/reports/inventory-movements` | `inventory:write` | `admin_inventory_movements_report` |
| GET | `/api/v1/admin/reports/inventory-movements.csv` | `inventory:write` | `admin_inventory_movements_report_csv` |
| GET | `/api/v1/admin/reports/expenses` | `finance:read` | `admin_expense_report` |
| GET | `/api/v1/admin/reports/expenses.csv` | `finance:read` | `admin_expense_report_csv` |
| GET | `/api/v1/admin/reports/sales` | `finance:read` | `admin_sales_report` |
| GET | `/api/v1/admin/reports/sales.csv` | `finance:read` | `admin_sales_report_csv` |

## `backend/app/routers/seo.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/seo/render/{kind}/{slug}` | public | `seo_render_page` |
| GET | `/api/v1/seo/sitemap.xml` | public | `seo_sitemap` |

## `backend/app/routers/store.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/store/items` | `products:write` or `inventory:write` | `store_items` |
| POST | `/api/v1/admin/store/items` | `products:write` | `store_quick_add` |
| POST | `/api/v1/admin/store/items/{product_id}/variants` | `products:write` | `store_add_variants` |
| PUT | `/api/v1/admin/store/items/{product_id}` | `products:write` | `store_edit` |
| POST | `/api/v1/admin/store/variants/{variant_id}/receive` | `products:write` or `inventory:write` | `store_receive` |
| POST | `/api/v1/admin/store/items/{product_id}/barcodes` | `products:write` | `store_generate_barcodes` |
| POST | `/api/v1/admin/store/barcodes/missing` | `products:write` | `store_generate_all_missing` |

## `backend/app/routers/system.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/admin/updates/cms/latest.json` | staff login | `cms_update_manifest` |
| GET | `/api/v1/admin/updates/cms/{filename}` | staff login | `cms_update_file` |
| GET | `/api/v1/admin/system/configuration` | `backups:write` | `admin_configuration_status` |
| GET | `/api/v1/admin/system/database` | `backups:write` | `admin_database_status` |
| POST | `/api/v1/admin/system/backups` | `backups:write` | `admin_create_backup` |
| GET | `/api/v1/admin/system/backups/{name}/download` | `backups:write` | `admin_download_backup_for_pc` |
| POST | `/api/v1/admin/system/backups/import` | `backups:write` | `admin_import_backup_from_pc` |
| POST | `/api/v1/admin/system/backups/{name}/restore` | `backups:write` | `admin_restore_backup` |
| POST | `/api/v1/admin/system/reset` | `backups:write` | `admin_reset_database` |

## `backend/app/routers/webhooks.py`

| Method | Path | Access | Function |
|---|---|---|---|
| GET | `/api/v1/webhooks/whatsapp` | public | `verify_whatsapp_webhook` |
| POST | `/api/v1/webhooks/whatsapp` | public | `receive_whatsapp_webhook` |
