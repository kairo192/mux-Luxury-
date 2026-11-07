-- ============================================================================
-- MUS LUXURY (LUXE) E-COMMERCE PLATFORM — NORMALIZED DATABASE SCHEMA
-- Supports PostgreSQL 16 (production) & SQLite 3 (CI / sandbox testing)
-- All 22 required core entities with FK constraints, unique indexes & auditability
-- ============================================================================

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(64) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    phone VARCHAR(32),
    whatsapp_verified INTEGER NOT NULL DEFAULT 0,
    emergency_phone VARCHAR(32),
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL UNIQUE,
    slug VARCHAR(140) NOT NULL UNIQUE,
    logo_url TEXT,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug VARCHAR(140) NOT NULL UNIQUE,
    name_fr VARCHAR(140) NOT NULL,
    name_ar VARCHAR(140) NOT NULL,
    name_en VARCHAR(140) NOT NULL,
    description_fr TEXT,
    description_ar TEXT,
    description_en TEXT,
    image_url TEXT,
    banner_url TEXT,
    parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    show_on_homepage INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS category_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    attr_key VARCHAR(80) NOT NULL,
    label_fr VARCHAR(140) NOT NULL,
    label_ar VARCHAR(140) DEFAULT '',
    label_en VARCHAR(140) DEFAULT '',
    input_type VARCHAR(40) NOT NULL,
    -- Supported input_types:
    -- short_text, long_text, number, price, boolean, single_select,
    -- multi_select, color, size, image, date, measurement, brand, barcode_sku
    unit VARCHAR(32) DEFAULT '',
    is_required INTEGER NOT NULL DEFAULT 0,
    default_value TEXT,
    allow_multiple INTEGER NOT NULL DEFAULT 0,
    is_visible_on_storefront INTEGER NOT NULL DEFAULT 1,
    is_filterable INTEGER NOT NULL DEFAULT 0,
    is_variant_axis INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, attr_key)
);

CREATE TABLE IF NOT EXISTS category_attribute_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attribute_id INTEGER NOT NULL REFERENCES category_attributes(id) ON DELETE CASCADE,
    value VARCHAR(140) NOT NULL,
    label_fr VARCHAR(140) NOT NULL,
    label_ar VARCHAR(140) DEFAULT '',
    label_en VARCHAR(140) DEFAULT '',
    color_hex VARCHAR(16),
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(attribute_id, value)
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    brand_id INTEGER REFERENCES brands(id) ON DELETE SET NULL,
    slug VARCHAR(180) NOT NULL UNIQUE,
    sku VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(100),
    name_fr VARCHAR(220) NOT NULL,
    name_ar VARCHAR(220) DEFAULT '',
    name_en VARCHAR(220) DEFAULT '',
    description_fr TEXT,
    description_ar TEXT,
    description_en TEXT,
    main_image_url TEXT,
    purchase_cost_dzd INTEGER NOT NULL DEFAULT 0, -- PRIVATE: Never exposed on public API
    selling_price_dzd INTEGER NOT NULL CHECK (selling_price_dzd >= 0),
    previous_price_dzd INTEGER CHECK (previous_price_dzd IS NULL OR previous_price_dzd >= 0),
    discount_percent INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'draft', -- draft, published, archived
    is_featured INTEGER NOT NULL DEFAULT 0,
    is_new_arrival INTEGER NOT NULL DEFAULT 0,
    sales_count INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    seo_title VARCHAR(255),
    seo_description TEXT,
    weight_grams INTEGER,
    dimensions_cm VARCHAR(60),
    tags VARCHAR(400),
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES product_variants(id) ON DELETE SET NULL,
    image_url TEXT NOT NULL,
    alt_text VARCHAR(220),
    display_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_attribute_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    attribute_id INTEGER NOT NULL REFERENCES category_attributes(id) ON DELETE RESTRICT,
    value_text TEXT NOT NULL,
    UNIQUE(product_id, attribute_id)
);

CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(120) NOT NULL UNIQUE,
    barcode VARCHAR(120),
    title VARCHAR(180) NOT NULL,
    price_override_dzd INTEGER CHECK (price_override_dzd IS NULL OR price_override_dzd >= 0),
    stock_qty INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    image_url TEXT,
    purchase_cost_dzd INTEGER CHECK (purchase_cost_dzd IS NULL OR purchase_cost_dzd >= 0),
    weight_grams INTEGER CHECK (weight_grams IS NULL OR weight_grams >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 3 CHECK (low_stock_threshold >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    combination_signature VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, combination_signature)
);

