# CMS i18n — audit & incremental migration guide

**Status (this commit):** infrastructure in place; shell + PosPage partially
translated as proof-of-pattern. ~20 CMS pages still have hardcoded French
strings and need per-page migration.

## 1. What landed this round

- `apps/desktop-cms/src/i18n/translations.ts` — flat snake_case dictionaries
  for **FR** (canonical), **EN** and **AR**. Keys cover sidebar, topbar,
  common CTAs, status strings, dashboard shell, and PosPage toolbar.
- `apps/desktop-cms/src/i18n/index.tsx` — React Context + hooks:
  `useT()` → `(key, vars?) => string`, `useLang()`, `useDir()`, and the
  `<LanguageToggle />` component (3-way FR / EN / AR segmented control).
- `tailwind.config.js` — `rtl:` and `ltr:` variants wired via a tiny
  plugin that reads `[dir="rtl"]`/`[dir="ltr"]`. Any class can now take
  the `rtl:` prefix without a second utility pass.
- `main.tsx` — wraps the app in `<I18nProvider>`.
- `App.tsx` — top bar now hosts `<LanguageToggle />` next to the online
  chip; status chip, refresh, and logout buttons use `useT()`; sidebar
  navigation labels are translated.
- `PosPage.tsx` — toolbar, status, "Encaisser" CTA, and the scan-input
  label all go through `useT()`.

Language selection is persisted at `localStorage.luxe_cms_lang`. The
provider updates `document.documentElement.lang` + `dir` on change, so
Tailwind's `rtl:` and any `:lang(ar)` CSS inherit globally.

## 2. What is still hardcoded

Rough count of user-facing French strings per file (greps for quoted
strings starting with a capital letter — approximate, use as a priority
hint):

| File                                   | Rough strings |
| -------------------------------------- | ------------: |
| `pages/CategoryBuilderPage.tsx`        |           233 |
| `pages/PosPage.tsx`                    |            57 |
| `components/ProductEditor.tsx`         |            47 |
| `components/VariantManager.tsx`        |            39 |
| `pages/DevicesPage.tsx`                |            35 |
| `pages/UsersRolesPage.tsx`             |            31 |
| `pages/PurchasesPage.tsx`              |            28 |
| `pages/BusinessDashboardPage.tsx`      |            27 |
| `pages/InventoryMovementsReportPage.tsx` |          24 |
| `pages/SuppliersPage.tsx`              |            22 |
| `pages/ExpensesPage.tsx`               |            22 |
| `components/CmsCharts.tsx`             |            22 |
| `pages/InventoryCountPage.tsx`         |            17 |
| `pages/CustomersPage.tsx`              |            16 |
| `pages/TreasuryReportPage.tsx`         |            14 |
| `pages/AccountingPage.tsx`             |             — |
| `pages/AuditLogPage.tsx`               |             — |
| `pages/DeliveryWilayasPage.tsx`        |             — |
| `pages/ExpenseReportPage.tsx`          |             — |
| `pages/FiscalSettingsPage.tsx`         |             — |
| `pages/LowStockPage.tsx`               |             — |
| `pages/SalesReportPage.tsx`            |             — |
| `pages/TreasuryPage.tsx`               |             — |
| `components/InvoiceModal.tsx`          |             — |
| `components/DeliveryNoteModal.tsx`     |             — |
| `components/BarcodeLabelModal.tsx`     |             — |
| `components/PrinterSettingsModal.tsx`  |             — |
| `components/StockWriteOffModal.tsx`    |             — |

And many strings surface from `utils/clientNotifier.ts` (toast messages),
the admin client's error messages, and the storefront's `index.html`
(already FR/AR/EN-aware there, so no CMS i18n work required).

## 3. Recipe: translate one page

The pattern we settled on has four steps. Follow it for every page.

1. **Import the hook**:

   ```tsx
   import { useT } from "../i18n";
   ```

2. **Call it inside the component**:

   ```tsx
   export const SomePage: React.FC<Props> = (props) => {
     const t = useT();
     // …
   };
   ```

3. **Pick keys**. Add one `category.action_description`-style key per
   visible string to `apps/desktop-cms/src/i18n/translations.ts`:

   ```ts
   // fr dictionary
   "products.list.title": "Catalogue produits",
   "products.list.add": "Ajouter un produit",

   // en dictionary (keep the key, translate the value)
   "products.list.title": "Product catalogue",
   "products.list.add": "Add a product",

   // ar dictionary
   "products.list.title": "كتالوج المنتجات",
   "products.list.add": "إضافة منتج",
   ```

   Keys live under a page-scoped prefix (`products.list.*`,
   `categories.builder.*`, `orders.table.*`, …). Keep the same insertion
   order in all three dictionaries so diffs stay readable.

