# HANDOFF — Mus Luxury (LUXE)

**To:** Antigravity (the AI running on the user's local Windows machine)
**From:** Claude Code (cloud session, branch `feat/pos-core-cash-register-18lsk6`)
**Date:** 2026-11-11 (section 0 is new; sections 1+ are from 2026-11-09)
**Last commit on cloud branch:** `0e44047` (the cleanup + production .env round) + the i18n foundation that will land in the next push (see `docs/cicd/I18N_AUDIT.md`).

---

## 0o. ONLY WORKING FEATURES (2026-11-12, latest)
- Removed everywhere: Chargily, Yalidine / ZR / Maystro APIs, SMTP, pixels, Google Maps, WhatsApp Cloud sending keys.
  Do not re-add them as "coming soon" keys: build the feature first, then register its keys.
- Kept: COD + manual delivery, `wa.me` messages, WhatsApp webhook (2 optional keys), S3 off-site backup.

## 0n. CONFIGURATION — backend/app/settings.py IS THE LIST OF .env KEYS (2026-11-12)
- New key: add it to `SETTINGS` (with help/secret/required), read it with `app_settings.get(...)`, then
  `python3 -m app.settings templates`. CI fails otherwise (`test_settings_registry.py`).
- Only keys of working features. Old leftover keys are reported as "not used — can be deleted".
- `GET /api/v1/admin/system/configuration` (owner) and the deploy check never return values. Guide: docs/CONFIGURATION.md.

## 0m. CMS ARCHITECTURE — READ apps/desktop-cms/ARCHITECTURE.md FIRST (2026-11-12)
- App.tsx is the shell only (3047 → 1682 lines). Screens live in `pages/`: Dashboard, Products, Inventory,
  Orders and Contenu were moved out (`DashboardPage`, `ProductsPage`, `InventoryPage`, `OrdersPage`,
  `ContentSettingsPage`). New screens follow ARCHITECTURE.md §5. Keep the keep-alive containers in App.tsx.
- `ContentSettingsPage` loads/saves its own data; the others get shared data as typed props.

## 0l. DEPLOY REHEARSAL FIXES (2026-11-12)
Details: WORK_SUMMARY §25.
- Never `source`/`.` the production `.env`: use `infrastructure/scripts/env-file.sh` (`luxe_load_env FILE`, or
  `bash env-file.sh FILE cmd…`). Nightly chain = `infrastructure/backups/nightly_backup.sh`.
- Every `docker compose` command must run under `COMPOSE_PROJECT_NAME` from `shared/.env`
  (`compose-project.sh`: `luxe_ensure_compose_project`, `luxe_check_db_volume`). Do not add a top-level `name:`
  to docker-compose.yml — it would override the detected name of an existing server.
- Rollback = `up -d --build`. Backend image has no compiler: keep dependencies wheel-only.

## 0k. ARABIC SHOP ON A PHONE (2026-11-12)
Details: WORK_SUMMARY §23. Storefront: `L(fr, ar, en)` for any visible text, `wilayaName(w)`, `ltr(text)` around
anything left-to-right inside Arabic; `formatDZD()` already isolates prices in Arabic — never build "… DA" by hand.
Fixed texts in the page: add `data-t-ar` / `data-t-en` (swapped by setLanguage). Information pages come from the CMS per language (`translate_untouched_starter_pages` in seed.py repaired old French copies). Only the offline fallback STATIC_PAGES_CONTENT is still French.

## 0j. HTTPS RENEWAL + HEALTH CHECK (2026-11-12)
Details: WORK_SUMMARY §22, VPS_DEPLOYMENT §6–7.
- `infrastructure/scripts/certificates.sh setup|deploy-hook|check`; nginx port-80 server serves
  `/.well-known/acme-challenge/` from `/var/www/certbot` (compose mount `ACME_WEBROOT`). Do not remove.
- `health-check.sh` = HTTPS through local nginx (`--resolve`, `--noproxy`); `CURL_CA` only for tests.
- CI runs shellcheck on `infrastructure/**/*.sh`.

## 0i. NO INVENTED DELIVERY PRICES, HOURS FROM THE CMS (2026-11-12)
Details: WORK_SUMMARY §21.
- Storefront `WILAYAS` fallback = geography only. Use `feesKnown()`, `deliveryFeeFor()` (0 while unknown) and
  `deliveryFeeText()` for any price shown; never read `home_fee`/`desk_fee` directly in templates.
- Settings `opening_hours` (lines « Jour (note) : horaires », rendered by `applyOpeningHours()` into
  `#store-hours-list`) and `store_maps_url` (links marked `data-maps-link`); CMS fields in Contenu & Bannières.
- `_LightGZipMiddleware` in main.py replaces Starlette's GZipMiddleware (level 6, closes the compressor, skips
  `/download`).