CREATE TABLE IF NOT EXISTS variant_attribute_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
    attribute_id INTEGER NOT NULL REFERENCES category_attributes(id) ON DELETE RESTRICT,
    option_value VARCHAR(140) NOT NULL,
    UNIQUE(variant_id, attribute_id)
);

CREATE TABLE IF NOT EXISTS delivery_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wilaya_code VARCHAR(4) NOT NULL UNIQUE,
    wilaya_name_fr VARCHAR(100) NOT NULL,
    wilaya_name_ar VARCHAR(100) NOT NULL,
    communes_json TEXT NOT NULL, -- JSON array of communes
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS delivery_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id) ON DELETE CASCADE,
    delivery_method VARCHAR(32) NOT NULL, -- 'home' or 'stop_desk'
    fee_dzd INTEGER NOT NULL CHECK (fee_dzd >= 0),
    estimated_days VARCHAR(40) NOT NULL DEFAULT '24h - 72h',
    is_supported INTEGER NOT NULL DEFAULT 1,
    UNIQUE(zone_id, delivery_method)
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(160) NOT NULL,
    phone VARCHAR(32) NOT NULL UNIQUE,
    wilaya_code VARCHAR(4) NOT NULL,
    commune VARCHAR(120) NOT NULL,
    address TEXT NOT NULL,
    orders_count INTEGER NOT NULL DEFAULT 0,
    total_spent_dzd INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_reference VARCHAR(40) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    customer_name VARCHAR(160) NOT NULL,
    customer_phone VARCHAR(32) NOT NULL,
    wilaya_code VARCHAR(4) NOT NULL,
    wilaya_name VARCHAR(100) NOT NULL,
    commune VARCHAR(120) NOT NULL,
    delivery_address TEXT NOT NULL,
    delivery_method VARCHAR(32) NOT NULL, -- 'home' or 'stop_desk'
    payment_method VARCHAR(32) NOT NULL DEFAULT 'cod', -- Cash on delivery
    subtotal_dzd INTEGER NOT NULL,
    delivery_fee_dzd INTEGER NOT NULL,
    total_dzd INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    -- Statuses: new, confirmed, preparing, shipped, delivered, cancelled, returned
    customer_notes TEXT,
    internal_notes TEXT, -- PRIVATE: Admin only
    stock_deducted INTEGER NOT NULL DEFAULT 0,
    idempotency_hash VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER NOT NULL REFERENCES product_variants(id),
    product_name VARCHAR(220) NOT NULL,
    variant_title VARCHAR(180) NOT NULL,
    sku VARCHAR(120) NOT NULL,
    unit_price_dzd INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    line_total_dzd INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    admin_user_id INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    change_qty INTEGER NOT NULL,
    previous_qty INTEGER NOT NULL,
    new_qty INTEGER NOT NULL,
    reason VARCHAR(120) NOT NULL, -- order_reserved, order_confirmed, order_cancelled, manual_adjustment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS homepage_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_key VARCHAR(80) NOT NULL UNIQUE,
    title_fr VARCHAR(180) NOT NULL,
    title_ar VARCHAR(180) DEFAULT '',
    title_en VARCHAR(180) DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    config_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS banners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position VARCHAR(60) NOT NULL, -- hero, promo_grid, seasonal
    title_fr VARCHAR(200) NOT NULL,
    title_ar VARCHAR(200) DEFAULT '',
    title_en VARCHAR(200) DEFAULT '',
    subtitle_fr TEXT,
    subtitle_ar TEXT,
    subtitle_en TEXT,
    cta_text_fr VARCHAR(100),
    cta_link VARCHAR(200),
    image_url TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS static_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug VARCHAR(120) NOT NULL UNIQUE,
    title_fr VARCHAR(200) NOT NULL,
    title_ar VARCHAR(200) DEFAULT '',
    title_en VARCHAR(200) DEFAULT '',
    content_fr TEXT NOT NULL,
    content_ar TEXT DEFAULT '',
    content_en TEXT DEFAULT '',
    is_published INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    action VARCHAR(120) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id VARCHAR(80),
    details_json TEXT,
    ip_address VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    backup_type VARCHAR(40) NOT NULL, -- full, database, media
    size_bytes INTEGER NOT NULL,
    sha256_checksum VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'verified',
    triggered_by INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS store_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- PHASE 5-7 EXTENSIONS: WHATSAPP OTP RECOVERY, MFA, COUPONS & SYNC VERSIONING
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    phone VARCHAR(32) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp_cloud_api', -- whatsapp_cloud_api or offline_emergency
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    is_used INTEGER NOT NULL DEFAULT 0,
    expires_at INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(64) NOT NULL UNIQUE,
    discount_type VARCHAR(24) NOT NULL, -- 'percentage' or 'fixed_dzd'
    discount_value INTEGER NOT NULL CHECK (discount_value > 0),
    min_order_dzd INTEGER NOT NULL DEFAULT 0,
    max_discount_dzd INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    starts_at TIMESTAMP,
    ends_at TIMESTAMP,
    usage_limit INTEGER,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 25. Anti-Retour COD: Customer Phone Blacklist & Return-Rate Protection
