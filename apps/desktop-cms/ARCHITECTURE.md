# Desktop CMS / POS — architecture

The back office and till of Mus Luxury: a React + TypeScript app (Vite) inside a **Tauri 2** desktop shell
(Rust) on Windows. The same React code also runs in a browser for development and for the browser tests
(`e2e/`); features that need Windows (printers, keychain, offline till, PC backup copies, notifications,
updates) detect the browser and degrade gracefully.

```
                ┌──────────────────────── Tauri window (Windows) ────────────────────────┐
                │  React UI (src/)                                                       │
  owner/staff ──┤   App.tsx  ─ shell: setup, login, session, layout, sidebar, dialogs   │
                │     │        shared data: catalogue, orders, dashboard (+ actions)     │
                │     ├─ pages/*      one file per screen                                │
                │     ├─ components/* pieces used by several screens / modals           │
                │     ├─ utils/*      helpers, hooks, desktop bridges                    │
                │     └─ api/adminClient.ts ── HTTPS ──▶ FastAPI server (VPS)            │
                │                                                                        │
                │  Rust (src-tauri/src/): 31 commands called from utils/*               │
                │   keychain · printers (ESC/POS, ZPL) · offline catalogue + sales queue │
                │   (local SQLite) · Windows notifications · updater · PC backup copies  │
                └────────────────────────────────────────────────────────────────────────┘
```

## 1. Folders

| Folder | What goes there | Rule |
|---|---|---|
| `src/App.tsx` | The shell: first-time setup, login, session restore (`keychainReady`), workspace loading (`loadAllWorkspaceData`), layout, sidebar, notification centre, product editor and delete dialogs, the catalogue/order actions shared by several screens | No screen markup: a screen is a file in `pages/`. Every screen sits in an always-mounted container `activeTab === "<id>" ? "block" : "hidden"` (switching screens never loses typed text) — tests check this |
| `src/pages/` | One file per screen of the menu (`ProductsPage`, `OrdersPage`, `PosPage`, `TreasuryPage`…) | A screen whose data nobody else uses **loads and saves it itself** (`CustomersPage`, `ContentSettingsPage`, the report pages). A screen showing data shared with other screens gets it as typed props (`ProductsPage`, `OrdersPage`, `DashboardPage`, `InventoryPage`) |
| `src/components/` | Modals and widgets used by several screens (`ProductEditor`, `VariantManager`, `InvoiceModal`, `DeliveryNoteModal`, `BarcodeLabelModal`, charts, toasts, sidebar) | No direct knowledge of which screen shows them |
| `src/api/adminClient.ts` | Every call to the server: `DesktopCmsApi.<method>()` (≈150 methods) | Screens never call `fetch` themselves; a test checks every method is used somewhere |
| `src/utils/` | Helpers and hooks (see §4) | Flat folder (backend tests read some files by path) |
| `src/i18n/` | `translations.ts` (FR / EN / AR keys) and `useT()` / `LanguageToggle` | French is the reference; Arabic switches the layout to right-to-left |
| `src-tauri/src/` | The Rust side: `main.rs` (keychain, external links), `pos_hardware/` (ESC/POS receipts, ZPL labels, cash drawer), `pos_mirror/` (offline catalogue + sales queue in local SQLite), `app_services.rs` (notifications, focus, updater), `backup_copies.rs` | Each command is registered in `main.rs` and called from one `utils/` bridge |

## 2. How data flows

1. **Start**: `main.tsx` mounts `App` inside the language provider and an error boundary. `App` restores the
   session token from the Windows keychain (`restoreSessionFromOsKeychain`) and only then sets
   `keychainReady` — nothing is loaded before (no request without a token).
2. **Workspace load** (`loadAllWorkspaceData`): one parallel round of requests for the data several screens
   share — dashboard, brands, categories, products, orders, stock movements, anti-retour blacklist, WhatsApp
   outbox, audit, readiness — each only if the user's role may see it (`may(...)`), each failing alone
   without breaking the others. It runs after login, after actions that change shared data, and on the
   automatic refresh.
3. **Screens that own their data** load when opened and after their own saves.
4. **Live updates**: a poll brings new online orders (Windows notification + sidebar badge); it never
   replaces a search the user is looking at.
5. **Errors**: every action ends in `notifyClientSuccess` / `notifyClientWarning` / `notifyClientError`
   (`utils/clientNotifier.ts`): a French message box or toast, never raw server text. A 401 becomes
   *Session expirée* and keeps local drafts.

## 3. Permissions

The server decides (every route checks a permission). The CMS mirrors it so people only see what they may
use: `utils/tabAccess.ts` maps each screen to the permissions it needs; `canOpen(id)` hides the menu entry,
the screen and its data loading. A cashier sees the till, orders and customers — not the money screens.

## 4. `utils/` by theme

| Theme | Files |
|---|---|
| Server time and labels | `serverDate.ts` (UTC from the server → shop time), `orderStatus.ts`, `movementReasons.ts`, `codeLabels.ts` |
| Messages and drafts | `clientNotifier.ts` (message boxes, toasts, confirmations), `notificationCenter.ts`, `draftStorage.ts` (unsaved typing survives a restart) |
| Network | `networkQueue.ts` (timeouts, retries, online/offline indicator) |
| Till (POS) | `posMirror.ts`, `posMirrorSync.ts` (offline catalogue), `posLookupResolver.ts`, `posOfflineQueue.ts` (sales made offline, sent later), `posHardware.ts`, `systemPrint.ts`, `barcode.ts`, `useBarcodeScanner.ts` |
| Desktop bridges | `osKeychain.ts`, `appUpdater.ts`, `backupCopies.ts`, `openExternal.ts` |
| Access and UI hooks | `tabAccess.ts`, `useEscapeToClose.ts` |

## 5. Adding a screen

1. `src/pages/MyPage.tsx` — loads its own data if no other screen needs it; French messages through
   `notifyClient*`; texts through `useT()` with keys in FR, EN and AR.
2. Server calls: add methods to `DesktopCmsApi` (`api/adminClient.ts`).
3. Menu: entry in `components/CmsSidebar.tsx`, permission in `utils/tabAccess.ts`, container in `App.tsx`
   (`{canOpen("my_page") && <div className={activeTab === "my_page" ? "block" : "hidden"}><MyPage /></div>}`).
4. Tests: a browser test in `e2e/tests/` for what the screen does; `06-cms-all-screens` already opens every
   menu entry in 3 languages for the owner and a cashier.

## 6. Checks

`npm run lint` (TypeScript with no unused code + ruff), `npm run test:e2e` (34 browser tests, shop + CMS),
`npm run test:backend`. CI runs them all, plus the build of the desktop bundle.