## 0h. REAL SERVER SIZE + BACKUPS ON THE OWNER'S PC (2026-11-12)
VPS = 1 vCPU, 2 GB RAM, **40 GB** disk (confirmed by the owner). Details: WORK_SUMMARY §20, VPS_DEPLOYMENT.md.
- Backup script: photos only when changed (`.media_manifest`), `BACKUP_MEDIA_KEEP=3`, `BACKUP_MIN_FREE_PCT=15`.
- `backup_engine.write_snapshot()` writes format `luxe-backup/2` (JSON Lines, restore order) and `restore_backup()` streams it after `_scan_v2()` validation; v1 files still load. Never go back to whole-file JSON in memory.
- PC copies: `GET /admin/system/backups/{name}/download` (owner, `.enc` only, audited),
  `POST /admin/system/backups/import`; Tauri commands `backup_copy_save/list/read` (src-tauri/src/backup_copies.rs),
  `utils/backupCopies.ts`, auto-copy effect in App.tsx (owner, desktop app).
- Uploads: `_optimize_product_image` (Pillow, 1600 px, EXIF stripped), 15 MB limit; nginx 16M on /admin/upload,
  110M on /backups/import, 6M elsewhere.
- `public_catalog_cache` middleware (5 s, cleared by any POST/PUT/PATCH/DELETE under /api/v1/).
- On Windows: build the desktop app once to check the new Rust module (`cargo check` passed here; linking needs
  libcups only on Linux).

## 0g. BROWSER TEST SUITE + CLEAN CODE (2026-11-12)
- `e2e/` (Playwright 1.63): `npm run test:e2e` (or `npm --prefix e2e test`). Own stack on ports
  18000/11420/15173, fresh production-mode DB (`E2E_DATABASE_URL` for PostgreSQL). Must stay green; CI job `e2e`.
  When you change a screen, run it; when you add a screen, `06-cms-all-screens` covers it automatically.
- CMS `tsconfig`: `noUnusedLocals` / `noUnusedParameters` are ON — `npm run build` fails on dead code.
- `npm run lint` = ruff + tsc. Server setting `LOGIN_ATTEMPTS_PER_MINUTE` (default 5, capped at 30; tests use 30; nginx keeps 5/min in front).
- Specs moved to `docs/specs/` (e.g. `docs/specs/claude code.md`); Windows helpers in `scripts/windows/`.

## 0f. BUSINESS CONNECTED END TO END (2026-11-12)
Details: `docs/WORK_SUMMARY_2026-11-11.md` §18. Keep these true (guarded by `tests/test_business_flow.py`):
- Receiving a purchase: landed unit cost (shipping+tax spread by line value) in the PMP of the product and
  of a variant that has its own cost.
- Register close: variance → `cash_movements` source `register_variance`.
- P&L / Analytique: net = gross − all expenses − `_stock_losses_dzd()` (movements `writeoff_*` except
  `writeoff_return_to_supplier`, and `physical_count_reconcile`, at cost).
- `orders.coupon_code` / `orders.discount_dzd` (via `_ADDITIVE_COLUMNS`); cancel → coupon usage −1.
- Documents use `_boutique_info_from_settings()` (fiscal settings, then store settings).
- `seed_initial_data()` runs `migration_runner.run()` at every start.
- Server messages shown to people are French. CMS screens/data loads are gated by `canOpenTab` / role perms.