CREATE TABLE IF NOT EXISTS customer_phone_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_e164 TEXT NOT NULL UNIQUE,
    phone_local TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'Retour abusif / Non-récupération COD',
    is_blocked INTEGER NOT NULL DEFAULT 1,
    blocked_by INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_phone_blacklist_e164 ON customer_phone_blacklist(phone_e164);
CREATE INDEX IF NOT EXISTS idx_phone_blacklist_local ON customer_phone_blacklist(phone_local);

-- 26. ERP: Fournisseurs & Achats (Purchasing & Suppliers)
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company_name TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    tax_id TEXT,
    notes TEXT,
    balance_dzd INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    reference TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft',
    subtotal_dzd INTEGER NOT NULL DEFAULT 0,
    shipping_dzd INTEGER NOT NULL DEFAULT 0,
    tax_dzd INTEGER NOT NULL DEFAULT 0,
    total_cost_dzd INTEGER NOT NULL DEFAULT 0,
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    paid_amount_dzd INTEGER NOT NULL DEFAULT 0,
    expected_date DATE,
    received_at TIMESTAMP,
    notes TEXT,
    created_by INTEGER REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER REFERENCES product_variants(id),
    product_name TEXT NOT NULL,
    variant_title TEXT NOT NULL DEFAULT '',
    sku TEXT NOT NULL,
    quantity_ordered INTEGER NOT NULL CHECK (quantity_ordered > 0),
    quantity_received INTEGER NOT NULL DEFAULT 0,
    unit_cost_dzd INTEGER NOT NULL CHECK (unit_cost_dzd >= 0),
    line_total_dzd INTEGER NOT NULL CHECK (line_total_dzd >= 0)
);

-- 27. ERP: Dépenses & Frais Généraux (Operating Expenses)
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_dzd INTEGER NOT NULL CHECK (amount_dzd > 0),
    expense_date DATE NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'cash',
    recipient TEXT,
    receipt_reference TEXT,
    payment_status TEXT NOT NULL DEFAULT 'paid',
    notes TEXT,
    created_by INTEGER REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 28. ERP: Caisse & Mouvements de Trésorerie (Cash & Bank Operations)
CREATE TABLE IF NOT EXISTS cash_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_type TEXT NOT NULL DEFAULT 'cash_box',
    movement_type TEXT NOT NULL,
    amount_dzd INTEGER NOT NULL CHECK (amount_dzd > 0),
    source_type TEXT NOT NULL,
    source_reference TEXT,
    description TEXT NOT NULL,
    recorded_by INTEGER REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 29. ERP: Grand Livre & Écritures Comptables (Accounting Ledger)
CREATE TABLE IF NOT EXISTS accounting_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_number TEXT NOT NULL,
    journal_code TEXT NOT NULL,
    entry_date DATE NOT NULL,
    account_code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    label TEXT NOT NULL,
    debit_dzd INTEGER NOT NULL DEFAULT 0 CHECK (debit_dzd >= 0),
    credit_dzd INTEGER NOT NULL DEFAULT 0 CHECK (credit_dzd >= 0),
    source_document TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ledger_entry_number ON accounting_ledger(entry_number);
CREATE INDEX IF NOT EXISTS idx_ledger_account_code ON accounting_ledger(account_code);
CREATE INDEX IF NOT EXISTS idx_ledger_entry_date ON accounting_ledger(entry_date);

