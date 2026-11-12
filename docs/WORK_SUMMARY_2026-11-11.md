# Mus Luxury — Work Summary (9–11 November 2026)

Branch: `feat/pos-core-cash-register-18lsk6`
Commits covered: `4898d4c` → `2775538` → `e9bea80` → `c32dfd3` (+ this summary)

Written for the owner. For day-to-day operation, read `docs/OPERATIONS_GUIDE.md`.

---

## At a glance

| # | Area | Result |
|---|---|---|
| 1 | CMS navigation | One-line tab strip replaced by a grouped side menu with search |
| 2 | Messages & notifications | Toasts, queued message boxes, notification bell, Windows notifications |
| 3 | New online orders | Detected within 45 s, with pop-up + Windows alert + "Voir" button |
| 4 | Auto-update of shop PCs | Rebuilt so it can no longer crash the app; signed updates from GitHub |
| 5 | Deleted categories coming back | Root cause found and fixed |
| 6 | Demo data reappearing | Demo catalog no longer re-created; dangerous script removed |
| 7 | Database management | Owner panel: status, backup now, restore, "new empty database" |
| 8 | Server backups | Nightly chain repaired (it would have saved empty backups) |
| 9 | Keys & placeholders | Audited; internal secrets generated; one-command setup for GitHub keys |
| 10 | Documentation | Operations guide in plain language + this summary + Antigravity handoff |

---

## 1. CMS navigation (commit `2775538`)

- The 26 modules are grouped into 8 sections in a side menu: Vue d'ensemble, Ventes, Catalogue,
  Stock & achats, Finances, Rapports, Boutique en ligne, Administration.
- **Ctrl + K** opens a search box. Typing "depense" and pressing Enter opens Dépenses.
- Sections fold and unfold. The menu can collapse to icons only, and the choice is remembered.
- Badges: number of orders to confirm, and number of products low or out of stock.
- Works in Arabic: the menu moves to the right-hand side.
- `4898d4c`: Antigravity's desktop branch was merged first, so nothing of his was lost.

## 2. Messages and notifications (commit `e9bea80`)

**Toasts** (small messages)
- Shown in the bottom corner (bottom-left in Arabic), no longer over the header.
- Newest nearest the corner, 4 at most. Identical messages merge into one with "×2".
- Show time depends on importance (success 4.5 s, error 10 s). Hovering pauses the timer,
  and so does leaving the window. A bar shows the time left.

**Message boxes** (errors and checks that need attention)
- Queued instead of overwriting each other. Several in a row show "1 sur 3", with **Suivant** and
  **Tout fermer** buttons.
- **Entrée** or **Échap** closes the current one. Translated in French, English and Arabic.
- An error shown in a message box is no longer also shown as a toast.

**Notification bell** (header)
- History of the session's messages, unread counter, "Tout marquer comme lu", "Effacer".
- On/off switch for Windows notifications.

**Windows notifications**
- Shown only when the CMS is in the background; the taskbar button flashes too.
- Used for: new online orders, an update being available, and offline POS sales synced or in conflict.

## 3. New online orders (commit `e9bea80`)

- The CMS checks for new orders every 45 seconds.
- A pop-up "Nouvelle commande en ligne #ref • client • total DA" with a **Voir** button opens Commandes.
- The Commandes list and its badge refresh by themselves.

## 4. Auto-update of the shop PCs (commit `e9bea80`)

- The old updater was removed because it crashed the app at startup when no signing key was set.
- The new one is switched on only in builds that carry the public signing key. Without the key,
  the app runs normally with updates off.
- Checks 15 s after the CMS starts, then every 4 hours.
- When an update exists, the version chip turns gold and a pop-up plus a Windows notification appear.
- The update installs only when someone clicks **Installer et redémarrer**, so it never interrupts a
  sale. If offline sales are still waiting, the CMS warns first.
- Only installers signed with the Mus Luxury key are accepted.
- GitHub side: pushing a tag `v1.2.0` builds the signed installer, takes the version from the tag,
  and publishes `latest.json` (script `apps/desktop-cms/scripts/make-latest-json.mjs`).

## 5. Deleted categories coming back (commit `c32dfd3`)

| Cause | Fix |
|---|---|
| The CMS read categories from the public website list, which the browser may cache for 5 minutes. A reload within 5 minutes showed the deleted ones again. | The CMS always asks the server for fresh data (`cache: "no-store"`) and reads the admin list. The website cache is cut to 30 s. |
| "Supprimer" only archived a category, and archived categories were invisible, so they could not be restored or removed. | New **Archivées (n)** tab with **Restaurer** and **Supprimer définitivement**. The "Total catégories" card counts only live categories. |

Checked in a browser: deleted categories stay deleted after two reloads.

## 6. Demo data reappearing (commit `c32dfd3`)

- Before: a PC in development mode re-created the demo shop (9 categories, 4 products) whenever its
  database file was new. Now the demo catalog exists only for automated tests, or when explicitly
  requested with `LUXE_SEED_DEMO_PRODUCTS=1`.
- `backend/scripts/restore_demo_products.py` was **deleted**. When the shop had no products, it
  erased all staff accounts and roles and re-created the demo shop.
- `backend/scripts/reset_fresh_store.py` now uses the safe engine below: backup first, works on the
  PC and on the server.

## 7. Database management for the owner (commit `c32dfd3`)

Location: **CMS → Sauvegardes & Sécurité → Base de données & sauvegardes** (owner only).

- **Status:** engine (SQLite on a PC, PostgreSQL on the server), size, number of records, contents
  (categories, products, orders, customers…), encryption on/off, last backup, warnings.
- **Sauvegarder maintenant**, optionally with the product photos.
- **Restaurer** any backup in the list. You type `RESTAURER` and your password. The current state is
  saved first, and the replacement is all-or-nothing.
- **Nouvelle base de données → Créer une base vide.** You type `EFFACER` and your password.
  - Erases: catalog, stock, orders, customers, POS sales, cash, expenses, suppliers, coupons,
    banners, history.
  - Keeps: staff accounts and roles, POS devices, the 69 wilayas with delivery prices, legal pages,
    and (by default) the shop settings.
  - A full backup is taken just before, so one click undoes it. Numbering restarts at 1.
- **POS PCs:** after a reset or restore, every till discards its offline catalog and downloads the
  new one, so deleted products don't stay on the tills.
- Backups are encrypted (AES-256) and are never downloadable over the internet.
- Same engine from the command line: `python -m app.backup_cli info | create | list | verify | restore | reset`.
- Tested on SQLite, on a real PostgreSQL 16, and with a PC backup restored onto PostgreSQL.

