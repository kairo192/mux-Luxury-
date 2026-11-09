# HANDOFF — Mus Luxury (LUXE)

**To:** Claude (next Claude Code session, running on the user's **local** machine)
**From:** Previous Claude Code session (Opus 4.7) — context exhausted
**Date:** 2026-11-09
**Project root:** `C:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce`
**Branch:** `feat/pos-core-cash-register`

---

## 1. Read this first

- **You are not starting fresh.** This codebase has been under heavy continuous work. A second AI (**Antigravity**, running in this same codebase whenever Claude Code hits its usage limit) has been building production features in parallel. Expect new files, new Rust modules, new commits, and uncommitted work in progress every time you return.
- **Your north star is** [`claude code.md`](claude%20code.md) — the full ERP/POS/e-commerce spec (1 148 lines). You and Antigravity are both working through it. Re-read it so you know what is done and what is left.
- **Your working directory is the user's real machine.** Edits ship to a real business. No mockups, no fake test data presented as real, no fake device detection. Follow §19 "Rules for Claude" in the spec.
- **This repo already has `backend/.env`** with a strong `SECRET_KEY` (persisted, git-ignored). Do not regenerate it. If `.env` ever disappears, re-create it per §5 below.

---

## 2. Before you do anything — mandatory discovery

Run these, read the output, then plan:

```bash
cd "C:/Users/MOURAD/Desktop/mix luxury/luxe-ecommerce"
git branch --show-current                   # confirm you're on feat/pos-core-cash-register
git log --oneline -20                       # see Antigravity's recent commits + mine
git status --short                          # see any in-flight uncommitted work
wc -l backend/app/main.py                   # grew from ~5100 to probably much more
ls backend/tests/test_*.py | wc -l          # test file count
ls apps/desktop-cms/src-tauri/src/pos_hardware/  # ESC/POS + ZPL printer modules
ls apps/desktop-cms/src-tauri/src/pos_mirror/    # local SQLite catalog mirror
cat docs/FULL_AUDIT_AND_DEPLOYMENT_DISCOVERY.md  # Antigravity's full audit
```

Then in parallel: `Grep` the backend for new `@app.get` / `@app.post` routes added since you last saw it, and the CMS pages directory for new tabs.

### Critical: handle uncommitted work carefully
If `git status` shows **modified** files you did not touch, **assume Antigravity is mid-task** and those are its work in progress. **Do not commit them, do not discard them, do not run `git reset`.** Look at the diff to understand what they're doing, and either:
- continue a different module that doesn't touch the same files, or
- ask the user whether Antigravity's work is finished and safe to commit.

Untracked files (`??`) that look like clean new features (page, test, doc) are generally safe to leave alone or commit alongside yours if the user asks.

---

## 3. What has been built (as of last known state, commit `11eaccc`)

**Fully implemented and tested** (all with backend tests + CMS UI):
- POS + cash register sessions, offline queue with idempotent sync
- Barcodes (EAN-13/8, UPC-A, Code 128), label printing (ZPL + ESC/POS)
- Devices & hardware registry with real TCP probe
- Customers (walk-in + online, cross-channel history), POS customer attach
- Users & roles (6 seeded roles, backend-enforced perms)
- Suppliers, Purchase orders (receive, pay), Expenses, Treasury
- Inventory counts (physical reconciliation), typed stock write-offs
- Business dashboard, Sales report + CSV, Expense report + CSV
- Inventory movements report + CSV, Treasury report + CSV
- Fiscal settings (NIF/NIS/RC/Article), configurable tax rate
- A4 Invoice (POS), A4 Delivery note (online orders), **A4 Purchase order document** (started, see §6)
- Audit log viewer with filters
- Low-stock alerts with reorder suggestions (velocity-based)
- Tauri native hardware bridge (ESC/POS, cash drawer, HID scanner) — **Antigravity's work**
- Local SQLite catalog mirror (`pos_mirror.sqlite3`) for offline lookup — **Antigravity's work**
- CSP-safe compiled Tailwind, hardened fetch, touch-friendly prompts — **Antigravity's work**

**Still missing from the spec** (highest value first):
1. **Production deployment** — 3 blockers below (§4). This is what the user most needs now.
2. **Arabic / RTL polish** across the new tabs (Part 14). The storefront already supports it; the ~24 new CMS tabs do not.
3. **Devices page: real USB enumeration** now that the Tauri bridge exists — wire the CMS Devices tab to call the bridge's enumeration commands.
4. **Documents**: Devis (quote) and Avoir (credit note for delivered-then-returned online orders).
5. **Automated backups**: logic exists but verify retention policy and off-server copy.
6. **Load test on the real 2 GB VPS** once deployed.

---

## 4. Known production blockers (from `docs/FULL_AUDIT_AND_DEPLOYMENT_DISCOVERY.md`)

Before go-live you MUST fix (ask the user, do not guess):

- **BLOCKER-01 — Domain mismatch.** `nginx.conf` and `main.py` have hard-coded `musluxury.dz`, but the real domain is `mus-luxury.dz` (with hyphen). TLS + CORS + CSP will all fail. Grep and replace after confirming with the user.
- **BLOCKER-02 — Storefront Dockerfile.** `apps/storefront/Dockerfile:6` copies raw `index.html` referencing `/src/index.css`. Must add a Vite `build` stage. The user already has a modified `apps/storefront/Dockerfile` in the working tree — check whether Antigravity already fixed it before you touch it.
- **BLOCKER-03 — Tauri updater key.** `apps/desktop-cms/src-tauri/tauri.conf.json:41` contains the literal placeholder `REPLACE_WITH_BASE64_TAURI_UPDATER_PUBLIC_KEY`. The user must generate a Tauri updater signing key pair and give you the public key; do not fabricate one.

Other things to verify: psycopg connection pooling is not enabled (fine for 2 GB VPS at launch, but mention it).

---

## 5. Configure the production `.env` (the user explicitly asked for this)

The runtime already has a **development** `backend/.env` with a real `SECRET_KEY`. For **production** you need a separate `.env.production` (or the same path on the VPS) with real values. **Do not hard-code secrets into the repo. `backend/.env*` is already git-ignored — verify with `git check-ignore backend/.env.production` before writing.**

Generate the secrets with the existing tool:
```bash
cd "C:/Users/MOURAD/Desktop/mix luxury/luxe-ecommerce/backend"
python scripts/generate_secrets.py          # prints fresh values, nothing persisted
```

Then write `backend/.env.production` with the following keys. Prompt the user for every value marked `<ASK USER>`; never invent them.

```ini
APP_ENV=production

# --- JWT / crypto (from generate_secrets.py) ---
SECRET_KEY=<generated 128-char hex>
CMS_HMAC_SIGNING_SECRET=<generated 128-char hex, DIFFERENT from SECRET_KEY>
BACKUP_ENCRYPTION_KEY=<generated 64-char hex>

# --- Database (PostgreSQL 16) ---
LUXE_DB_ENGINE=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=luxe_ecommerce
POSTGRES_USER=luxe_app_user
POSTGRES_PASSWORD=<generated 36-char alphanum>
DATABASE_URL=postgresql://luxe_app_user:<password>@db:5432/luxe_ecommerce

# --- CORS (production domain) ---
# Fix BLOCKER-01 first — confirm the domain with the user!
CORS_ORIGINS=https://mus-luxury.dz,https://www.mus-luxury.dz,https://api.mus-luxury.dz

# --- WhatsApp Cloud API (admin recovery OTP) ---
WHATSAPP_CLOUD_API_TOKEN=<ASK USER - from Meta Developer Console>
WHATSAPP_PHONE_NUMBER_ID=<ASK USER>
WHATSAPP_APP_SECRET=<ASK USER>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<generated 64-char hex>

# --- Owner seed policy ---
# On first boot the app forces the owner-init wizard. Do NOT set this in prod
# unless the user explicitly wants a pre-seeded owner for testing.
# LUXE_SEED_DEMO_ACCOUNTS=0

# --- Backup ---
BACKUP_DIR=/srv/luxe/backups
UPLOAD_DIR=/srv/luxe/uploads
```

Once the user provides the `<ASK USER>` values, write the file, then check:
```bash
git check-ignore backend/.env.production    # must print the path = it's ignored ✓
```

If `git check-ignore` prints **nothing**, the file is NOT ignored — stop, and add `.env.production` to `.gitignore` first.

---

## 6. In-flight work you may inherit (last known state)

Right before my context ran out I was adding **Partie 6 — Purchase order A4 document**:
- Backend endpoint `GET /api/v1/admin/purchases/{po_id}/document` with full supplier identity + items + totals.
- Test suite `backend/tests/test_purchase_document.py` — 5/5 passing standalone.
- Not yet committed. CMS `PurchaseOrderDocumentModal.tsx` not yet written.

Check `git diff backend/app/main.py` — if the function `admin_get_purchase_order_document` is there with the decorator `@app.get("/api/v1/admin/purchases/{po_id}/document")` AND the test file exists, **you can finish it**:
1. Run the full backend suite: should be ~228 tests green.
2. Create `apps/desktop-cms/src/components/PurchaseOrderDocumentModal.tsx` (mirror `InvoiceModal.tsx` / `DeliveryNoteModal.tsx`).
3. Add API method `getPurchaseOrderDocument(poId)` in `adminClient.ts`.
4. Wire a "Bon de commande" button on the Purchases tab.
5. Build CMS, restart backend, commit with the trailer at §8.

If Antigravity already did this or moved on to something else, skip it and pick the next unfinished module from §3.

---

## 7. How to work

### Loop
1. `git status` → check for Antigravity's in-flight work.
2. Pick an unfinished module from `claude code.md` (highest-value first, see §3 list).
3. Backend: write endpoint(s) + tests. Run tests for that file, then the **full suite** (`python -m unittest discover -s tests`). Must be green.
4. CMS: add API method, write page/component, wire into `App.tsx` (import + tab nav + tab content block). Run `npm run build`.
5. **Restart the backend** (see §9) so the new routes are live.
6. Commit with the message trailer in §8.
7. Repeat.

### Rules from the spec you MUST honor
- Never fabricate device status / test results.
- Never expose the local DB or hardware bridge to the public internet.
- Never hard-code business rules (wilayas, tax, invoice numbers, colors, sizes).
- Never destroy data. Use migrations + `ensure_schema_columns` for additive changes.
- Always enforce permissions on the **backend**, not just UI.
- Completed sales are never edited — correct via reversal/refund.
- Revenue, gross margin and net profit are DISTINCT numbers in every report.

### What NOT to do
- Do **not** touch `apps/storefront/*` live assets or `src-tauri/*` Rust code unless the module explicitly needs it. That is mostly Antigravity's territory.
- Do **not** commit secrets, `.env*`, upload fixtures, or the SQLite dev DB.
- Do **not** run `git push --force`, `git reset --hard`, or anything destructive.
- Do **not** merge `main` into this branch without the user asking.

---

## 8. Commit trailer (always)

```
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

(The exact Claude model name in the trailer may vary between sessions — a system-reminder will tell you what to use. Honor that reminder.)

---

## 9. Backend restart playbook

The backend runs as a background uvicorn process on port 8000. New routes won't be visible until you restart it.

**Windows PowerShell:**
```powershell
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conns) { $conns | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }
```

**Bash (start in background):**
```bash
cd "C:/Users/MOURAD/Desktop/mix luxury/luxe-ecommerce/backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# use run_in_background: true so your tool call returns immediately
```

Then probe:
```bash
curl -s --retry 30 --retry-delay 1 --retry-connrefused -o /dev/null \
     -w "health=%{http_code}\n" --max-time 5 http://127.0.0.1:8000/api/v1/health