## 0e. EVERY CMS SCREEN TESTED ONE BY ONE (2026-11-11)
Commits `a54a23f` → `e61c4a8`, details in `docs/WORK_SUMMARY_2026-11-11.md` §17. Rules now in force:
- **Permissions**: `finance:read` (owner, Administrateur) guards every money endpoint; permissions,
  role and `is_active` are read from the DB on each request (`get_current_admin`), not from the token.
- **Time**: DB stores UTC text without zone. Server: `SHOP_TZ` / `_shop_today()` / `_utc_range_for_days()`
  (half-open `created_at >= ? AND created_at < ?`) / `_shop_day_of()` (group by `substr(created_at,1,13)`
  then fold) / `_csv_date()` in shop time. PostgreSQL sessions use `timezone=UTC`. CMS: always
  `serverDate()` / `formatServerDateTime()` / `localDateIso()` from `utils/serverDate.ts`, never
  `new Date(server_string)` or `toISOString().slice(0,10)`.
- **Audit names**: add every new `log_audit` action/entity to `_AUDIT_ACTION_FR` / `_AUDIT_ENTITY_FR`
  (a test fails otherwise).
- **Accounting**: sales = orders not cancelled/returned + POS sales − refunds; charges = all expenses
  (paid or pending). `accounting_ledger` holds purchases/expenses only. CSV: `/admin/accounting/export.csv?part=`.
- **Devices**: printer tests run in the desktop app (`testPrint` / `testPrintLabel`) and report
  `{success, error}`; the server never probes private LAN addresses as a failure.
- **Products** with history are archived, never hard-deleted; treasury rows are written for POS
  sales/refunds, COD delivered/returned, expenses, purchases and manual entries.
- No hard-coded `127.0.0.1` in CMS calls: use `getApiBaseUrl()` / `adminFetch`.

## 0d. SHOP CONTENT FROM CMS, NO FAKE DATA (2026-11-11)
- Storefront home is driven by `GET /api/v1/store/layout` (settings + ALL homepage_sections with
  `is_active` + active banners). Fixed promo cards / hero texts / contacts were removed from
  `apps/storefront/index.html`: see `renderHero()`, `renderPromos()`, `renderFooterCollections()`,
  `applyStoreContacts()`, `setting()`, `waNumber()`. Do NOT re-add hardcoded phone numbers or promos.
- Backend: `_free_delivery_threshold()` applied in order creation + `/delivery-zones/calculate`
  (`free_delivery_applied`); `PUT /admin/banners/{id}`; `GET /admin/homepage-sections` (standard
  blocks, auto-created on PUT); dashboard `revenue_by_day`, `active_variants`,
  `low_stock_only_variants` (stock counts exclude archived/deleted products); `/ready` = 69 zones
  exist + storage writable (inactive wilayas allowed).
- CMS: `components/HomepageContentPanel.tsx` (top of the Contenu tab); settings form has
  `instagram_url` / `tiktok_url`; static pages edit FR/AR/EN (`pageDraft`); `settingsDirtyRef` /
  `pageDirtyRef` stop background refresh from wiping unsaved typing. `RevenueTrendChart` takes
  `byDay` only (no estimates); `OrderStatusDistributionChart` computes its own total;
  `InventoryHealthWidget` takes `totalVariants`.
- `seed.remove_legacy_demo_content()`: ONE-TIME (marker `system_legacy_demo_cleanup_v1` in
  store_settings), skipped in test/demo mode, audited (`remove_legacy_demo_content`). Operator check:
  `docker compose exec api python -m app.cleanup_demo --dry-run`.
- PostgreSQL parity (database.py): rows reshaped like SQLite (`sqlite_shaped_dict_row`: datetime →
  text, Decimal → int/float); `_translate_sqlite_functions` (substr/datetime/scalar MAX);
  `TABLES_WITHOUT_ID` (no RETURNING id). backup_engine `_fk_parents` aliases columns. ALWAYS run the
  suite on PostgreSQL too (CI job "PostgreSQL 16"); write SQL valid on both (no bare GROUP BY with
  non-aggregated columns). Tests: `tests/test_pg_compat.py`.
