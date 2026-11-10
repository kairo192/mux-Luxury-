// ============================================================================
// MUS LUXURY — local catalog mirror (SQLite).
//
// The Tauri app keeps a copy of the whole product catalog on the shop floor
// so the POS can look up products and ring sales even with no internet. The
// backend feeds this mirror through two endpoints:
//
//   GET /api/v1/admin/pos/catalog/snapshot   -- full dump (first launch)
//   GET /api/v1/admin/pos/catalog/deltas     -- incremental (every ~30 s)
//
// The TypeScript side orchestrates fetching + batching; this Rust module owns
// the on-disk database and exposes:
//
//   mirror_init()                          one-time schema init
//   mirror_upsert_products(rows)           batch upsert
//   mirror_upsert_variants(rows)           batch upsert
//   mirror_mark_synced(cursor)             record last sync timestamp
//   mirror_lookup(term)                    scan or search — same shape as the
//                                          backend's /pos/lookup response
//   mirror_status()                        stats for the UI
//   mirror_clear()                         wipe (for troubleshooting)
//
// Database file lives at <app_data_dir>/pos_mirror.sqlite3, persistent
// across app updates. WAL mode so writes don't block lookups.
// ============================================================================

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{Manager, State};

// -------------------------------------------------- Types ------------------

#[derive(Debug, Clone, Deserialize)]
pub struct MirrorProduct {
    pub id: i64,
    #[serde(default)]
    pub sku: Option<String>,
    #[serde(default)]
    pub name_fr: String,
    #[serde(default)]
    pub name_ar: String,
    #[serde(default)]
    pub name_en: String,
    #[serde(default)]
    pub selling_price_dzd: i64,
    #[serde(default)]
    pub purchase_cost_dzd: i64,
    #[serde(default)]
    pub main_image_url: Option<String>,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub category_id: Option<i64>,
    #[serde(default)]
    pub updated_at: Option<String>,
    #[serde(default)]
    pub deleted: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MirrorVariant {
    pub id: i64,
    pub product_id: i64,
    #[serde(default)]
    pub sku: Option<String>,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub barcode: Option<String>,
    #[serde(default)]
    pub price_override_dzd: Option<i64>,
    #[serde(default)]
    pub stock_qty: i64,
    #[serde(default = "default_true")]
    pub is_active: bool,
    #[serde(default)]
    pub updated_at: Option<String>,
    #[serde(default)]
    pub deleted: bool,
}

fn default_true() -> bool { true }

#[derive(Debug, Clone, Serialize)]
pub struct LookupVariant {
    pub variant_id: i64,
    pub product_id: i64,
    pub sku: String,
    pub barcode: Option<String>,
    pub variant_title: String,
    pub product_name: String,
    pub main_image_url: Option<String>,
    pub unit_price_dzd: i64,
    pub stock_qty: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct LookupProduct {
    pub id: i64,
    pub name_fr: String,
    pub selling_price_dzd: i64,
    pub main_image_url: Option<String>,
    pub status: String,
    pub variants: Vec<LookupVariant>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LookupResponse {
    pub match_type: String,    // "variant" | "product" | "search" | "none"
    #[serde(skip_serializing_if = "Option::is_none")]
    pub variant: Option<LookupVariant>,
    pub results: Vec<LookupProduct>,
    pub source: &'static str,  // always "mirror" here
}

#[derive(Debug, Clone, Serialize)]
pub struct MirrorStatus {
    pub initialized: bool,
    pub product_count: i64,
    pub variant_count: i64,
    pub variants_with_barcode: i64,
    pub last_cursor: Option<String>,
    pub last_synced_at: Option<String>,
    pub db_path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OfflineQueueRow {
    pub client_txn_id: String,
    #[serde(rename = "type")]
    pub item_type: String,
    pub created_at: String,
    pub register_session_id: Option<i64>,
    pub payload_json: String,
    pub total_dzd: i64,
    pub status: String,
    pub error: Option<String>,
    pub reason: Option<String>,
    pub attempts: i64,
    pub sale_reference: Option<String>,
    pub updated_at: String,
}

// -------------------------------------------------- Shared connection -----

pub struct MirrorState {
    conn: Mutex<Option<Connection>>,
    db_path: Mutex<Option<PathBuf>>,
}

impl MirrorState {
    pub fn new() -> Self {
        Self { conn: Mutex::new(None), db_path: Mutex::new(None) }
    }
}

const SCHEMA_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS products (
    id                INTEGER PRIMARY KEY,
    sku               TEXT,
    name_fr           TEXT NOT NULL DEFAULT '',
    name_ar           TEXT NOT NULL DEFAULT '',
    name_en           TEXT NOT NULL DEFAULT '',
    selling_price_dzd INTEGER NOT NULL DEFAULT 0,
    purchase_cost_dzd INTEGER NOT NULL DEFAULT 0,
    main_image_url    TEXT,
    status            TEXT NOT NULL DEFAULT 'draft',
    category_id       INTEGER,
    updated_at        TEXT,
    deleted           INTEGER NOT NULL DEFAULT 0,
    name_normalized   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_products_name_norm ON products(name_normalized);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku) WHERE sku IS NOT NULL;

CREATE TABLE IF NOT EXISTS variants (
    id                 INTEGER PRIMARY KEY,
    product_id         INTEGER NOT NULL,
    sku                TEXT,
    title              TEXT NOT NULL DEFAULT '',
    barcode            TEXT,
    price_override_dzd INTEGER,
    stock_qty          INTEGER NOT NULL DEFAULT 0,
    is_active          INTEGER NOT NULL DEFAULT 1,
    updated_at         TEXT,
    deleted            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_variants_barcode ON variants(barcode) WHERE barcode IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_variants_sku ON variants(sku) WHERE sku IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS offline_sales_queue (
    client_txn_id       TEXT PRIMARY KEY,
    item_type           TEXT NOT NULL DEFAULT 'sale',
    created_at          TEXT NOT NULL,
    register_session_id INTEGER,
    payload_json        TEXT NOT NULL,
    total_dzd           INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'pending',
    error               TEXT,
    reason              TEXT,
    attempts            INTEGER NOT NULL DEFAULT 0,
    sale_reference      TEXT,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offline_sales_queue_status ON offline_sales_queue(status);
"#;

fn normalize(s: &str) -> String {
    // Lowercase + strip common diacritics so a search for "cafe" matches
    // "Café" and "CHÊNE" matches "chene". Lowercase FIRST so an uppercase
    // "É" maps the same way as a lowercase "é".
    let mut out = String::with_capacity(s.len());
    for ch_upper in s.chars() {
        for ch in ch_upper.to_lowercase() {
            let folded = match ch {
                'à'|'â'|'ä'|'á'|'ã' => 'a',
                'ç' => 'c',
                'é'|'è'|'ê'|'ë' => 'e',
                'î'|'ï'|'í'|'ì' => 'i',
                'ô'|'ö'|'ó'|'ò'|'õ' => 'o',
                'û'|'ü'|'ú'|'ù' => 'u',
                'ÿ'|'ý' => 'y',
                c => c,
            };
            out.push(folded);
        }
    }
    out
}

fn open_or_create(path: &PathBuf) -> rusqlite::Result<Connection> {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let conn = Connection::open(path)?;
    conn.pragma_update(None, "journal_mode", "WAL")?;
    conn.pragma_update(None, "synchronous", "NORMAL")?;
    conn.pragma_update(None, "foreign_keys", "ON")?;
    conn.execute_batch(SCHEMA_SQL)?;
    Ok(conn)
}

fn with_conn<F, T, E>(state: &State<'_, MirrorState>, f: F) -> Result<T, String>
where
    F: FnOnce(&mut Connection) -> Result<T, E>,
    E: std::fmt::Display,
{
    let mut guard = state.conn.lock().map_err(|e| e.to_string())?;
    let conn = guard.as_mut().ok_or_else(|| "miroir non initialisé".to_string())?;
    f(conn).map_err(|e| e.to_string())
}

// -------------------------------------------------- Tauri commands --------

#[tauri::command]
pub fn mirror_init(app: tauri::AppHandle, state: State<'_, MirrorState>) -> Result<MirrorStatus, String> {
    let app_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("répertoire de données indisponible: {e}"))?;
    let db_path = app_dir.join("pos_mirror.sqlite3");
    let conn = open_or_create(&db_path).map_err(|e| e.to_string())?;
    {
        let mut c = state.conn.lock().map_err(|e| e.to_string())?;
        *c = Some(conn);
        let mut p = state.db_path.lock().map_err(|e| e.to_string())?;
        *p = Some(db_path.clone());
    }
    mirror_status(state)
}

#[tauri::command]
pub fn mirror_upsert_products(
    state: State<'_, MirrorState>,
    rows: Vec<MirrorProduct>,
) -> Result<usize, String> {
    with_conn(&state, |conn| -> rusqlite::Result<usize> {
        let tx = conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT INTO products
                    (id, sku, name_fr, name_ar, name_en, selling_price_dzd,
                     purchase_cost_dzd, main_image_url, status, category_id,
                     updated_at, deleted, name_normalized)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET
                     sku=excluded.sku,
                     name_fr=excluded.name_fr,
                     name_ar=excluded.name_ar,
                     name_en=excluded.name_en,
                     selling_price_dzd=excluded.selling_price_dzd,
                     purchase_cost_dzd=excluded.purchase_cost_dzd,
                     main_image_url=excluded.main_image_url,
                     status=excluded.status,
                     category_id=excluded.category_id,
                     updated_at=excluded.updated_at,
                     deleted=excluded.deleted,
                     name_normalized=excluded.name_normalized
                ",
            )?;
            for p in &rows {
                let norm = normalize(&format!("{} {} {}", p.name_fr, p.name_en, p.name_ar));
                stmt.execute(params![
                    p.id,
                    p.sku,
                    p.name_fr,
                    p.name_ar,
                    p.name_en,
                    p.selling_price_dzd,
                    p.purchase_cost_dzd,
                    p.main_image_url,
                    p.status,
                    p.category_id,
                    p.updated_at,
                    p.deleted as i64,
                    norm,
                ])?;
            }
        }
        tx.commit()?;
        Ok(rows.len())
    })
}

#[tauri::command]
pub fn mirror_upsert_variants(
    state: State<'_, MirrorState>,
    rows: Vec<MirrorVariant>,
) -> Result<usize, String> {
    with_conn(&state, |conn| -> rusqlite::Result<usize> {
        let tx = conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT INTO variants
                    (id, product_id, sku, title, barcode, price_override_dzd,
                     stock_qty, is_active, updated_at, deleted)
                 VALUES (?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET
                     product_id=excluded.product_id,
                     sku=excluded.sku,
                     title=excluded.title,
                     barcode=excluded.barcode,
                     price_override_dzd=excluded.price_override_dzd,
                     stock_qty=excluded.stock_qty,
                     is_active=excluded.is_active,
                     updated_at=excluded.updated_at,
                     deleted=excluded.deleted
                ",
            )?;
            for v in &rows {
                stmt.execute(params![
                    v.id,
                    v.product_id,
                    v.sku,
                    v.title,
                    v.barcode,
                    v.price_override_dzd,
                    v.stock_qty,
                    v.is_active as i64,
                    v.updated_at,
                    v.deleted as i64,
                ])?;
            }
        }
        tx.commit()?;
        Ok(rows.len())
    })
}

#[tauri::command]
pub fn mirror_mark_synced(
    state: State<'_, MirrorState>,
    cursor: String,
) -> Result<(), String> {
    let now = now_iso();
    with_conn(&state, |conn| -> rusqlite::Result<()> {
        conn.execute(
            "INSERT INTO meta(key,value) VALUES ('last_cursor', ?1)
             ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            params![cursor],
        )?;
        conn.execute(
            "INSERT INTO meta(key,value) VALUES ('last_synced_at', ?1)
             ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            params![now],
        )?;
        Ok(())
    })
}

fn meta_value(conn: &Connection, key: &str) -> rusqlite::Result<Option<String>> {
    conn.query_row(
        "SELECT value FROM meta WHERE key = ?1",
        params![key],
        |r| r.get::<_, String>(0),
    )
    .optional()
}

#[tauri::command]
pub fn mirror_status(state: State<'_, MirrorState>) -> Result<MirrorStatus, String> {
    let db_path = state
        .db_path
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .unwrap_or_default();
    let mut guard = state.conn.lock().map_err(|e| e.to_string())?;
    let conn = match guard.as_mut() {
        Some(c) => c,
        None => return Ok(MirrorStatus {
            initialized: false,
            product_count: 0,
            variant_count: 0,
            variants_with_barcode: 0,
            last_cursor: None,
            last_synced_at: None,
            db_path: db_path.display().to_string(),
        }),
    };
    let product_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM products WHERE deleted = 0", [], |r| r.get(0))
        .unwrap_or(0);
    let variant_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM variants WHERE is_active = 1 AND deleted = 0", [], |r| r.get(0))
        .unwrap_or(0);
    let variants_with_barcode: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM variants WHERE is_active = 1 AND deleted = 0 AND barcode IS NOT NULL AND barcode <> ''",
            [], |r| r.get(0),
        )
        .unwrap_or(0);
    let last_cursor = meta_value(conn, "last_cursor").unwrap_or(None);
    let last_synced_at = meta_value(conn, "last_synced_at").unwrap_or(None);
    Ok(MirrorStatus {
        initialized: true,
        product_count,
        variant_count,
        variants_with_barcode,
        last_cursor,
        last_synced_at,
        db_path: db_path.display().to_string(),
    })
}

#[tauri::command]
pub fn mirror_clear(state: State<'_, MirrorState>) -> Result<(), String> {
    with_conn(&state, |conn| -> rusqlite::Result<()> {
        conn.execute_batch("DELETE FROM variants; DELETE FROM products; DELETE FROM meta;")?;
        Ok(())
    })
}

#[tauri::command]
pub fn mirror_lookup(
    state: State<'_, MirrorState>,
    term: String,
) -> Result<LookupResponse, String> {
    let q = term.trim().to_string();
    if q.is_empty() {
        return Ok(LookupResponse {
            match_type: "none".into(),
            variant: None,
            results: vec![],
            source: "mirror",
        });
    }
    with_conn(&state, |conn| -> rusqlite::Result<LookupResponse> {
        // 1. Exact variant barcode OR SKU → one variant
        let variant = conn
            .query_row(
                "SELECT v.id, v.product_id, v.sku, v.barcode, v.title, v.stock_qty,
                        v.price_override_dzd,
                        p.name_fr, p.selling_price_dzd, p.main_image_url, p.status
                   FROM variants v
                   JOIN products p ON p.id = v.product_id
                  WHERE v.is_active = 1 AND v.deleted = 0
                    AND p.deleted = 0
                    AND (v.barcode = ?1 OR v.sku = ?1)
                  LIMIT 1",
                params![q],
                |r| {
                    let price_override: Option<i64> = r.get(6)?;
                    let product_price: i64 = r.get(8)?;
                    let unit_price = price_override.unwrap_or(product_price);
                    Ok(LookupVariant {
                        variant_id: r.get(0)?,
                        product_id: r.get(1)?,
                        sku: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
                        barcode: r.get(3)?,
                        variant_title: r.get(4)?,
                        stock_qty: r.get(5)?,
                        product_name: r.get(7)?,
                        main_image_url: r.get(9)?,
                        unit_price_dzd: unit_price,
                    })
                },
            )
            .optional()?;
        if let Some(v) = variant {
            return Ok(LookupResponse {
                match_type: "variant".into(),
                variant: Some(v.clone()),
                results: vec![LookupProduct {
                    id: v.product_id,
                    name_fr: v.product_name.clone(),
                    selling_price_dzd: v.unit_price_dzd,
                    main_image_url: v.main_image_url.clone(),
                    status: "published".into(),
                    variants: vec![v],
                }],
                source: "mirror",
            });
        }

        // 2. Exact product SKU
        let prod_by_sku = conn
            .query_row(
                "SELECT id, name_fr, selling_price_dzd, main_image_url, status
                   FROM products
                  WHERE deleted = 0 AND sku = ?1
                  LIMIT 1",
                params![q],
                |r| Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, i64>(2)?,
                    r.get::<_, Option<String>>(3)?,
                    r.get::<_, String>(4)?,
                )),
            )
            .optional()?;
        if let Some((pid, name, price, img, status)) = prod_by_sku {
            let variants = load_variants_for(conn, pid, &name, price)?;
            return Ok(LookupResponse {
                match_type: "product".into(),
                variant: None,
                results: vec![LookupProduct {
                    id: pid, name_fr: name, selling_price_dzd: price,
                    main_image_url: img, status, variants,
                }],
                source: "mirror",
            });
        }

        // 3. Fuzzy name/SKU search (normalized LIKE); cap at 20.
        let normalized = normalize(&q);
        let like = format!("%{}%", normalized);
        let mut stmt = conn.prepare(
            "SELECT id, name_fr, selling_price_dzd, main_image_url, status
               FROM products
              WHERE deleted = 0 AND status = 'published'
                AND (name_normalized LIKE ?1 OR sku = ?2)
              ORDER BY name_fr
              LIMIT 20",
        )?;
        let mut results = vec![];
        let rows = stmt.query_map(params![like, q], |r| {
            Ok((
                r.get::<_, i64>(0)?, r.get::<_, String>(1)?,
                r.get::<_, i64>(2)?, r.get::<_, Option<String>>(3)?,
                r.get::<_, String>(4)?,
            ))
        })?;
        for row in rows {
            let (pid, name, price, img, status) = row?;
            let variants = load_variants_for(conn, pid, &name, price)?;
            results.push(LookupProduct {
                id: pid, name_fr: name, selling_price_dzd: price,
                main_image_url: img, status, variants,
            });
        }
        Ok(LookupResponse {
            match_type: if results.is_empty() { "none".into() } else { "search".into() },
            variant: None,
            results,
            source: "mirror",
        })
    })
}