```
`health=200` means you're good. New routes should return 401 (not 404) for unauthenticated calls.

---

## 10. When YOUR limit is about to hit

The user does not want to lose momentum between sessions. If you see your usage running low (long-running tool outputs are being truncated, or a system reminder about limits), **stop whatever you're doing and write a handoff for Antigravity**. Save it as:

```
C:/Users/MOURAD/Desktop/mix luxury/luxe-ecommerce/HANDOFF_FOR_ANTIGRAVITY.md
```

Keep the structure of this document (sections 1–10), but target Antigravity: tell it what you just committed, what you were in the middle of, which files are modified vs untracked, what tests pass, which backend routes exist, and which spec section to pick up next. Do **not** restart the backend in your last turn — Antigravity will do that when it needs to.

Likewise, Antigravity leaves `HANDOFF_FOR_CLAUDE.md` for you (this file). Always read the freshest handoff before doing anything else.

---

## 11. Key paths cheat sheet

| What | Where |
|---|---|
| Spec | `claude code.md` |
| Full audit | `docs/FULL_AUDIT_AND_DEPLOYMENT_DISCOVERY.md` |
| Backend monolith | `backend/app/main.py` |
| DB migrations (dual engine) | `backend/migrations/001_initial_schema.sql`, `001_initial_schema_postgres.sql` |
| Additive columns (idempotent) | `backend/app/database.py` → `_ADDITIVE_COLUMNS` |
| RBAC seed + upgrade | `backend/app/seed.py` |
| Backend tests | `backend/tests/test_*.py` |
| CMS shell + tab routing | `apps/desktop-cms/src/App.tsx` |
| CMS API client | `apps/desktop-cms/src/api/adminClient.ts` |
| CMS pages | `apps/desktop-cms/src/pages/*.tsx` |
| Tauri hardware bridge (Rust) | `apps/desktop-cms/src-tauri/src/pos_hardware/` |
| Local POS mirror (Rust + SQLite) | `apps/desktop-cms/src-tauri/src/pos_mirror/` |
| Offline POS queue (TS) | `apps/desktop-cms/src/utils/posOfflineQueue.ts` |
| Nginx (prod proxy) | `infrastructure/nginx/nginx.conf` |
| Compose | `docker-compose.yml` |

---

## 12. Final words

Keep committing in small, tested increments. One commit per module. Full backend suite green every time. Never leave the tree broken.

Good luck. The user is building a real shop in Blida — every decision has to work in a real boutique with real customers and a real accountant. Stay honest.

— Opus 4.7, signing off