4. **Replace the string** at the call site:

   ```diff
   - <h2 className="text-xl">Catalogue produits</h2>
   + <h2 className="text-xl">{t("products.list.title")}</h2>
   ```

   Interpolation is `{{name}}` in the value, `t("key", { name })` at the
   call site.

5. **RTL polish**. For layouts that need direction-aware behaviour:

   - **Padding / margin** — use logical variants OR Tailwind's `rtl:`:
     `className="pl-4 rtl:pl-0 rtl:pr-4"`.
   - **Flex row ordering** — `flex-row rtl:flex-row-reverse`.
   - **Chevron / arrow icons** — rotate with `rtl:-scale-x-100` if the
     arrow has directional meaning (←/→). Decorative icons (search,
     edit) stay as-is.
   - **Tables** — numeric / currency columns stay left-aligned in LTR,
     right-aligned in RTL: `text-start` (logical) or
     `text-left rtl:text-right`.
   - **Dropdown origins** — Tailwind positions are based on
     `left/right`, so flip with `rtl:left-auto rtl:right-0`.

## 4. RTL-sensitive places to double-check

The grep for `className=.*left-|right-|pl-|pr-|ml-|mr-|text-left|text-right`
across the CMS highlights spots where absolute direction is used. For each:

- Sidebar: already fine — flexbox handles row reversal.
- Toolbars (top bar, POS toolbar): flex gaps are symmetric, but the
  **online chip's `w-2 h-2` pulse** is fine in both directions; verify.
- Tables with action columns (`ProductEditor`, `VariantManager`,
  `PurchasesPage`): the per-row action buttons are flex-end — look OK.
- Modals: fixed-center modals need no RTL work; the icon-left-header
  pattern in `PrinterSettingsModal` reads naturally in RTL too.
- Invoice / delivery-note documents: these are **print-targeted** and
  should respect the store's fiscal paperwork orientation. Leave them
  FR-only unless the owner specifies an Arabic invoice layout.

## 5. Translation quality notes

- **Arabic verbs** are infinitives where English uses imperatives
  (Save → حفظ, Delete → حذف). Avoid the awkward imperative "احفظ".
- **Numbers and currency** stay in Latin digits (`1 500 DA`). Arabic-
  Indic digits (١٥٠٠) are less legible on a touchscreen and conflict
  with the thermal-receipt font. If the owner insists, reopen.
- **Technical IDs** (SKU, barcode, slug, email, URL) are never
  translated. Keep them as data, render them in the `font-mono` family
  which the UI already uses.
- **Product names / brand names / descriptions** come from the backend
  per-locale (`name_fr`, `name_ar`, `name_en`) — never auto-translated.

## 6. Storefront

The public storefront (`apps/storefront/index.html`) already has a
FR / AR / EN language toggle (see `setLanguage()` + the `[dir="rtl"]`
CSS). That path is **separate** from the CMS i18n layer and should
stay untouched — the two use different mechanisms by design (vanilla
JS state in index.html; React Context in CMS).

If you want the CMS to drive the storefront language, that's a bigger
decision: it would require a shared setting in `store_settings` and a
backend endpoint. Out of scope for this round.

## 7. Next-up priority queue (COMPLETED by Antigravity)

1. ✅ **BusinessDashboardPage** — Translated (Commit `dffd817`).
2. ✅ **PurchasesPage + SuppliersPage** — Translated (Commits `db8bcd4` & `0f5a1a6`).
3. ✅ **ProductEditor + VariantManager** — Translated (Commit `de2c170`).
4. ✅ **CategoryBuilderPage** — Headers, CTAs, filter tabs, stats cards, and action buttons translated (Commit `53e3fb0`).
5. ✅ **Reports** (`SalesReportPage`, `ExpensesPage`, `InventoryMovementsReportPage`, `TreasuryReportPage`) — Translated (Commits `054ff52` & `4d6a104`).
6. ✅ **Modals** (`InvoiceModal`, `DeliveryNoteModal`, `PrinterSettingsModal`, `BarcodeLabelModal`) — Translated (Commit `0394e4c`).

## 8. Verified here

- `npx tsc --noEmit` on the CMS → clean.
- `npm run build` → OK.
- Switching language in the UI: updates `document.documentElement.{lang,dir}`
  live, persists to `localStorage.luxe_cms_lang`, no reload needed.
- Switching to AR flips Tailwind `rtl:` utilities (verified by grepping the
  compiled CSS for `[dir="rtl"]` selectors — generated by the plugin).

## 9. Known gaps (documented, not fixed this round)

- Toast text in `utils/clientNotifier.ts` is still French.
- Error messages from `adminFetch` in `api/adminClient.ts` are French.
- Date / currency formatting still uses `fr-DZ` locale strings; swapping
  to `ar-DZ` or `en-DZ` per language would require a tiny helper.
- Input placeholder text in form fields is translated per-file; no
  global coverage check yet.