- Tests: `backend/tests/test_storefront_content.py`.
- Round 16: "sale" = online order NOT IN ('cancelled','returned') everywhere money is counted;
  `/admin/accounting/pnl` + `/products-profitability` include POS sales − refunds and use
  `_UNIT_COST_SQL`; gross profit = revenue incl. delivery − COGS (same as dashboard/business).
  No owner "emergency code" any more; recovery = `python -m app.admin_cli reset-password` (VPS).
  `utils/movementReasons.ts` = labels for inventory_movements.reason.

## 0c. CMS PRODUCT EDITOR (2026-11-11)
- `mediaUrl()` / `storefrontBaseUrl()` / `PLACEHOLDER_IMG` in `src/api/adminClient.ts`: ALWAYS wrap stored
  image paths with `mediaUrl()` in the CMS (`/uploads` → API host, `/assets` → shop host).
- `components/StorefrontPreview.tsx` replaces `LiveProductCardPreview` (deleted): card + product page,
  FR/AR/EN, readiness checklist, copy-link. Keep it visually in sync with `apps/storefront/index.html`.
- `VariantManager`: `image_url` per variant + photo picker (`availableImages` prop); saved via create
  payload or `updateVariant` (`""` clears).
- Backend: variants are no longer created with a copy of the main photo (NULL = follow product photo);
  migration `004_variant_image_follows_product.sql`. `seo.py` uses `seo_title`/`seo_description`.
- Storefront: `prodDesc()/catDesc()` per language, PDP buttons via `I18N`, language saved in
  `localStorage.luxe_store_lang`.

## 0b. STOREFRONT STEP 2 (2026-11-11, latest)
- Real paths `/produit/<slug>`, `/categorie/<slug>` (`currentRouteHash()` maps them to the old internal
  routes; `navigateTo('#/category/x')` now pushes `/categorie/x`; `popstate`+`hashchange` → `onRouteEvent`, deduped).
- nginx → `GET /api/v1/seo/render/{produit|categorie}/{slug}` and `/sitemap.xml` (`backend/app/seo.py`):
  replaces `<!-- SEO:START -->…<!-- SEO:END -->` in the shop's index.html (fetched from
  `STOREFRONT_INTERNAL_URL`, default `http://storefront`, cached 60 s). **Keep those markers in index.html.**
  The API middleware does not add its CSP on `/api/v1/seo/*` (nginx sets the storefront CSP).
- Dev: vite proxies those paths to :8000; start the API with `STOREFRONT_INTERNAL_URL=http://localhost:5173`.
- Checkout: one `state.checkoutIdemKey` per order, `state.placingOrder` guard, never invents an order number.
- `apps/storefront/src/` now only holds `index.css` + `vite-env.d.ts`; React deps removed. Tests retargeted to index.html.

## 0a. STOREFRONT STEP 1 (2026-11-11, latest)
`apps/storefront/index.html` (the live shop; `src/App.tsx` is NOT loaded):
- Server data is escaped ONCE on arrival (`escapeDeep` in `syncStorefrontWithBackend`). Templates may
  interpolate catalog fields directly; use `decodeHtml()` before `textContent`/`value`, `jsArg(v)` for
  values inside inline handlers, `safeHex()` for colours. Wilayas are NOT pre-escaped: escape at render.
- `fetchAllProducts()` pages through `/products` (50/page). Polling: 60 s (`syncIfStale`), not 4 s.
- Product route `#/produit/<slug>` (`openProductBySlug`, `pdpReturnHash`, `pdpPushed`); Back closes the modal.
- No fake ratings/swatches; `PLACEHOLDER_IMG` = `/assets/placeholder_product.svg`.
- Tests: suite unchanged except test_57 still looks for the literal `escapeHtml(msg)` in `showToast` (kept).