fn load_variants_for(
    conn: &Connection,
    product_id: i64,
    product_name: &str,
    product_price: i64,
) -> rusqlite::Result<Vec<LookupVariant>> {
    let mut stmt = conn.prepare(
        "SELECT id, sku, barcode, title, price_override_dzd, stock_qty
           FROM variants
          WHERE product_id = ?1 AND is_active = 1 AND deleted = 0
          ORDER BY id",
    )?;
    let rows = stmt.query_map(params![product_id], |r| {
        let price_override: Option<i64> = r.get(4)?;
        Ok(LookupVariant {
            variant_id: r.get(0)?,
            product_id,
            sku: r.get::<_, Option<String>>(1)?.unwrap_or_default(),
            barcode: r.get(2)?,
            variant_title: r.get(3)?,
            stock_qty: r.get(5)?,
            product_name: product_name.to_string(),
            main_image_url: None,
            unit_price_dzd: price_override.unwrap_or(product_price),
        })
    })?;
    rows.collect()
}

fn now_iso() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    // ISO-8601 Z (UTC). We don't need subsecond precision here.
    let (y, m, d) = date_from_days((secs / 86400) as i64);
    let rem = (secs.rem_euclid(86400)) as u32;
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y, m, d, rem / 3600, (rem / 60) % 60, rem % 60
    )
}

