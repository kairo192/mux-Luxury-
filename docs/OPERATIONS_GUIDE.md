# Mus Luxury — Operations Guide

*For the owner and the people who run the shop. No programming needed.*
*Last review: 11 November 2026.*

---

## 1. The system in one picture

```
   SHOP PCs (Windows)                    THE SERVER (VPS, in the cloud)                 CUSTOMERS
 ┌──────────────────────┐   internet   ┌──────────────────────────────────────┐   ┌──────────────────┐
 │ Mus Luxury CMS app   │ ───────────► │  API  ──►  DATABASE (PostgreSQL)     │ ◄─│ mus-luxury.com   │
 │  • back office       │ ◄─────────── │   │        the ONE source of truth   │   │ (online shop)    │
 │  • POS / till        │              │   └──► product photos                │   └──────────────────┘
 │  • offline copy of   │              │  Nightly backups (03:30)             │
 │    the catalog       │              └──────────────────────────────────────┘
 └──────────────────────┘                          ▲
            ▲                                       │ new website versions
            │ new CMS versions (signed)             │
            └──────────── GITHUB (code, automatic builds, releases) ─────────┘
```

**The rule to remember:** the database on the server is the only master copy.
The shop PCs and the online shop *read from it and write to it*. Nothing that
matters is stored only on a PC, except offline sales waiting for the internet
(see §3.3).

---

## 2. Where your data lives

| What | Where | Notes |
|---|---|---|
| Catalog, stock, orders, customers, POS sales, cash, expenses, suppliers, staff accounts | Server database (PostgreSQL 16, Docker container `luxe_postgres`) | Master copy. |
| Product photos | Server (`luxe_api` container, uploads folder) | Public anyway: they are shown on the website. |
| Offline catalog copy | Each POS PC (small local file) | Lets the till find products when the internet is down. Rebuilt automatically. |
| Offline sales queue | Each POS PC | Sales made without internet. Sent to the server automatically when the connection returns. |
| Login session | Windows Credential Manager on each PC | Never stored in plain text. |
| Backups | Server folder `/var/lib/luxe/backups` (+ off-site copy when enabled, see §5.4) | Encrypted. |

A PC can also run the whole system **locally** (for tests or training). It then
uses a single file database (SQLite) instead of PostgreSQL. Everything in this
guide works the same in both cases: backups, restore, and "New database".

---

## 3. How everything stays synchronized

### 3.1 Back office (CMS) → server
Every change in the CMS (a product, a price, a category, an order status) is
saved on the server **immediately**. There is no "publish" step.

Since 11 Nov 2026 the CMS never shows an old cached list. It always asks the
server for fresh data. This fixed the "deleted categories come back after a
reload" problem (§7, incident 1).

### 3.2 Server → online shop
The website re-reads the server every 4 seconds while a customer has it open.
Short caches keep the server fast:

| Data | Visible on the website after a change |
|---|---|
| Categories | within 30 seconds |
| Products / prices / stock | within 60 seconds |
| Wilayas & delivery prices | within 1 hour (they almost never change) |

### 3.2b The shop on Google and in shared links
* Every product has its own address: `mus-luxury.com/produit/<name>`, and every
  category too: `mus-luxury.com/categorie/<name>`. Copy it from the browser to
  share it on WhatsApp, Instagram or Facebook: the preview shows the product's
  photo, name and price.
* Google finds every page through `mus-luxury.com/sitemap.xml`, which updates by
  itself. **Once, after the launch:** add the site in Google Search Console
  (search.google.com/search-console) and submit `https://mus-luxury.com/sitemap.xml`.
* Better previews and search results come from good content in the CMS: a clear
  product name, a 1–3 sentence description, and a real photo.

### 3.2c Creating a product (CMS → Produits → Nouveau produit)
1. **Informations**: category, name (FR, and AR/EN if you can), description, prices. The SKU and the
   web address fill themselves from the name; change them if you want.
2. **Visuels**: the main photo, then more photos in the gallery.
3. **Déclinaisons**: tick the colours/sizes, click **Ajouter … combinaison(s)**, set the stock. In the
   **Photo** column, give each colour its own photo if you have one.
4. Check the preview on the right: **Carte** = how it looks in the shop grid, **Page produit** = what
   the customer reads; switch **FR / ع / EN** to check each language. Follow the
   **"Prêt pour la boutique ?"** list.