## 0. NEWEST ROUND (2026-11-11, later): database admin, backups fixed, demo data gone

**Read `docs/OPERATIONS_GUIDE.md` (owner-facing) first.** Summary for you:

- **"Deleted categories come back after reload"**: the CMS read `/categories` (the public, cacheable
  endpoint, max-age 300). Now `adminFetch` uses `cache: "no-store"` for every call;
  `listCategories(includeArchived)` hits `/admin/categories`; public cache is 30 s. Archived
  categories have an **Archivées** tab + `POST /admin/categories/{id}/restore`.
- **Demo data**: `seed.py` seeds the demo catalog only when `APP_ENV=test` or
  `LUXE_SEED_DEMO_PRODUCTS=1` (development PCs start empty now). **`backend/scripts/restore_demo_products.py`
  was deleted.** On an empty shop it wiped `admin_users`/roles and re-seeded the demo. Please don't
  re-create it. `reset_fresh_store.py` is now a wrapper around the engine below.
- **New `backend/app/backup_engine.py` + `backup_cli.py`**: portable encrypted snapshots
  (AES-256-GCM, key from `BACKUP_ENCRYPTION_KEY`), restore and reset in ONE transaction, safety
  backup first, SQLite + PostgreSQL (tested on real PG 16, plus PC→VPS cross-restore). Owner-only
  endpoints: `GET /admin/system/database`, `POST /admin/system/backups`,
  `POST /admin/system/backups/{name}/restore` (`confirm: "RESTAURER"` + password),
  `POST /admin/system/reset` (`confirm: "EFFACER"` + password). There is deliberately NO download
  endpoint. UI: `components/DatabasePanel.tsx` at the top of the `backups` tab.
- **POS offline mirror**: snapshot/deltas now return `catalog_epoch`; reset/restore changes it, and
  `posMirrorSync.ts` clears + re-snapshots the mirror when it changes (deltas can't express
  hard deletes). `syncCatalog(true)` also clears first.
- **VPS backup chain was broken** (it would have written EMPTY backups: host cron had no pg_dump,
  fell back to SQLite). Now `backup_postgres_and_media.sh` uses `docker exec luxe_postgres pg_dump
  --clean --if-exists`, archives photos from `luxe_api`, adds a CMS snapshot, refuses an empty dump,
  and writes `last_backup_status.json`. `restore_backup.sh`, `verify_backup.sh` (temp DB inside the
  container) and `upload_to_offsite.sh` (uploads exactly the manifest's set) are Docker-aware too.
  Backup dir owned by the deploy user; cron logs the whole chain; `release-deploy.sh` runs the
  NEW release's backup script. `vps_nightly_backup.sh` just delegates.
- `infrastructure/scripts/setup-github-secrets.ps1`: generates the Tauri signing key + deploy SSH key
  on the owner's PC and sets the GitHub secrets/variables via `gh`. (Not executed in the cloud: no
  PowerShell there. If you can, dry-run it on Windows.)
- Tests: new `backend/tests/test_backup_engine.py` (7 tests). Suite: 249 run, only the 4
  `@babel/core` container failures (they pass with a TS compiler).

---

## 0. LATEST ROUND (2026-11-11): notifications, Windows alerts, auto-update

Pushed on `feat/pos-core-cash-register-18lsk6`. Pull it before touching any of these files:

- **Toasts**: `src/components/ToastStack.tsx`. They sit in the bottom corner (bottom-left in Arabic), newest nearest the corner,
  4 at most, duplicates merge into ×N. Hovering pauses the timer, and so does a hidden window. The CSS animation of the progress bar
  is the dismiss timer (`index.css` → `.luxe-toast*`). Errors and warnings that open a message box
  are **not** toasted a second time.
- **Message boxes**: still in `App.tsx` `renderClientNotificationCenter()`. They are now a **queue**
  (`messageQueue`), with a "1 sur N" counter, Suivant / Tout fermer, and Enter/Esc to close. The test contract is
  intact: `role="dialog"`, `aria-modal="true"`, `"Compris (Fermer)"`, and the `active-confirm-title`
  confirm. The confirm dialog is now z-[80], above everything.