-- Indexes for High Performance & Query Amplification Protection (Backend Architect & Cloudflare Security Audit)
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_lookup ON products(status, deleted_at, category_id);
CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_brand_id ON products(brand_id);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(selling_price_dzd);
CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);
CREATE INDEX IF NOT EXISTS idx_categories_active ON categories(is_active, deleted_at, display_order);
CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_product_variants_active ON product_variants(product_id, is_active);
CREATE INDEX IF NOT EXISTS idx_pav_product_attr ON product_attribute_values(product_id, attribute_id);
CREATE INDEX IF NOT EXISTS idx_vav_variant_attr ON variant_attribute_values(variant_id, attribute_id);
CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id, display_order);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_idempotency_hash ON orders(idempotency_hash);
CREATE INDEX IF NOT EXISTS idx_orders_customer_phone ON orders(customer_phone);
CREATE INDEX IF NOT EXISTS idx_delivery_rates_zone_id ON delivery_rates(zone_id);
CREATE INDEX IF NOT EXISTS idx_delivery_rates_zone_method ON delivery_rates(zone_id, delivery_method);

-- ============================================================================
-- 30. POS: Cash Register Sessions (per-shift open / close / reconcile)
-- ============================================================================
CREATE TABLE IF NOT EXISTS cash_register_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    register_name VARCHAR(80) NOT NULL DEFAULT 'Caisse principale',
    opened_by_admin_id INTEGER NOT NULL REFERENCES admin_users(id),
    closed_by_admin_id INTEGER REFERENCES admin_users(id),
    opening_float_dzd INTEGER NOT NULL DEFAULT 0 CHECK (opening_float_dzd >= 0),
    expected_cash_dzd INTEGER,          -- opening float + net cash movements, computed at close
    counted_cash_dzd INTEGER,           -- physical cash counted at close
    variance_dzd INTEGER,               -- counted - expected (negative = shortage)
    total_sales_dzd INTEGER NOT NULL DEFAULT 0,
    total_refunds_dzd INTEGER NOT NULL DEFAULT 0,
    sales_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'open', -- open, closed
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_register_sessions_status ON cash_register_sessions(status, opened_at);

-- ============================================================================
-- 31. POS: In-store Sales (immediate payment, distinct from online COD orders)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pos_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_reference VARCHAR(40) NOT NULL UNIQUE,
    register_session_id INTEGER REFERENCES cash_register_sessions(id),
    cashier_admin_id INTEGER NOT NULL REFERENCES admin_users(id),
    customer_id INTEGER REFERENCES customers(id),
    sale_type VARCHAR(16) NOT NULL DEFAULT 'sale', -- sale, refund
    reverses_sale_id INTEGER REFERENCES pos_sales(id), -- original sale when sale_type='refund'
    subtotal_dzd INTEGER NOT NULL DEFAULT 0,
    discount_dzd INTEGER NOT NULL DEFAULT 0,
    tax_dzd INTEGER NOT NULL DEFAULT 0,
    total_dzd INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'completed', -- completed, refunded, partially_refunded, voided
    idempotency_key VARCHAR(128),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pos_sales_idem ON pos_sales(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pos_sales_session ON pos_sales(register_session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_pos_sales_created ON pos_sales(created_at);

CREATE TABLE IF NOT EXISTS pos_sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES pos_sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER NOT NULL REFERENCES product_variants(id),
    product_name VARCHAR(220) NOT NULL,
    variant_title VARCHAR(180) NOT NULL,
    sku VARCHAR(120) NOT NULL,
    unit_price_dzd INTEGER NOT NULL,
    line_discount_dzd INTEGER NOT NULL DEFAULT 0,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    line_total_dzd INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pos_sale_items_sale ON pos_sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_pos_sale_items_variant ON pos_sale_items(variant_id);

CREATE TABLE IF NOT EXISTS pos_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES pos_sales(id) ON DELETE CASCADE,
    method VARCHAR(32) NOT NULL DEFAULT 'cash', -- cash, card, transfer, other
    amount_dzd INTEGER NOT NULL,           -- amount settled by this method (positive)
    tendered_dzd INTEGER,                  -- cash physically handed over (cash only)
    change_dzd INTEGER NOT NULL DEFAULT 0, -- change returned (cash only)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pos_payments_sale ON pos_payments(sale_id);

-- POS sales reuse the shared inventory_movements ledger. The pos_sale_id link column
-- is added idempotently via ensure_schema_columns() in database.py so existing stores
-- upgrade without a destructive rebuild.
