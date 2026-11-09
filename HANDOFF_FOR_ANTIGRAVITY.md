# HANDOFF — Mus Luxury (LUXE)

**To:** Antigravity (the AI running on the user's local Windows machine)
**From:** Claude Code (cloud session, branch `feat/pos-core-cash-register-18lsk6`)
**Date:** 2026-11-09
**Last commit on cloud branch:** `11eaccc` + the uncommitted work described in §3 below.

---

## 1. Read this first

- The user asked me to produce a production `.env` and continue cleanup. That's what the diff on this branch does. **I did not push this work yet**; the next commit (`§5 below`) is yours to amend or extend before you push.
- You are mirroring sections of the full spec (`claude code.md`). I've been working on the operational cleanup lane (CSP, fetch hardening, `window.prompt` removal, offline SQLite catalog mirror, test pruning, `.env` generator). You are the owner of the feature lane.
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
- Third-party vendor fields the project can't fabricate (Meta WhatsApp, Chargily, Yalidine, S3, SMTP) are written as explicit `<FILL_IN_...>` tokens — a `grep "<FILL_IN"` on the file immediately shows what still needs the owner's input.
- Writes to `scratch/production.env` by default, chmod 0600 on POSIX. Prints the critical values on stdout one time so the user can file them in a password manager.
- Usage (from the repo root):

  ```bash
  python3 backend/scripts/generate_production_env.py \
      --domain mus-luxury.dz \
      --admin-email admin@mus-luxury.dz \
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

1. **Keep working on the `claude code.md` modules.** The handoff you left me (`HANDOFF_FOR_CLAUDE.md`) listed the roadmap; it's still accurate except that the backup admin UI and WhatsApp recovery UI are now intentionally gone from the CMS. Do not re-add them.
2. **Keep writing to `HANDOFF_FOR_CLAUDE.md`.** The user wants a continuously-updated handoff doc that documents the current state so the next Claude session can resume without context loss. You own that file.
3. **Three blockers from your own earlier audit (BLOCKER-01/02/03) are untouched.** I deliberately did not change them because they need the owner's input (domain confirmation, Dockerfile build stage, Tauri signing keypair). Confirm with the user before changing.
4. **Do NOT regenerate the production `.env`** — the user already has the values from my run. If they need fresh entropy, re-run `backend/scripts/generate_production_env.py --force` and have them re-copy to the VPS.

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

Mirror what I did here: write `HANDOFF_FOR_CLAUDE.md` with the shape above. Include **what you just committed**, **what's uncommitted**, **what tests pass**, and **what section of `claude code.md` to pick up next**. Leave the backend running if you had it running — I'll probe `/api/v1/health` to know.

Good luck. The user is watching the shop open in Blida — every decision has to work in the real boutique.

— Claude Opus 4.7, cloud session, signing off this round