- **Bell + history**: `src/components/NotificationBell.tsx` + `src/utils/notificationCenter.ts`
  (history in sessionStorage, plus the "Notifications Windows" switch in localStorage `luxe_cms_os_notifications`).
- **Windows notifications**: Rust `src-tauri/src/app_services.rs` → `os_notify` (only shown when the
  window is not focused, and flashes the taskbar) + `app_focus_main_window`, through `tauri-plugin-notification`.
  To raise one from TS: `notifyClient({ ..., os: true })`.
- **New online orders**: `App.tsx` polls `listOrders("new")` every 45 s. The first poll only seeds.
  Later polls raise a toast with a **Voir** button and a Windows alert, then refresh the Orders list.
- **POS background sync** (`PosPage.tsx` `runSync(silent)`) now reports created/conflict sales.
- **Auto-update (crash-safe)**: `app_services.rs` `updater_status/check/install`. The updater
  plugin is registered **only if** the binary was compiled with `LUXE_UPDATER_PUBKEY`. Without it, the app
  runs normally with the updater off, so the startup crash you fixed in `500116a` cannot come back.
  `tauri.conf.json` has `plugins.updater` (endpoint + empty pubkey placeholder; the Builder overrides it).
  UI: the version chip in the header opens `UpdateDialog.tsx`. Checks run 15 s after start, then every 4 h.
  Before installing it warns about unsynced offline sales.
- **CI**: `build-desktop-cms.yml` signs only when the secret `TAURI_SIGNING_PRIVATE_KEY` and the **variable**
  `TAURI_UPDATER_PUBKEY` both exist. The version comes from the tag, and `scripts/make-latest-json.mjs` writes
  `latest.json`. See `docs/DESKTOP_CMS_RELEASE_GUIDE.md` §2–4.
- Verified: `cargo check` OK, `tsc` + `vite build` OK, a Playwright run of every behaviour above (0 console errors),
  and backend suite 238/242. The 4 failures are only the missing `@babel/core` in the cloud container; they
  pass with a TS compiler.
- **Do NOT** re-add `@tauri-apps/plugin-updater` JS calls. Everything goes through the Rust commands.

---

## 1. Read this first

- The user asked me to produce a production `.env` and continue cleanup. That's what the diff on this branch does. **I did not push this work yet**; the next commit (`§5 below`) is yours to amend or extend before you push.
- You are mirroring sections of the full spec (`docs/specs/claude code.md`). I've been working on the operational cleanup lane (CSP, fetch hardening, `window.prompt` removal, offline SQLite catalog mirror, test pruning, `.env` generator). You are the owner of the feature lane.
- My cloud branch is `feat/pos-core-cash-register-18lsk6`; your desktop branch is `feat/pos-core-cash-register`. **Do not merge them automatically** — we're both committing and the user wants manual control over which branch becomes the PR.

---

## 2. What I just did (uncommitted, still staged on the cloud branch)

Context: the owner explicitly asked to strip the WhatsApp admin password recovery flow and the admin-facing backup UI, to clear the demo catalog from a production first-boot, and to produce a ready-to-use production `.env`.

### 2.1 Backend (`backend/app/main.py`)

- **Removed endpoints**:
  - `GET  /api/v1/admin/auth/recovery/status`
  - `POST /api/v1/admin/auth/recovery/request`
  - `POST /api/v1/admin/auth/recovery/verify`
  - `POST /api/v1/admin/auth/recovery/rotate-emergency-code`
  - `GET  /api/v1/admin/backups`
  - `POST /api/v1/admin/backups`
  - `POST /api/v1/admin/backups/{id}/verify-restore`
  Each left a short header comment explaining the removal and pointing operators at `backend/scripts/emergency_reset_owner.py` (password reset) and `docs/cicd/ROLLBACK.md` (backup/restore).