## 8. Server backups repaired (commit `c32dfd3`)

| Problem found | Fix |
|---|---|
| The nightly backup could not reach the database inside Docker. It fell back to SQLite and saved an **empty** database as "success". The same script runs before every deploy. | Dumps through `docker exec luxe_postgres pg_dump`, refuses an empty database, records `last_backup_status.json`. |
| Photos were taken from an empty folder outside Docker. | Archived from the `luxe_api` container. |
| The backup folder belonged to `root`, but the job runs as `luxe`. | Folder now belongs to the backup user. |
| Restore would have gone into a SQLite file instead of the real database. | Restores into the Docker database, pauses the API meanwhile, all-or-nothing. |
| The nightly verification needed tools missing on the server. | Verifies in a temporary database inside the container, then deletes it. |
| The off-site upload could send an incomplete set of files. | Uploads exactly the files listed in the backup's checksum file. |
| Only the last step of the backup job was logged. | The whole chain is logged to `/opt/luxe/logs/backup.log`. |
| Deploys used the old release's backup script. | Deploys use the new, fixed script. |

The nightly backup now also includes a snapshot that can be restored in one click from the CMS.

## 9. Keys and placeholders (commit `c32dfd3`)

- **Already generated** (strong random values in the private production `.env`, never in GitHub,
  because the repository is public): `SECRET_KEY`, `CMS_HMAC_SIGNING_SECRET`, database password,
  `BACKUP_ENCRYPTION_KEY`, admin password, emergency code, WhatsApp webhook token.
- **GitHub keys in one command on your PC**: the app-update signing key and the server deploy key are
  created on your PC and stored in GitHub automatically:
  ```powershell
  powershell -ExecutionPolicy Bypass -File infrastructure\scripts\setup-github-secrets.ps1 -VpsHost <VPS IP>
  ```
- **Only you can obtain these**, from accounts in your company's name: Yalidine, ZR Express, Maystro,
  Chargily, S3 storage, email password, WhatsApp Cloud API. The shop works without them; each feature
  stays off until its key is added. The full list is in `docs/OPERATIONS_GUIDE.md` §8.

## 10. Documentation

- `docs/OPERATIONS_GUIDE.md`: how the PC, the server, GitHub and the website work together; where the
  data lives; how sync and updates work; backups, restore and "new database"; the incident list and
  remaining risks; key status; routine checklist.
- `docs/DESKTOP_CMS_RELEASE_GUIDE.md`: release and update process (updated).
- `HANDOFF_FOR_ANTIGRAVITY.md`: technical notes for the other AI working on the PC branch (updated).

## 11. Online shop — Step 1 fixes (after the storefront review)

| Problem found | Fix |
|---|---|
| Every product showed ★★★★★ "(12)" reviews that did not exist | Fake rating removed everywhere |
| Every product showed the same 3 colour dots (green, black, gold) | Dots now show the product's real colours, or nothing |
| A product without a photo showed a Chanel-style bag photo | Neutral "ML — Photo à venir" image |
| Only the first 50 products were ever shown | The shop reads every page of the catalog (up to 2 000 products) |
| Each visitor asked the server for data every 4 s (≈1 request/second) | Every 60 s while the page is visible, and when the customer returns after 30 s |
| 17 of 23 places inserted server text without cleaning it (code injection risk) | Every text from the server is cleaned on arrival; colour codes validated |
| A colour like "Bleu d'azur" broke the product page | Option names are encoded safely |
| Products had no link of their own; Back did not close the product | Each product has a link `#/produit/<slug>` (shareable on WhatsApp/Instagram); Back closes it and keeps the scroll position; a shared link opens the product directly |
| Phone: menu button cut off, top bar truncated, WhatsApp button covering content | Header fits on phones (favourites in the bottom bar), top bar shows tariffs + language, WhatsApp is a small round icon |

The "order on WhatsApp" message now includes the product link, so the shop sees exactly which item it is.
Checked in a browser with 64 products, a product named like an attack (shown as plain text, not run),
an apostrophe colour, shared links, Back button, iPhone size in French and Arabic.

## 12. Online shop — Step 2: Google, link previews, clean code

| Before | Now |
|---|---|
| Products and categories had no real address (only `#/…`, which Google ignores) | `mus-luxury.com/produit/<name>` and `mus-luxury.com/categorie/<name>`; old `#/` links still work |
| Sharing a product on WhatsApp/Facebook/Instagram showed only the generic shop preview | The server builds each product/category page with its own title, description, photo, price and availability, so link previews show the real product |
| Google had no structured product data | Each product page carries schema.org data (name, photos, price in DZD, in stock / out of stock, brand, breadcrumbs). **No ratings are ever invented** |
| `robots.txt` pointed to a sitemap that did not exist | `/sitemap.xml` lists the home page, every active category and every published product, updated automatically |
| Tab title never changed | Title and description follow the product or category being viewed |
| Arabic version still showed "Tarifs 69 Wilayas" and a French banner caption | Translated (FR / AR / EN) |
| A double click or network retry on "Commander" could create **two orders** (new anti-duplicate key per click) | One key per order: the server refuses the second one, and the customer sees the order confirmed once |
| If the server's answer had no order number, the shop **invented one** and showed it as confirmed | Never: the customer sees an error and can retry or use WhatsApp |
| An unused React copy of the shop (3 files, 53 packages) | Removed; tests now check the live shop |

How it works: nginx sends `/produit/…`, `/categorie/…` and `/sitemap.xml` to the API
(`backend/app/seo.py`). The API takes the shop's own page, replaces the block between
`<!-- SEO:START -->` and `<!-- SEO:END -->` with the page's tags, and the shop opens the product
or category as usual. If the shop page cannot be read, people are redirected to the same product
and previews still work.

Checked: 5 new automated tests (`backend/tests/test_seo.py`, including a product name containing
`</script>` that cannot break the page), a real nginx running the production config, and a browser run
covering direct product links, Back/Forward with scroll kept, category addresses after reload, old links,
Arabic labels, and a double click on "Commander" (exactly 1 order in the database).

## 13. CMS — product creation & live preview