5. Set **Statut = Publié** and save. Use **Copier le lien boutique** to share it.

### 3.2d The home page, banners, contacts (CMS → Contenu & Bannières)
Everything the customer sees on the home page is set here; nothing is fixed in the shop's code.
- **Blocs de la page d'accueil**: switch on/off the big banner, the guarantees bar, the categories,
  the products, the promotion cards.
- **Bannière principale** (top of the home page): title and text in FR/AR/EN, button text, photo, and
  where the button leads (the whole shop, a category, a product, or an https:// link). Several
  banners rotate every 7 seconds. With none, the brand text is shown.
- **Carte promo** (e.g. "-20 % sur les sacs"): same fields. With none, the block disappears. A promo
  card only *announces* a promotion: to really lower prices, change the product's price / old price
  (Produits) or create a **Code promo** (same tab).
- Eye icon = hide without deleting; arrows = order.
- **Coordonnées de la boutique**: phone, WhatsApp, address, Instagram, TikTok, and **Livraison
  gratuite à partir de (DA)**. The threshold is applied by the server on every order; `0` = no free
  delivery (the shop then stops announcing it).
- **Pages d'information**: À propos, FAQ, Livraison & retours, Conditions, in FR / AR / EN.

Changes appear on the shop within about a minute (the shop checks every 60 seconds).

### 3.3 Server ↔ POS PCs
* **Catalog:** each till downloads the full catalog the first time, then only
  the changes, every time the CMS starts and every time the internet comes back.
* **"New database" / restore:** the server gives the catalog a new "edition
  number". Every till that sees a new number throws its offline copy away and
  downloads the catalog again, so deleted products do not survive on a till.
* **Offline sales:** a sale made without internet is kept in the till's queue
  and sent automatically when the connection returns. The cashier gets a
  notification: "Ventes hors-ligne synchronisées". If the server refuses a sale
  (for example, stock already sold online), it is flagged as a **conflict** to
  check in the Point de vente.

### 3.4 New online orders
The CMS checks for new website orders **every 45 seconds**. A new order shows
a pop-up with a **Voir** button. If the CMS window is in the background, a
**Windows notification** appears and the taskbar button flashes.

---

## 4. Updates — how the system updates itself

There are two kinds of update, both started from GitHub. Nobody copies files
by hand.

### 4.1 Website + server
1. A change is merged into the `main` branch → automatic tests run.
2. It is deployed automatically to the **staging** server (a test copy).
3. A version tag (`v1.2.0`) deploys to **production**. Before anything
   changes, the deploy takes a **full backup** (database + photos), then
   upgrades the database structure, then switches to the new version.
4. If the health check fails after the switch, the previous version of the
   **program** comes back automatically (rollback). Database structure changes
   are not undone automatically: the backup from step 3 is the way back
   (§5.3).

### 4.2 Shop PCs (CMS / POS app)
*Requires the one-time key setup in §8.2; until then, installers are built
unsigned and the PCs do not look for updates.*

1. The same `v1.2.0` tag builds a **signed** Windows installer and publishes it.
2. Every shop PC checks for an update **15 seconds after the CMS starts**,
   then **every 4 hours**.
3. When an update exists, the version chip in the header turns gold, a pop-up
   offers **Installer et redémarrer**, and Windows shows a notification.
4. The install happens **only when someone clicks**. This is deliberate: an
   update never interrupts a sale. If offline sales are still waiting, the CMS
   warns first. They are kept and sent after the restart.
5. The PC only accepts installers signed with the Mus Luxury key. A fake
   installer is refused.

> Turning a PC off and on is enough to pick up updates: the check runs at
> every start.

---

## 5. Backups

### 5.1 What is backed up, and when
| When | What | Who triggers it |
|---|---|---|
| Every night at 03:30 | Full database (native PostgreSQL copy) + all photos + a "CMS snapshot" | Automatic (server) |
| Before every production deploy | Same full set | Automatic |
| Before every **restore** or **New database** | CMS snapshot ("Avant restauration" / "Avant remise à zéro") | Automatic |
| Any time | CMS snapshot (+ photos if ticked) | Owner: **Sauvegarder maintenant** |

### 5.2 Protection
* **Encrypted** with AES-256 using the server's backup key. A stolen backup
  file cannot be read.
* **Checksums** (SHA-256) detect a damaged file before any restore.
* Every night a **verification** restores the latest backup into a temporary
  database, counts the rows, then deletes the temporary copy. A backup that
  cannot be restored is reported at once, not on the day you need it.
* Kept **30 days**. The **10 most recent** are always kept, whatever their age.
* Backup files never travel over the internet from the CMS. There is no
  download button, so a stolen password cannot leak the database.

### 5.3 Restoring (owner only)
**CMS → Sauvegardes & Sécurité → Base de données & sauvegardes**
1. Choose a backup in the list → **Restaurer**.
2. Type `RESTAURER` and your owner password.
3. The CMS first saves the current state ("Avant restauration"), then replaces
   everything in one go. If anything goes wrong, nothing is changed.
4. The CMS reloads. Tills refresh their catalog automatically.

To undo a restore, restore the "Avant restauration" copy.

### 5.4 Off-site copy — the one setting still to switch on
Today all backups sit on **the same server** as the shop. If the VPS provider
loses the machine, the backups are lost with it. Enable the off-site copy:

1. Create a storage bucket at any S3-compatible provider (Backblaze B2,
   Wasabi, Scaleway, OVH…; a few euros per month).
2. Put the 5 values in the server `.env`: `S3_ENDPOINT_URL`, `S3_REGION`,
   `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and set
   `S3_BACKUP_ENABLED=true`.
3. The next night's backup is copied there automatically, already encrypted.

Until this is done, the CMS backup page shows a yellow warning.

---

## 6. "New database" — starting clean

**CMS → Sauvegardes & Sécurité → Nouvelle base de données → Créer une base vide**
(owner only: type `EFFACER` + owner password)

| Erased | Kept |
|---|---|
| Categories, products, variants, photos links | Staff accounts and roles |
| Stock and stock movements | Registered POS devices |
| Online orders, customers, blacklist | The 69 wilayas + delivery prices |
| POS sales, cash sessions, expenses, accounting | Legal pages (CGV, FAQ…) |
| Suppliers, purchase orders, inventory counts | Shop settings & homepage layout (box ticked by default) |
| Coupons, banners, audit history | |

* A full backup ("Avant remise à zéro") is taken **just before**. You can undo
  with one click (§5.3).
* Numbering restarts at 1 (first new category = #1).
* The tills drop their offline catalog automatically.
* You stay logged in. The shop keeps working immediately, just empty.

Demo products are **never** re-created automatically any more, neither on the
server nor on a PC.

---

## 7. Incidents found and fixed (11 Nov 2026 audit)

| # | What the owner saw / what could happen | Real cause | Fix |
|---|---|---|---|
| 1 | Deleted categories **came back after a reload**, "sometimes" | The CMS read categories from the public website list, which browsers may keep for 5 min. A reload within 5 min showed the old list. | CMS always asks for fresh data; categories read from the admin list; website cache cut to 30 s. |
| 2 | "Deleted" categories could not be found or restored | Default delete = archive, but archived items were invisible in the CMS | New **Archivées** tab with **Restaurer** / **Supprimer définitivement**. |
| 3 | The 9 demo categories re-appeared on a PC | (a) A development PC re-created the demo shop each time its database file was new. (b) A helper script `restore_demo_products.py`, if run on an empty shop, **deleted all staff accounts** and re-created the demo. | Demo only for automated tests; dangerous script removed. |
| 4 | **Nightly server backups would have been empty** | The backup ran outside Docker. It could not reach PostgreSQL, fell back to SQLite, created an empty file and backed that up as "success". The same script ran before every deploy. | Backups go through Docker (`docker exec`), refuse an empty database, and record their status. |
| 5 | Backup job could not write its folder | Folder owned by `root`, job running as `luxe` | Folder now belongs to the backup user. |
| 6 | A restore on the server would have gone to the wrong place | Restore script had the same problem as #4 | Restores into the Docker database, pausing the API, all-or-nothing. |
| 7 | Nightly verification could never succeed on the server | Needed tools that are not on the server | Verifies inside the database container, in a temporary database. |
| 8 | Off-site upload could send an incomplete set | Picked files by "newest timestamp" | Uploads exactly the files listed in the backup's checksum file. |
| 9 | Backup errors were not logged | Only the last step's output reached the log | The whole chain is logged (`/opt/luxe/logs/backup.log`). |
| 10 | Tills kept selling deleted products after a reset | Tills only received changes, never removals | Catalog "edition number" forces a full refresh (§3.3). |

**Remaining risks (honest list)**
* No off-site copy until §5.4 is done. This is the most important item.
* The new backup chain was tested end-to-end on PostgreSQL 16 here, but has
  not yet run on the real VPS. After the first deploy, do the **restore
  drill** in §9 once.
* A restore replaces the **whole** database. To recover a single deleted
  product, restore, then re-enter today's other changes. Plan restores outside
  shop hours.

---

## 8. Keys and passwords — status

### 8.1 Generated automatically (nothing to do)
Created with a cryptographic random generator by
`python3 backend/scripts/generate_production_env.py`. They are in the private
production `.env`, which is **never** stored in GitHub (the repository is
public):

`SECRET_KEY` · `CMS_HMAC_SIGNING_SECRET` · `POSTGRES_PASSWORD` / `DATABASE_URL` ·
`BACKUP_ENCRYPTION_KEY` · `ADMIN_INITIAL_PASSWORD` · `ADMIN_EMERGENCY_RECOVERY_CODE` ·
`WHATSAPP_WEBHOOK_VERIFY_TOKEN`

> Keep a copy of `BACKUP_ENCRYPTION_KEY` outside the server (a password
> manager). Without it, encrypted backups cannot be opened.

### 8.2 GitHub keys — one command on your PC
App-update signing key + deploy key, created **on your PC** so they never pass
through a chat or a cloud machine:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure\scripts\setup-github-secrets.ps1 -VpsHost <IP of the VPS>
```
It creates the keys, stores them in GitHub (secrets + variables) through the
GitHub CLI, and prints the one public line to give to the VPS. Then back up
`%USERPROFILE%\.tauri\mux_luxury.key` and its `.password` file to a USB key
kept in a safe.

### 8.3 Only you can obtain these (accounts in your company's name)
Left as `<FILL_IN_…>` in the production `.env`. **The shop works without
them**: each feature simply stays off until you add its key.

| Value | Where to get it | Without it |
|---|---|---|
| `S3_*` (5 values) | Your storage provider (§5.4) | No off-site backup copy. **Recommended.** |
| `YALIDINE_API_ID/TOKEN` | Yalidine merchant account → API | Shipments are booked by hand |
| `ZR_EXPRESS_API_KEY/TOKEN` | ZR Express merchant account | Same |
| `MAYSTRO_API_TOKEN/STORE_ID` | Maystro Delivery account | Same |
| `CHARGILY_PUBLIC/SECRET/WEBHOOK` | Chargily Pay dashboard (CIB / Edahabia) | Customers pay cash on delivery only |
| `SMTP_PASSWORD` | Your e-mail provider (app password) | No automatic e-mails |
| `WHATSAPP_*` (Cloud API) | Meta Business → WhatsApp Cloud API | WhatsApp messages open as click-to-chat links (works today) |

---

## 9. Routine checklist

**Every day (10 seconds):** the "En ligne" indicator in the CMS header is green
and the bell shows no unread error.

**Every week:** CMS → Sauvegardes & Sécurité: "Dernière sauvegarde" is from
last night, with no yellow warning except the off-site one (until §5.4 is done).

**Once after the first deploy, then every 3 months — restore drill (15 min):**
1. **Sauvegarder maintenant**.
2. Create a test category "TEST-RESTAURATION".
3. Restore the backup from step 1 → the test category must be gone.
4. Note the date of the drill.

**Server commands (for the technician)**
```bash
docker exec luxe_api python -m app.backup_cli info        # status
docker exec luxe_api python -m app.backup_cli create --kind manual --media
docker exec luxe_api python -m app.backup_cli list
docker exec luxe_api python -m app.backup_cli restore <name> --yes
bash infrastructure/backups/restore_backup.sh /var/lib/luxe/backups/luxe_db_<ts>.sql.gz.enc /var/lib/luxe/backups/luxe_backup_<ts>.sha256
tail -50 /opt/luxe/logs/backup.log ; cat /var/lib/luxe/backups/last_backup_status.json
```
