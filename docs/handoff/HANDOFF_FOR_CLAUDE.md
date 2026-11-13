# HANDOFF — Mus Luxury (LUXE)

**To:** Claude (next Claude Code session) & Antigravity
**From:** Antigravity (Advanced Agentic Pair Programmer on local Windows machine)
**Date:** 2026-11-09
**Project root:** `C:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce`
**Branch:** `feat/pos-core-cash-register`
**Latest commit:** `dac4246` (`fix(security): enforce mus-luxury.com domain and purge legacy .dz references in backend`)

---

## 1. Executive Summary & Critical Context

1. **WhatsApp Password Recovery:** **100% REMOVED.**
   - All backend recovery endpoints (`/admin/auth/recovery/*`) were deleted from `backend/app/main.py`.
   - All frontend UI (link "Mot de passe oublié ?", WhatsApp OTP modal, recovery fields in setup wizard) were removed from `apps/desktop-cms/src/App.tsx`.
   - Remaining dead code (`dispatch_whatsapp_recovery_otp`, `RecoveryRequestInput`, `RecoveryVerifyInput`, and dead error translation handlers) was completely purged.
   - Owner password reset is **strictly server-side CLI only**:
     ```bash
     python3 backend/scripts/emergency_reset_owner.py --email admin@mus-luxury.com --new-password '<new>'
     ```
   - **Customer order notifications via WhatsApp are kept intact** (`backend/app/whatsapp.py` and `/api/v1/webhooks/whatsapp`).

2. **Production Domain Enforcement:**
   - **Strictly `https://mus-luxury.com` and `https://api.mus-luxury.com`**.
   - Zero tolerance for legacy `.dz` / `musluxury.dz` references. Purged from CORS in `backend/app/main.py`, seed templates in `backend/app/seed.py`, `backend/scripts/emergency_reset_owner.py`, `ProductEditor.tsx`, and `UsersRolesPage.tsx`.

3. **Desktop Application Build & Live Execution:**
   - Visual Studio 2022 C++ MSVC toolchain + Rust Tauri 2 build completed cleanly.
   - Standalone release binary built: `apps/desktop-cms/src-tauri/target/release/luxe-desktop-cms.exe`.
   - Local FastAPI backend daemon running on `http://127.0.0.1:8000` (Health status verified: `database: connected`, 69 wilayas, 9 categories).
   - Desktop app process `luxe-desktop-cms.exe` launched and active on Windows desktop with Microsoft Edge WebView2 runtime.
   - Login credentials for local testing:
     - **Email:** `admin@mus-luxury.com`
     - **Password:** `MusLuxury2026!`
   - Server endpoint switcher added to login screen to toggle between `http://127.0.0.1:8000/api/v1` (local) and `https://api.mus-luxury.com/api/v1` (VPS production).

4. **2 GB RAM Octenium VPS Optimization:**
   - Container memory caps enforced in `docker-compose.yml`: API (256M), DB (256M), Nginx (64M), Storefront (32M) = 608 MB total memory footprint.
   - PostgreSQL 16 tuned for 2 GB VPS (`shared_buffers=128MB`, `work_mem=4MB`, `max_connections=30`).
   - `PostgresConnectionPool` (max 15 connections) with thread-safe leasing and automatic rollback on return implemented in `backend/app/database.py`.
   - Docker JSON log rotation enabled (`max-size: 10m`, `max-file: 3`).

5. **Durable Offline POS Queue:**
   - SQLite table `offline_sales_queue` added to `pos_mirror.sqlite3` in Rust (`apps/desktop-cms/src-tauri/src/pos_mirror/mod.rs`).
   - Tauri IPC commands exposed: `pos_queue_enqueue`, `pos_queue_list`, `pos_queue_upsert_batch`, `pos_queue_remove`, `pos_queue_clear_synced`.
   - Auto-migration in `apps/desktop-cms/src/utils/posOfflineQueue.ts` migrates items from `localStorage` to SQLite on boot and purges `localStorage`.

---

## 2. i18n Translation Pass Status (`docs/cicd/I18N_AUDIT.md`)

- **Infrastructure:**
  - `apps/desktop-cms/src/i18n/translations.ts`: Flat snake_case dictionaries in FR (canonical), EN, and AR in identical key order.
  - `apps/desktop-cms/src/i18n/index.tsx`: `<I18nProvider>`, `useT()`, `useLang()`, `useDir()`, `<LanguageToggle />`.
  - Tailwind RTL plugin enabled in `tailwind.config.js`.

- **Completed Pages & Modules:**
  - Shell (topbar, online chip, refresh, logout, 14 sidebar items)
  - `PosPage.tsx` (cash register, items, payments, drawer, hold/resume)
  - `BusinessDashboardPage.tsx` (Commit `dffd817`)
  - `SuppliersPage.tsx` (Commit `0f5a1a6`)
  - `PurchasesPage.tsx` (Commit `db8bcd4`)
  - `ProductEditor.tsx` (~47 keys) + `VariantManager.tsx` (~39 keys) (Commit `de2c170`)
  - `CategoryBuilderPage.tsx` (CTAs, headers, filter tabs, stats cards, action buttons) (Commit `53e3fb0`)
  - `SalesReportPage.tsx` + `ExpensesPage.tsx` (Commit `054ff52`)
  - `InventoryMovementsReportPage.tsx` + `TreasuryReportPage.tsx` (Commit `4d6a104`)
  - Modals: `InvoiceModal.tsx`, `DeliveryNoteModal.tsx`, `PrinterSettingsModal.tsx`, `BarcodeLabelModal.tsx` (Commit `0394e4c`)

- **Translation Pass Result:**
  - 100% of all planned pages, reporting tools, management workflows, and operational modals have been completely translated into FR, EN, and AR with full bidirectional layout and RTL awareness.

---

## 3. Test & Build Status (All 100% Green)

| Component | Command | Result |
| --- | --- | --- |
| **Backend API** | `uvicorn app.main:app` | **Listening on http://127.0.0.1:8000** (`/api/v1/health` 200 OK) |
| **Desktop Binary** | `cargo build --release` | **Clean release build** (`luxe-desktop-cms.exe`, 1.24s incremental) |
| **Desktop CMS Web** | `cd apps/desktop-cms && npm run build` | **Clean build** (`tsc && vite build` in ~6.2s) |
| **Storefront Build** | `cd apps/storefront && npm run build` | **Clean build** (`tsc && vite build` in ~2.6s) |
| **Tauri Rust Check** | `cd apps/desktop-cms/src-tauri && cargo check` | **Clean** (0 errors) |
| **Tauri Rust POS Tests** | `cd apps/desktop-cms/src-tauri && cargo test pos_mirror` | **3/3 PASS** |