| Problem found | Fix |
|---|---|
| Uploaded photos showed as **broken images** inside the CMS (it looked for `/uploads/…` on itself instead of the server) | Every photo is loaded from the right server (`mediaUrl`) |
| Preview showed a Chanel-style bag when there was no photo; colour dots were always the same green; it did not look like the shop (wrong button, stock badge, category label) | New preview that copies the real shop: **Card** view and **Product page** view, with the real colours, badge, prices, description, characteristics and colour/size buttons |
| No way to check Arabic / English texts before publishing | Preview switches **FR / ع / EN** (Arabic right-to-left) and warns when a translation is missing |
| No photo per variant (e.g. the red version) | **Photo column** in Déclinaisons: pick one of the product's photos for each variant; on the shop, choosing that colour shows its photo |
| The server copied the main photo into every variant, so after changing the main photo the shop still showed the **old photo** when a colour was picked | Variants only keep a photo that was chosen for them; a migration cleaned existing copies |
| SKU had to be typed by hand | Suggested automatically from category + name (e.g. `SAC-SEP-482`), editable |
| Extra photos added before the first save lost their order | Kept in the order they were added |
| "Produit créé… sont en ligne" even for a draft | Says "en ligne" only when published, otherwise "enregistré en brouillon" |
| No guidance before publishing | **"Prêt pour la boutique ?" checklist**: name, photo, price, stock, description, translations, gallery, status |
| No way to get the product's link | **Copier le lien boutique** for published products |
| New categories defaulted to a clothing photo | No photo until one is chosen (neutral placeholder) |
| Shop showed the French description to Arabic/English customers; product-page buttons were French only | Descriptions and buttons follow the customer's language |
| The shop forgot the customer's language on every page load | Language remembered; switching it updates an open product |
| SEO title/description typed in the CMS were not used | Used for Google and link previews |

Tested end to end in a browser: created a dress with FR/AR/EN texts, 3 uploaded photos, 2 colours,
the red photo on the red variant, published it, then opened it on the shop (red photo when "Rouge" is
picked, Arabic description and buttons). New tests: `backend/tests/test_product_media.py`.

## 14. Shop content controlled from the CMS — no fixed or invented data

**Where did the "-20 %" promotion cards come from?** They were typed directly into the shop's page
code (three fixed cards: Chaussures -20 %, etc.). They were connected to nothing: the CMS could not
change or remove them, and no real promotion was behind them. The CMS also had a banner form and
home-page switches in its code, but **neither was ever shown on screen**.

| Problem found | Fix |
|---|---|
| 3 promotion cards fixed in the shop's code | Removed. Promotion cards now come only from **CMS → Contenu & Bannières → Carte promo**. With none, the block is hidden |
| Big banner at the top of the home page fixed in the code | **Bannière principale** in the CMS: title/text in FR/AR/EN, button text, photo, where the button leads. Several = they rotate every 7 s. With none, the brand text is shown (translated) |
| Banner form and home-page switches existed in the CMS code but were never displayed; the hidden form invented values ("Collection Exclusive Mus Luxury", link `/categories/sacs` that does not exist on the shop) | New **Page d'accueil** panel: switch each home block on/off; create / edit / hide / reorder / delete banners; choose the destination from the real categories and products (or an https:// link); upload the photo; live preview |
| Banners could not be edited, only created | New server route to edit a banner (`PUT /admin/banners/{id}`), with protection against script links |
| **Free delivery was promised but not applied**: the shop showed "livraison offerte dès 25 000 DA" but the server still charged delivery, so the courier collected more than the customer had seen | The server applies the CMS threshold on the preview AND on the stored order. The shop's confirmation shows the server's own totals. `0` = no free delivery, and the shop then stops promising it |
| Phone, WhatsApp, Instagram, TikTok typed by hand in many places in the shop | All come from **CMS → Contenu → Coordonnées de la boutique** (Instagram and TikTok fields added). WhatsApp numbers are validated |
| Footer "Collections" links fixed | Built from the real categories |
| Products above 25 000 DA hidden by the price filter's starting value | No price limit until the customer moves the slider; the slider's maximum follows the most expensive product |
| Information pages (À propos, FAQ, Retours, CGV): CMS edited only French, and **saving erased the Arabic/English texts** | FR / AR / EN tabs in the CMS; the shop shows the customer's language (French when a translation is empty) |
| Typing in the settings or a page was wiped when the CMS refreshed in the background (window focus) | Unsaved edits are kept until saved |
| **Dashboard chart was invented**: daily values computed from the total (`total ÷ 7 × …`), dates fixed in November 2026, the 7 days / 30 days / Global buttons did nothing | Real revenue per day from the server (last 30 days, cancelled/returned excluded); 7 / 30 days buttons work; "Aucune donnée" when empty |
| Order status ring: percentages could exceed 100 % (cancelled orders counted on top, divided by a total without them); "En attente de confirmation" and "Prêtes à expédier" orders were missing | Total = all orders; every status shown |
| Stock widget mixed products and variants ("normal" stock = products − variants), counted variants of archived products, and "Stock faible" also counted the out-of-stock ones twice in the sidebar badge | Counts variants of products still in the catalogue only; low and out-of-stock counted separately |
| Revenue card counted returned orders | Cancelled and returned orders excluded |
| "69 Wilayas couvertes" written in the CMS whatever the real delivery settings | Shows the real number of wilayas switched on |
| "Protection Système Active / Chiffrement matériel certifié" shown even when the Windows vault was not used | Says which protection is really in use |
| Health check said "degraded" as soon as the owner switched off delivery to one wilaya | Health = the 69 wilayas exist + photos can be saved; switched-off wilayas are a business choice |

Tested in a browser: created a hero banner (with photo, Arabic title, link to a category) and a
promotion card in the CMS, switched off the guarantees bar, set free delivery at 30 000 DA and a new
Instagram link → all visible on the shop within a minute; the banner button opens the chosen
category; the dashboard chart shows the real 5 510 DA order of the test database.
New tests: `backend/tests/test_storefront_content.py` (8).

**Old example content is removed automatically** (details in §15).

---

## 15. Production hardening (server database = PostgreSQL)

The shop server runs **PostgreSQL**; PCs and the automated tests ran on **SQLite**. Running the whole
test suite against a real PostgreSQL 16 database (the same as the VPS) found that several parts that
worked on the PC **would have failed on the production server**:

| Problem on the production database | Effect | Fix |
|---|---|---|
| Dates came back as date objects instead of text | **Shop product list and category list crashed** (shop empty) | The database layer returns the same shapes as on the PC (text dates, whole numbers) |
| The first update on an existing database crashed in the migration step | **The update would stop** ("new release not activated") | Inserts into tables without an `id` column (`schema_migrations`, …) are no longer given `RETURNING id` |
| `substr(date)`, `datetime()`, `MAX(a, b)` (PC-only SQL) | **Sales report, treasury report, POS catalog sync and POS refunds crashed** | Translated automatically for PostgreSQL |
| Best-sellers query grouped by variant only | **Business dashboard and sales report crashed** | Valid on both databases |
| Foreign keys not detected (two columns with the same name) | **"Nouvelle base de données" and restore failed** | Fixed |