#[tauri::command]
pub fn pos_queue_enqueue(
    state: State<'_, MirrorState>,
    item: OfflineQueueRow,
) -> Result<String, String> {
    with_conn(&state, |conn| -> rusqlite::Result<String> {
        conn.execute(
            "INSERT INTO offline_sales_queue
                (client_txn_id, item_type, created_at, register_session_id, payload_json,
                 total_dzd, status, error, reason, attempts, sale_reference, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
             ON CONFLICT(client_txn_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                total_dzd = excluded.total_dzd,
                status = excluded.status,
                error = excluded.error,
                reason = excluded.reason,
                attempts = excluded.attempts,
                sale_reference = excluded.sale_reference,
                updated_at = excluded.updated_at",
            params![
                item.client_txn_id,
                item.item_type,
                item.created_at,
                item.register_session_id,
                item.payload_json,
                item.total_dzd,
                item.status,
                item.error,
                item.reason,
                item.attempts,
                item.sale_reference,
                item.updated_at,
            ],
        )?;
        Ok(item.client_txn_id)
    })
}

#[tauri::command]
pub fn pos_queue_list(state: State<'_, MirrorState>) -> Result<Vec<OfflineQueueRow>, String> {
    with_conn(&state, |conn| -> rusqlite::Result<Vec<OfflineQueueRow>> {
        let mut stmt = conn.prepare(
            "SELECT client_txn_id, item_type, created_at, register_session_id,
                    payload_json, total_dzd, status, error, reason, attempts,
                    sale_reference, updated_at
             FROM offline_sales_queue
             ORDER BY created_at ASC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(OfflineQueueRow {
                client_txn_id: row.get(0)?,
                item_type: row.get(1)?,
                created_at: row.get(2)?,
                register_session_id: row.get(3)?,
                payload_json: row.get(4)?,
                total_dzd: row.get(5)?,
                status: row.get(6)?,
                error: row.get(7)?,
                reason: row.get(8)?,
                attempts: row.get(9)?,
                sale_reference: row.get(10)?,
                updated_at: row.get(11)?,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    })
}

#[tauri::command]
pub fn pos_queue_upsert_batch(
    state: State<'_, MirrorState>,
    items: Vec<OfflineQueueRow>,
) -> Result<usize, String> {
    with_conn(&state, |conn| -> rusqlite::Result<usize> {
        let tx = conn.transaction()?;
        let mut count = 0;
        {
            let mut stmt = tx.prepare(
                "INSERT INTO offline_sales_queue
                    (client_txn_id, item_type, created_at, register_session_id, payload_json,
                     total_dzd, status, error, reason, attempts, sale_reference, updated_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
                 ON CONFLICT(client_txn_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    total_dzd = excluded.total_dzd,
                    status = excluded.status,
                    error = excluded.error,
                    reason = excluded.reason,
                    attempts = excluded.attempts,
                    sale_reference = excluded.sale_reference,
                    updated_at = excluded.updated_at",
            )?;
            for item in items {
                stmt.execute(params![
                    item.client_txn_id,
                    item.item_type,
                    item.created_at,
                    item.register_session_id,
                    item.payload_json,
                    item.total_dzd,
                    item.status,
                    item.error,
                    item.reason,
                    item.attempts,
                    item.sale_reference,
                    item.updated_at,
                ])?;
                count += 1;
            }
        }
        tx.commit()?;
        Ok(count)
    })
}

#[tauri::command]
pub fn pos_queue_remove(
    state: State<'_, MirrorState>,
    client_txn_id: String,
) -> Result<bool, String> {
    with_conn(&state, |conn| -> rusqlite::Result<bool> {
        let affected = conn.execute(
            "DELETE FROM offline_sales_queue WHERE client_txn_id = ?1",
            params![client_txn_id],
        )?;
        Ok(affected > 0)
    })
}

#[tauri::command]
pub fn pos_queue_clear_synced(state: State<'_, MirrorState>) -> Result<usize, String> {
    with_conn(&state, |conn| -> rusqlite::Result<usize> {
        let affected = conn.execute(
            "DELETE FROM offline_sales_queue WHERE status = 'synced'",
            [],
        )?;
        Ok(affected)
    })
}

fn date_from_days(mut n: i64) -> (i32, u32, u32) {
    n += 719468;
    let era = if n >= 0 { n / 146097 } else { (n - 146096) / 146097 };
    let doe = (n - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    let y = if m <= 2 { y + 1 } else { y };
    (y as i32, m, d)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn in_memory() -> Connection {
        let c = Connection::open_in_memory().unwrap();
        c.execute_batch(SCHEMA_SQL).unwrap();
        c
    }

    #[test]
    fn normalize_strips_accents_and_lowercases() {
        assert_eq!(normalize("Café"), "cafe");
        assert_eq!(normalize("CHÊNE"), "chene");
        assert_eq!(normalize("naïve Noël"), "naive noel");
    }

    #[test]
    fn schema_creates_tables_and_indexes() {
        let c = in_memory();
        let tables: Vec<String> = c
            .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").unwrap()
            .query_map([], |r| r.get(0)).unwrap()
            .collect::<rusqlite::Result<_>>().unwrap();
        assert!(tables.contains(&"products".to_string()));
        assert!(tables.contains(&"variants".to_string()));
        assert!(tables.contains(&"meta".to_string()));
    }

    #[test]
    fn date_from_days_known_value() {
        assert_eq!(date_from_days(20766), (2026, 11, 9));
    }
}