- **Kept intact**: the `whatsapp.py` module for customer-facing order notifications + the inbound webhook (`/api/v1/webhooks/whatsapp`).
- **Dead imports removed**: `decrypt_backup_bytes`, `encrypt_backup_bytes`, `dispatch_whatsapp_recovery_otp`, and the `BACKUP_STORAGE_DIR` top-level.

### 2.2 Seed (`backend/app/seed.py`)

- Demo catalog (brands / categories / attributes / products / variants / homepage banners / promo coupons) is now **gated behind** `LUXE_SEED_DEMO_PRODUCTS=1` OR `APP_ENV != "production"`. Production first-boot gives a clean slate:

  ```
  products       0
  categories     0
  brands         0
  coupons        0
  banners        0
  static_pages   4   (legal pages still seed)
  delivery_zones 69  (wilayas are infrastructure, always seed)
  admin_users    0   (owner-init wizard required)
  roles          7
  ```

  Wilayas (section 7) moved back **out** of the demo block — they're infrastructure and must always seed, even on production first-boot. I split the demo content into a `_seed_demo_catalog_content(cur, owner_id)` helper.

### 2.3 CMS (`apps/desktop-cms/src/App.tsx`, `src/api/adminClient.ts`)

- Login screen: "Mot de passe oublié ?" link and the full WhatsApp OTP modal are gone. A short note replaces them: password reset happens via the server CLI.
- Owner-setup form: the "WhatsApp Récupération" input is gone. The surviving "Téléphone propriétaire" input feeds `emergency_phone`. Added a helper line telling the owner that recovery is a server-side operation.
- Workspace: `backups` state, `backups.map` render, `restoreReport` state, `handleTriggerBackup`, `handleVerifyBackupRestore`, `handleRotateEmergencyCode`, `handleRequestRecoveryOtp`, `handlePasswordRecoveryVerify` — all removed. Matching `DesktopCmsApi.*` methods deleted from `adminClient.ts`. Admin-settings section that read `recoveryStatus?.whatsapp_cloud_api_configured` deleted.
- `DesktopCmsApi.initializeOwner`'s `whatsapp_phone` field is now optional — the backend still accepts it, but the UI stops collecting it.

### 2.4 Tests (`backend/tests/test_luxe_api.py`, `test_security_hardening.py`)

- 10 test methods that exercised the removed endpoints are stubbed with a single `self.skipTest("Feature removed: ...")` call citing the owner request + the replacements. Test runner still collects them (useful breadcrumbs); they report as skipped, not as failures.
- One stub left an orphan Python multi-line string (`js_ast_check = """...`) in `test_80`; I deleted the orphan by hand.
- Focused suites `test_catalog_sync` + `test_barcode_scan_loop` + `test_purchase_document` → 14/14 passing.

### 2.5 Production `.env` generator (`backend/scripts/generate_production_env.py`)