Before: 35 test failures on PostgreSQL (31 real ones + 4 caused by the missing tool below), so the CI
"PostgreSQL 16" job could not pass. After: all pass, except
the 4 that need a tool missing from the cloud machine (`@babel/core`; they pass in CI and with a
substitute compiler).

**Example content cleanup, production style.** Older versions put two example banners
("CHAUSSURES — Jusqu'à -20%", "Votre style, notre passion") and two **active** promo codes
(BIENVENUE10 −10 %, ALGERIE500 −500 DA) in every database: any customer typing them got a discount.
Nothing to do by hand:
1. The deploy script backs up the database (as on every update).
2. At the server's first start, the banners are deleted and the codes switched off — **once** (a
   marker is stored, so a banner you later create with the same text is never touched).
3. What was changed is written in **CMS → Journal d'audit**.
Only rows that still have all their original values are touched: an edited banner, or a code
customers already used, is kept. Tested on PostgreSQL 16 with a copy of an old database (backup →
migration → start → 2 banners removed, 2 codes off, 1 audit entry; restart → nothing more).
Server admin check: `docker compose exec api python -m app.cleanup_demo --dry-run`.

## 16. CMS checked as in production (PostgreSQL, first installation, real activity)

Method: empty PostgreSQL database, API in **production** mode, CMS in a real browser. First-time
owner setup, then every one of the 26 screens opened, empty and again after realistic activity (catalogue,
3 online orders — delivered / cancelled / new — an in-store sale, an expense, a supplier purchase
received, a promo code, a banner). Every screen recorded for crashes, failed server calls and errors:
**none**. Then the figures were compared screen to screen.

| Problem found | Fix |
|---|---|
| **Comptabilité ignored in-store sales** (revenue and cost) and counted **returned** orders as revenue; it disagreed with Analytique (26 700 vs 36 400 DA) | Both channels; cancelled and returned orders excluded; cost per variant. Comptabilité and Analytique now give the same revenue, margin and result |
| Per-product profitability counted **cancelled** orders and ignored in-store sales | Same rules as above (refunds subtracted) |
| Returned (never paid) orders counted as sales in the business dashboard, sales report, customer totals and reorder speed | Excluded everywhere ("sale = not cancelled, not returned") |
| Stock value included archived products | Only products still in the catalogue |
| Column "Marge nette" was the unit margin; gross-margin card labelled "Marge nette"; subtitle mentioned VAT that is not computed | Correct labels; subtitle says "since opening, online + in-store" |
| Stock history showed internal codes (`pos_sale`, `order_reserved`…) and "Stock compté" for before → after | Readable reasons, "Avant → après" |
| After first setup the CMS showed an **"emergency code"** that nothing in the system accepts (left from the removed WhatsApp recovery), and copied it into the notification history | Removed; the message explains how a forgotten password is really reset |
| **No way to recover a forgotten owner password**: the login screen said "reset on the server" but no tool existed | `python -m app.admin_cli reset-password` on the VPS (hidden input, 10+ characters, re-activates, signs out everywhere, audited) — guide §7b |

New tests: `tests/test_accounting.py` (both channels, cancelled/returned excluded, reconciled with the
business dashboard). All 269 tests pass on SQLite and on PostgreSQL 16 (except the 4 needing
`@babel/core`, which pass with a substitute compiler).

---

## 17. Every CMS screen, every action, one by one (production mode, PostgreSQL)

Method: API in **production** mode on PostgreSQL 16, CMS in a real browser (Playwright, Algiers time
zone). On each screen every button, form, filter, export and dialog was used, the result checked on the
screen **and** in the database, then fixed and re-tested. One commit per screen group.

| Screen | Problems found → fixed |
|---|---|
| Commandes (`a54a23f`) | WhatsApp buttons said "envoyé" but nothing was sent → the CMS opens WhatsApp on the PC with the message written; the server records "prepared", never "delivered". Cards show items, address, note, discount; only allowed status changes; cancel/return asks first |
| Point de vente (`9cfaa3a`) | Refunds paid back the **list** price, ignoring discounts → each unit refunded at its share of what was paid. Change computed from the pre-discount total → fixed. Open register showed 0 sales → live totals |
| Clients & Produits (`ea3216e`) | "Forcer" on a product **deleted customer orders** → products with history are archived, never deleted. "Réactiver" left the product hidden → really visible again. Customer totals counted cancelled orders → recomputed. PostgreSQL search was case-sensitive → ILIKE |
| Catégories (`5394ce9`) | Photos were typed file paths or example photos → upload field. New categories/products got invented photos → empty. Deleting an attribute used by products was silently forced → explained and confirmed; variant attributes protected |
| Stock, inventaire, rapports (`1328509`) | Treasury ignored till sales, refunds and delivered COD → recorded (with an audited one-time catch-up). Applying a stock count erased sales made after counting → applies the gap. CSV files open correctly in French Excel |
| Achats, fournisseurs, dépenses, trésorerie (`c245f1f`) | Purchases always went to the first variant → variant selector. Bank-paid expenses could not be saved; unpaid expenses could never be paid; deleting a paid expense left its money out; every manual treasury entry failed → all fixed, transfers recorded on both accounts |
| Utilisateurs & rôles (`35d3ee7`) | **A cashier could read accounting, margins, treasury and purchase costs** → new `finance:read` permission (owner, Administrateur) on 18 endpoints. Permissions were frozen in the login token → read live; a deactivated account is refused at once |
| Livraison & Wilayas (`222eb3a`) | A stop-desk switched off in the CMS was still offered by the shop (order failed at the end) → greyed out, never an invented price |
| Paramètres fiscaux, Appareils, Journal d'audit (`8fba426`) | Receipt/refund/inventory prefixes were saved but never used → used. "Tester" a printer asked the **cloud server** to reach a shop-LAN address (always "error") → the desktop app prints a real test and reports it; the server says "test from the shop PC" for LAN addresses. "Impr. test" recorded success blindly → asks if the ticket came out. Audit log showed raw codes → French names, French search, search by person |
| Times (`8fba426`, `507596e`) | Stored UTC times were shown as local (**1 hour early**) → fixed on every screen, 24-hour format. Days, "today", "this month" and reports used the UTC date: an order at 00:30 in Algiers counted on the previous day → shop days (`SHOP_TIMEZONE`, default `Africa/Algiers`). Last second of each day was dropped on PostgreSQL → half-open ranges. CSV times in shop time |
| Tableau de bord, Analytique, Comptabilité (`e61c4a8`) | Infrastructure card was fixed text ("SQLite WAL…", false on the server) → real engine and failed backups. "Nouveau Produit" did not open the form. **Comptabilité and Analytique gave different net profits** (unpaid expenses counted in one only) → same rule everywhere, unpaid part shown. The accounting CSV exported the orders list from a hard-coded `127.0.0.1` address (broken on the VPS) → exports the open tab through the configured server. The "Grand livre" only holds purchases/expenses → renamed "Journal achats & dépenses" |
| Sauvegardes & Sécurité | Backup now, list, refresh, "Créer une base vide" dialog (cancelled): all correct, no change needed |

