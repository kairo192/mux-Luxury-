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

Still to do (Step 2): every page readable by Google (real page addresses instead of `#/`), search
descriptions and sharing previews, sitemap, Arabic translation of a few labels ("Tarifs 69 Wilayas",
banner caption), and removing the unused React copy of the shop in `apps/storefront/src`.

---

## Verification

| Check | Result |
|---|---|
| Backend tests | 249 run (7 new for backups/categories). Only 4 failures, all caused by `@babel/core` missing in the cloud container; those 4 pass with a substitute TypeScript compiler and pass in CI. |
| CMS TypeScript + build | OK |
| Rust (`cargo check`) | OK |
| Browser tests (Playwright) | Notifications, message box queue, bell, update dialog, new-order alert, Arabic layout, category delete + reload, archived tab, database panel, backup, reset: all OK |
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