- **This is the piece the user explicitly asked for.** Produces a full `.env.production` with cryptographically strong values for `SECRET_KEY`, `CMS_HMAC_SIGNING_SECRET`, `BACKUP_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `ADMIN_INITIAL_PASSWORD`, `ADMIN_EMERGENCY_RECOVERY_CODE`.
- (Superseded 2026-11-12, see 0n/0o: the file is built from `backend/app/settings.py`; provider keys are left empty.)
- Writes to `scratch/production.env` by default, chmod 0600 on POSIX. Prints the critical values on stdout one time so the user can file them in a password manager.
- Usage (from the repo root):

  ```bash
  python3 backend/scripts/generate_production_env.py \
      --domain mus-luxury.com \
      --admin-email admin@mus-luxury.com \
      --admin-whatsapp +213655534154 \
      --emergency-phone +213559420426
  ```

  I already ran it once to prove it works; the output file is at `scratch/production.env` (git-ignored). You can regenerate with `--force` if the user asks for fresh entropy before go-live.

### 2.6 Gitignore (`.gitignore`)

- Added a `*.env` catch-all at repo root so `scratch/production.env` (and any other file ending in `.env`) stays off GitHub, with `!.env.example` + `!*.env.example` carve-outs.
- `scratch/` dir was already tracked (historical patch scripts). I did NOT change that — only the `.env` catch-all applies.

---

## 3. What is dirty but uncommitted (your merge responsibility)

```
M  .gitignore
M  apps/desktop-cms/src/App.tsx
M  apps/desktop-cms/src/api/adminClient.ts
M  backend/app/main.py
M  backend/app/seed.py
M  backend/tests/test_luxe_api.py
M  backend/tests/test_security_hardening.py
?? backend/scripts/generate_production_env.py
?? scratch/README.md
```

I'll commit + push this as one atomic change before this session ends. If the session ends **before** that push, just `git diff` to see the full picture.

**This `HANDOFF_FOR_ANTIGRAVITY.md` file itself is part of that commit.**

---

## 4. The user's immediate priorities (top → bottom)

1. **Finish the CMS i18n translation pass.** This is the newest priority. The
   infrastructure is now in place (see `docs/cicd/I18N_AUDIT.md`). I shipped
   the shell + PosPage as the pattern reference; ~20 pages remain. The audit
   doc has a per-page priority queue in §7 and a step-by-step recipe in §3
   — follow that pattern and **keep the FR / EN / AR keys in the same
   order inside `apps/desktop-cms/src/i18n/translations.ts`** to keep diffs
   readable.
   - Next three pages, in order: `BusinessDashboardPage` → `PurchasesPage` +
     `SuppliersPage` → `ProductEditor` + `VariantManager`.
   - For every page, add RTL polish per the recipe's §5 (test with the
     language toggle — no reload needed; the provider updates
     `document.documentElement.{lang,dir}` live).
2. **Keep working on the `docs/specs/claude code.md` modules.** The handoff you left me (`HANDOFF_FOR_CLAUDE.md`) listed the roadmap; it's still accurate except that the backup admin UI and WhatsApp recovery UI are now intentionally gone from the CMS. Do not re-add them.
3. **Keep writing to `HANDOFF_FOR_CLAUDE.md`.** The user wants a continuously-updated handoff doc that documents the current state so the next Claude session can resume without context loss. You own that file.
4. **Three blockers from your own earlier audit (BLOCKER-01/02/03) are untouched.** I deliberately did not change them because they need the owner's input (domain confirmation, Dockerfile build stage, Tauri signing keypair). Confirm with the user before changing.
5. **Do NOT regenerate the production `.env`** — the user already has the values from my run. If they need fresh entropy, re-run `backend/scripts/generate_production_env.py --force` and have them re-copy to the VPS.

---

## 5. The commit I'm about to make

```
feat(cleanup): strip WhatsApp recovery + backup UI; blank-slate seed; production .env

Removes the WhatsApp admin password recovery flow and the admin-facing
backup endpoints + UI per owner request. Production first-boot now
leaves the storefront empty (demo catalog gated behind
LUXE_SEED_DEMO_PRODUCTS=1). Adds a production .env generator with
cryptographically strong values for every secret the stack owns.

Details in HANDOFF_FOR_ANTIGRAVITY.md.
```

Followed by the standard `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` trailer.

---

## 6. Rules of engagement (unchanged from your handoff)

- Never commit `.env` files, SQLite DBs, uploaded fixtures, or secrets.
- Never run `git push --force`, `git reset --hard` on the branch, or `git clean`.
- Keep commits small and tested. Full backend focused-suite green before pushing.
- Both of us land commits on separate branches: you on `feat/pos-core-cash-register`, me on `feat/pos-core-cash-register-18lsk6`. The user merges both into the final PR.

---

## 7. When your limits are near

Mirror what I did here: write `HANDOFF_FOR_CLAUDE.md` with the shape above. Include **what you just committed**, **what's uncommitted**, **what tests pass**, and **what section of `docs/specs/claude code.md` to pick up next**. Leave the backend running if you had it running — I'll probe `/api/v1/health` to know.

Good luck. The user is watching the shop open in Blida — every decision has to work in the real boutique.

— Claude Opus 4.7, cloud session, signing off this round