New tests this round: `test_product_lifecycle.py`, `test_roles_finance.py`, `test_shop_timezone.py`, plus
refund, treasury, expense, transfer, purchase-variant, device, audit-label (fails if an audited action has
no French name) and accounting-export tests. **295 tests** pass on SQLite and PostgreSQL 16 (the 4
`@babel/core` ones pass with the substitute compiler).

---

## 18. The whole business connected — one day through every module

Method: a scripted business day on a fresh database (now the permanent test
`tests/test_business_flow.py`): supplier purchase → online order → delivery → till sale with discount →
partial refund → unpaid expense → register close with a shortage → return after delivery → damaged item,
return to supplier, stock count. After each step every connected figure is compared: stock and its
movements, product cost, supplier debt, treasury (cash / bank), customer totals (list, search and customer
page), stock alerts, register cash, dashboard, Analytique, reports and Comptabilité. Then every screen was
opened in French, English and Arabic as owner and as cashier, looking for errors, refused calls, `NaN` /
`undefined` / raw translation keys.

| Problem found | Fix (`ef65ce3`, `d0696b1`, `3f7b096`) |
|---|---|
| Product cost ignored the purchase's shipping/tax (61 000 DA booked to stock, cost 5 000 instead of 5 083): margins overstated | Landed cost in the weighted average; a variant's own cost is updated too |
| A till closed short or over left the treasury cash box wrong | The difference is recorded in Trésorerie ("Écart de caisse") |
| Damaged / lost / gifted stock and count gaps never reached the accounts: profit overstated | "Pertes et écarts de stock" (at cost) in Comptabilité, Analytique and the CSV; a return to the supplier is not a loss; a unit found at a count reduces it |
| Orders did not keep the promo code or the discount; cancelled orders used up limited codes | Code and discount stored on the order (new columns added at start), shown on the order and invoice; promo list shows orders kept and discount given; cancelling gives the use back |
| Order invoices, receipts and the COD refusal message had the shop's address/phone/links as fixed text | Taken from the settings edited in the CMS |
| ~100 server messages the owner can see were English, so the CMS showed a generic error | French messages (the shop still recognises a retried order) |
| The till's offline catalogue crashed on databases where the VPS deploy had not run the migrations (shop PC, fresh install) | Pending migrations applied at every API start (idempotent, locked on PostgreSQL) |
| "Clients" in the cashier's menu, but the list was refused; a cashier's CMS made 34 refused background calls | Customer list uses the till's permission; screens and data loading follow the role |

| Shop + CMS in real browsers: the shop cached the product list up to ~6 min and delivery prices up to a day, so an archived product stayed orderable and a sold-out bag showed "En stock" (`20d0e67`) | Browsers revalidate on every load (ETag, 304 when unchanged). Checked: shop order with promo = identical server order; stock, price, sold out at the till, cancel and archive appear at once |
| Customer order tracking showed raw codes (`ready_for_shipment`), put cancelled orders at "Reçue", could show a deleted order from the browser copy (`db71fac`) | Clear status in FR / AR / EN, red notice for cancelled / returned, server answer always wins, public fields only |
| Concurrency (6 simultaneous buyers of the last unit, online / till / mixed, PostgreSQL) | Exactly one sale, others refused in French, stock never negative — no change needed |

All 300 tests pass on SQLite and PostgreSQL 16 (the 4 `@babel/core` ones with the substitute compiler).

---

## 19. Full browser test suite and clean code

**End-to-end suite** (`e2e/`, Playwright, `npm run test:e2e`): starts its own fresh production-mode API
(random secrets, empty SQLite or PostgreSQL database), the CMS and the shop on separate ports, then drives
both in a real browser. 28 tests, ~1.5 min, green on SQLite **and** PostgreSQL 16, and a required CI job:

| Spec | What it proves |
|---|---|
| first installation | setup wizard creates the owner, cannot run twice, empty shop, wrong password refused, owner creates a cashier |
| catalogue | product created in the CMS editor (price, variant, stock, photo) is on sale in the shop; archive removes it at once |
| shop | home, AR/EN, product, cart, phone validation, promo checkout = server order, stock reserved, tracking, sold out |
| CMS operations | order statuses (cash on delivery, cancel restores stock), till sale with change / refund / close short, damaged-stock loss, unpaid expense then paid |
| CMS finance | supplier purchase (landed cost, debt, bank), every report CSV, Comptabilité = Analytique + its 3 CSV, cashier refused |
| all screens | every CMS screen × FR/EN/AR × owner/cashier: no crash, console error, refused call or broken text |

Every test fails on a page crash, a console error or an unexpected failed API call.

Found while building it: product-editor and login labels were not linked to their fields, the category picker
and variant buttons had no accessible name / pressed state (fixed: screen readers and tests can use them).

**Clean code:** backend lint clean (incl. unused imports / variables); CMS now compiles with
`noUnusedLocals` + `noUnusedParameters` (56 unused imports, states and handlers removed — including three
lists fetched at every login and never shown); no debug output, no TODO/FIXME; stale comments fixed; the
login brute-force limit is a setting (`LOGIN_ATTEMPTS_PER_MINUTE`, default 5, never above 30); original specification notes
moved to `docs/specs/`, Windows helpers to `scripts/windows/`; the Windows-only Chrome script replaced by
the suite; README updated. Not removed: 12 photos in `apps/storefront/public/assets` that nothing
references (~16 MB, e.g. `store_photo_01…04.jpg`, `01…05.jpg`) — they look like the owner's real shop photos.

---

## 20. Sized for the real server (1 vCPU, 2 GB RAM, 40 GB disk) + backups on the owner's PC

| Risk on this server | Change |
|---|---|
| Nightly **full** photo archive kept 30 days: 30× the photos, more than 40 GB | Photos archived only when they change, newest 3 kept (never pruned by age); database 30 days; under 15 % free disk photos are skipped, under 7 % dumps older than 7 days are removed; warnings and `disk_free_pct` in `last_backup_status.json` (tested by running the script: unchanged photos, low disk, keep 3) |
| Backup snapshot built entirely in memory in the 256 MB API container | Streamed table by table (server-side cursor on PostgreSQL): **1.5 MB peak instead of 38 MB** for the same data; test guards it |
| Phone photos stored at full size (3–12 MB, with GPS in the camera data); 5 MB limit refused many | Uploads up to 15 MB are turned upright, stripped of metadata, reduced to 1600 px and saved as JPEG (WebP if transparent): a few hundred KB; huge PNG/WebP refused (memory); nginx allows 16 MB only on the upload route |
| A **restore** read and parsed the whole backup in memory (~18 MB for 30 000 rows, growing with the shop): the disaster-recovery path could crash the 256 MB API | Backup format v2 (one JSON line per row, tables in restore order): restore checks the whole file first (a truncated or damaged file never empties the database), then streams rows in batches of 500 — **1.7 MB peak**; old v1 backups still restore (tests) |
| Every shop visitor's once-a-minute refresh rebuilt the product list | Shared 5 s server cache for products / categories / delivery prices, emptied by any change (4× less work per visit with 4 products, more with a real catalogue); a CMS change is still visible on the next request (test) |

**Copies on the owner's PC** (requested): the desktop CMS copies the newest backup to
`Documents\\Mus Luxury\\Sauvegardes` 20 s after the owner logs in and every 6 h (newest 60 kept); *Copier sur ce PC*
per backup; *Copies sur ce PC* list with *Renvoyer au serveur*; send back from a file. Server side: download is owner
only, **encrypted files only**, audited; an import must decrypt with this server's key and be a store backup (junk,
tampered, other-key files refused); nginx allows 110 MB only on that route. Browser spec `07-backups` covers the cycle.

Also fixed from the code review of the test suite: `test:shop` / `test:cms` selected no tests; a single spec could
not log in on its own (now creates its accounts); CI retries ran on half-changed data (off); the test login limit
could be copied to production (setting now capped at 30, nginx keeps 5/min in front); accounting test safe across a
month boundary; secret-scanner exemption reduced to the two test passwords; API launcher reports a crash as a
failure and runs on older Node 20; CI caches npm and Chromium. And in *Achats*, a product without a cost no longer
pre-fills an invented 2 500 DA.

---

## 21. No invented delivery prices, hours and Maps link from the CMS, lighter compression

| Before | Now |
|---|---|
| The shop page carried a built-in price list for the 69 wilayas (invented amounts). Before the server's prices arrived — or if that call failed — the product page, the tariff table, the checkout cards and the wilaya list showed those amounts | The built-in list keeps only geography (codes, names, communes). Until the real prices (CMS → Livraison & Wilayas) arrive, the shop shows « Tarif en cours… » and totals « … + livraison »; a method switched off shows « Indisponible », a free delivery « Offerte ». The server always computes the fee of the order, and the confirmation shows the server's totals (browser test: prices from the server; price list blocked → no figure) |
| Opening hours written in the page | CMS → Contenu → *Horaires d'ouverture* (one line per day, « Vendredi : Fermé » highlighted); without a saved value the page keeps its current hours (browser test) |
| Google Maps links fixed in the page; `store_maps_url` stored but unused | CMS field *Lien Google Maps de la boutique*; every Maps link of the shop follows it (short `maps.app.goo.gl` links work) |
| « Copier l'adresse GPS » copied a fixed text | Copies the address set in the CMS |
| API compression: level 9 on the single CPU, compressor never closed for small answers (« I/O operation on closed file » in the logs), 100 MB encrypted backup downloads compressed for nothing | Level 6 (as nginx), compressor always closed, downloads sent as they are (tests; no warning left in the e2e server log) |
| Refused script/link in a setting answered in English | French message |


## 22. Operations check: HTTPS renewal and a health check that tells the truth

| Found | Fixed |
|---|---|
| The HTTPS certificate was copied into nginx **once**; renewal used certbot *standalone*, which cannot work while nginx holds port 80, and nothing copied a renewed certificate or reloaded nginx → browser security error on day 91 | `infrastructure/scripts/certificates.sh setup`: first certificate, then renewals by *webroot* through the running nginx (`/.well-known/acme-challenge/` on port 80, `/var/www/certbot` mounted read-only), hook copies the files and **reloads** nginx; stable copy `/usr/local/sbin/luxe-certificates` (release folders are pruned); `check` warns under 14 days. Tested locally with the real nginx.conf: challenge served, missing → 404, `../` cannot escape, everything else → HTTPS |
| `health-check.sh` called plain HTTP: port 80 only redirects, so on a healthy server it reported 2 failures (shop page and a product route that does not exist) | Goes through the local nginx over HTTPS with the real domain (`--resolve`, never through a proxy): API, readiness (database), products, shop page, HTTP→HTTPS, certificate days, disk use. Tested: healthy stack → 7/7 OK; API stopped → 3 failures, exit 1 |
| Shell scripts only syntax-checked in CI | `shellcheck` (warnings + errors) on every infrastructure script in CI; all clean today |

Checked and fine: client IP behind nginx (every route that is rate-limited gets `X-Real-IP` from nginx, so a
customer cannot fake their address to dodge the login limit), Docker log rotation (10 MB × 3 per container),
container memory limits (~610 MB in total on the 2 GB server).


## 23. Tested as a customer on a phone, in French and Arabic

Phone screen (390 px), full journey home → product → cart → order: no sideways scrolling, buttons reachable,
order placed, no console error — in both languages. Found and fixed:

| Found (Arabic) | Fixed |
|---|---|
| **Prices read backwards**: "9 500 DA" displayed as "DA 500 9" (right-to-left text reorders the groups) — on the product page, cart, totals, delivery prices | Prices in Arabic are one left-to-right block (invisible Unicode isolate marks + no-break spaces, so "10 000 DA" never splits across lines); same for "+ 500 DA", "- 1 200 DA", the order number and the phone |
| The whole order path was French in the Arabic shop: cart, delivery form, delivery choice, totals, confirmation, error messages, product-page delivery box and tabs | Translated (Arabic + English) with a small `L(fr, ar, en)` helper; wilaya names in Arabic; French unchanged word for word |
| Promo field suggested "ex: BIENVENUE10" — a demo code that no longer exists | "Code promo (facultatif)" |
| Customer's name / commune inserted unescaped in the confirmation | Escaped |
| Form fields without linked labels or phone keyboard hints | Labels linked, `autocomplete` and phone keypad on mobile |

New browser test: *shop in Arabic on a phone* (prices in reading order, Arabic form and confirmation, no
sideways scrolling). Still French in the Arabic shop: information pages (FAQ, returns…), footer, order tracking.


## 24. Stock under simultaneous sales

Customer orders, POS sales and stock-outs already change the stock with one conditional update ("subtract only
if enough is left"): two customers can never both buy the last bag. Two places still read the stock and then
wrote a total — a sale committed in between would have been undone (one bag too many shown, then oversold):
**supplier receipt** (now adds the quantity in place) and **applying an inventory count** (now locks the row before
reading). Checked on PostgreSQL with 20 orders and 5 receipts fired at the same time on one product: all accepted,
final stock exactly 100 − 20 + 50 = 130, no error or deadlock in the server log.


## 25. Deploy rehearsal: two bugs that would have stopped the first real deploy

The release script was run for real in the cloud sandbox (Docker), as the CD workflow runs it on the VPS, with a
throw-away production `.env` made by the project's generator. Docker Hub then refused image downloads from the
sandbox (*429 Too Many Requests*, shared address), so the end of the rehearsal was finished with a small stand-in
stack using images already present. Found and fixed:

| Found | Effect on the real server | Fixed |
|---|---|---|
| The deploy and the **nightly backup** read the production `.env` with bash (`set -a; . .env`). The generated file holds `<FILL_IN_…>` placeholders and passwords with `? # & ;` | Deploy stops at "syntax error near unexpected token"; **every nightly backup fails before starting** | `infrastructure/scripts/env-file.sh` reads it like Docker (values literal, quotes, comments, CRLF); used by the deploy and by the new `infrastructure/backups/nightly_backup.sh` (both cron installers now call it). Tested with placeholders, special characters and a `$(…)` value: nothing executed |
| Docker Compose named the project after the folder: migrations ran in `releases/<version>` (project *<version>*), the start in `current/` (project *current*) | **First deploy fails** (second `luxe_postgres` container: name clash); each project has its own, **empty**, database volume | `infrastructure/scripts/compose-project.sh`: one `COMPOSE_PROJECT_NAME` in `shared/.env` for every release (Compose reads it for every command, manual ones too). Missing → keeps the project of the database already running, else `luxe`. Refuses to start when its database volume is missing but another shop volume exists. Reproduced, then checked: new server, server already running under another name (data kept), wrong name (refused) |
| Rollback restarted with the images of the release being rolled back | Rollback would keep the faulty code | Rollback (and the deploy's automatic rollback) rebuild the target release (`--build`, cached layers) |
| Old images and build cache never removed | 0.5–1 GB more on the 40 GB disk at each deploy | Removed after each successful deploy (images in use and data volumes untouched) |
| API image installed `gcc` + `libpq-dev`; shop image used `npm install` | ~200 MB per image, slow builds on 1 vCPU; builds not reproducible | Removed (every Python dependency has a ready-made wheel for Python 3.11 / Linux — checked); `npm ci`; CI now starts the built API image and loads its libraries |

**On a server that is already running:** after the next deploy, run `sudo bash infrastructure/backups/install_backup_cron.sh`
once (from `/opt/luxe/current`) so the nightly backup uses the new safe loader.

Also: Arabic order tracking (window, messages) translated; the order-tracking code no longer hides the `L()` helper.


## 26. CI was red — seven causes, all fixed

CI had been failing on this branch for several pushes while everything passed in the cloud container, because
the container had older packages than a fresh CI machine. Found from the CI logs and fixed:

| CI job | Cause | Fix |
|---|---|---|
| Backend tests (PostgreSQL) — all 37 test files | `httpx` 0.28 (installed fresh in CI) removed the `app=` argument that Starlette 0.25's test client uses | `httpx>=0.23,<0.28` in requirements |
| Backend tests (SQLite) | The migration runner on an **empty** database marked the base schema as applied without creating it → "no such table: product_variants". Same would happen on any brand-new database run through the runner | The runner creates the base tables first when they are missing (checked on empty SQLite and empty PostgreSQL) |
| Dependency audit | Vite 5 / esbuild advisories (development server only: path traversal, cross-origin requests) and `zod` — an unused CMS dependency | Vite 7 in the shop and the CMS (both build, e2e 33/33 on it); `zod` removed; `npm audit` = 0 for both |
| Lint (actionlint) | The `raven-actions/actionlint` wrapper installs `@actions/tool-cache` into the workspace; its newest version cannot be `require()`d — the step crashed before linting | Official `rhysd/actionlint:1.7.12` image run directly |
| Backend tests (PostgreSQL), 1 test | `test_74` ran the backup script against `backend/luxe_store.sqlite3`, a local dev file absent on a fresh machine | The test makes its own small database for the script |
| Lint (actionlint, once it really ran) | Unused loop counters `i` in the production and staging deploy workflows | `_` |
| End-to-end (tests green, job red) | `setup-python` asked to cache pip while installs used `--no-cache-dir` → the cache folder never existed and saving it failed | `--no-cache-dir` removed in the three jobs that cache pip |


## 27. Arabic shop: information pages and footer

- **Information pages (À propos, FAQ, Livraison & retours, Conditions)**: the starter content copied the
  *French* text into the Arabic and English fields — Arabic customers read French laid out right-to-left, and in
  the CMS the Arabic field looked already translated. New shops now get real Arabic and English texts; existing
  shops are repaired at the next start, **only where the field still holds that exact French starter text**
  (anything the owner wrote is never touched). Test: repaired once, owner text kept.
- **Footer** in Arabic and English (headings, links, slogan): page texts marked `data-t-ar` / `data-t-en` are
  swapped by the language switch (French kept to switch back). The Arabic phone test checks it.


## 28. Load test: two years of a busy shop

A PostgreSQL copy filled with 20 000 customers, 60 000 orders (120 000 lines), 100 000 audit entries, 60 000
treasury movements and 80 000 stock movements; every daily screen timed through the API:

| Screen | Before | After |
|---|---|---|
| **Clients** | **never loaded** (over 2 minutes): total spent / order count re-read all orders for each customer, and `orders.customer_id` / `pos_sales.customer_id` had no index | **45 ms**: indexes (migration 005, both engines), totals computed once per table, list in pages of 200 (best customers first, *Afficher plus*; search still finds anyone) |
| Client search | (same cause) | 30–140 ms |
| Trésorerie — mouvements | 470 ms, every movement since opening loaded into the 256 MB API to compute running balances | 105 ms: running balances computed by the database (window function), only the rows shown are read — checked identical to the old figures on 60 000 movements, cash and bank |
| Dashboard, Analytique, Commandes, Journal d'audit, Comptabilité, stock screens, all reports over a full year | — | 5–150 ms (no change needed) |
| **Commandes — finding an older order** | impossible: the screen shows the newest 100 (per status) and had no search | Search box (Entrée): order number, phone (spaces ignored) or name (any case), with or without the status filter; 90–180 ms over 60 000 orders. The automatic refresh no longer replaces search results. Tests: backend + browser |


## 29. Public routes under hostile input (fuzzing)

About 40 odd or hostile requests to the routes anyone can call (products, categories, delivery calculator,
order tracking, pages, order form: wrong types, huge values, 1 000 lines, 100 000-character address, HTML,
SQL-looking text, NUL and invisible characters), on SQLite and PostgreSQL. All got clean 4xx answers except:

| Found | Fixed |
|---|---|
| A NUL character (`%00` in the address, `\u0000` in the order form) → **500** on PostgreSQL ("cannot contain NUL") | Refused before any route with a 422 in French (address, query string, JSON body; uploads never read). 0 server errors after the fix |
| Invisible text-direction override characters (U+202E…) accepted in names — can disguise a name in the CMS and on receipts | Removed from name, commune, address and notes |
| Three order-form validation messages in English | French |
| The shop's error messages (wrong details, stock, too many tries, not found, service down) only in French | In the customer's language (FR/AR/EN) |

Test file `test_input_hygiene.py` (NUL, override characters, French message, uploads unaffected).


## 30. CMS architecture: App.tsx was doing everything

`App.tsx` was 3 047 lines: the shell *and* five whole screens. Now it is the shell (setup, login, session,
workspace loading, layout, sidebar, notifications, shared catalogue/order actions) and every screen is a
file in `pages/`:

| Screen | Now | Data |
|---|---|---|
| Tableau de bord | `pages/DashboardPage.tsx` | from App (props) |
| Produits | `pages/ProductsPage.tsx` (list, search, tabs, bulk actions; derived list moved with it) | from App (props) |
| Stock | `pages/InventoryPage.tsx` | from App (props) |
| Commandes | `pages/OrdersPage.tsx` | from App (props) |
| Contenu & Bannières | `pages/ContentSettingsPage.tsx` | **loads and saves its own** (no longer fetched by every workspace refresh) |

`App.tsx` 3 047 → 1 682 lines; behaviour unchanged — checked after each step: TypeScript clean, browser tests
34/34, backend 315/315 (including the four tests that compile the CMS sources). New guide:
`apps/desktop-cms/ARCHITECTURE.md` (folders, data flow, permissions, `utils/` by theme, how to add a screen).


## 31. Keys and invented text — audit

**Keys and tokens.** No real secret anywhere in the repository (patterns for API keys, tokens, private keys;
only `.example` files with placeholders; `scratch/production.env` is git-ignored; gitleaks runs in CI). The
server has no fallback secret: production refuses to start without a strong `SECRET_KEY`. One gap closed: with
`LUXE_SEED_DEMO_ACCOUNTS=1` (offered by the generator's comment) a production server would have created the
owner and an editor account with the **development passwords published in this repository**. Now production
creates such an account only with a strong configured password (12+ characters, not a placeholder, not a
development one); otherwise it is not created and an error is logged (test `test_seed_accounts.py`).

Still to fill in by the owner (left as placeholders on purpose — the features stay off until then): delivery
companies (Yalidine, ZR Express, Maystro), Chargily online payment, off-site backup storage (S3), e-mail (SMTP).

**Invented text.** The shop showed promises nobody had decided and the system does not support — a liability
if a customer holds the shop to them:

| Was | Now (what the shop really does) |
|---|---|
| « Produits authentiques & vérifiés », « Authenticité & Contrôle 100 % — pièces expertisées » | Échange sous 7 jours, dans l'emballage d'origine |
| « Click & Collect sous 1 h » (no pick-up option exists in the checkout) | Confirmation par téléphone avant l'expédition |
| « Écrin Signature Offert… ruban doré prestige » | Paiement à la livraison dans les 69 wilayas |
| « Conseil & Stylisme Privé sur-mesure » | Commande sans compte (site ou WhatsApp) |
| « Toujours à votre écoute 7j/7 » | Par téléphone et WhatsApp |
| « Sélection certifiée », « Photographie certifiée », La Maison intro (« haute horlogerie, châles nobles… ») | Plain description of the shop |
| Starter pages: « Sélection certifiée », fixed delivery times « 24h-48h / 48h-72h » | Factual text; delays depend on the wilaya. Existing shops upgraded only where the text is still the generated one (owner text never touched; test) |

All new texts in FR / AR / EN. The owner can of course make real promises later — as a decision, in the CMS.


## Verification

| Check | Result |
|---|---|
| Backend tests | 308 run on SQLite and on PostgreSQL 16 (incl. the end-to-end business day, round 18). Only 4 failures, all caused by `@babel/core` missing in the cloud container; those 4 pass with a substitute TypeScript compiler and pass in CI. |
| CMS TypeScript + build | OK |
| Rust (`cargo check`) | OK |
| Browser tests (Playwright) | `e2e/`: 33 shop + CMS tests green on SQLite and PostgreSQL 16 (CI job). Earlier manual checks — notifications, message box queue, bell, update dialog, new-order alert, Arabic layout, category delete + reload, archived tab, database panel, backup, reset: all OK |
| Backup engine | SQLite, PostgreSQL 16, and PC → server restore: OK |
| VPS backup scripts | Backup, verify, native restore and snapshot restore, tested through a Docker stand-in against PostgreSQL 16: OK |

**Not tested yet:** the real VPS (no access from here), the PowerShell key script (no PowerShell
here), and real Windows notifications or an update install on a Windows PC.

---

## What the owner still needs to do

1. Run `setup-github-secrets.ps1` once (see §9), then back up the signing key files to a USB key.
2. Switch on the off-site backup copy (`S3_*` values + `S3_BACKUP_ENABLED=true`, guide §5.4).
   Until then, backups live on the same server as the shop. This is the most important remaining risk.
3. Keep a copy of `BACKUP_ENCRYPTION_KEY` in a password manager.
4. After the first deploy, do the 15-minute restore drill (guide §9).
