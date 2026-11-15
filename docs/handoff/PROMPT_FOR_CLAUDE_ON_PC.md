# Prompt for Claude Code on the owner's Windows PC (updated 2026-11-15)

Open Claude Code **in the project folder** on the PC, then copy everything below the line into it.

---

You are continuing the Mus Luxury project (online shop + desktop CMS/POS + FastAPI server) on the owner's
Windows PC. The previous work was done in a cloud session that could not reach Windows, the shop's printers or the
VPS. Your job, in order: **sync the local code with GitHub, verify it on Windows, connect to the VPS over SSH, then
finish the go-live steps that only this PC can do.** Work step by step, paste real command output for anything that
fails, and commit + push after each finished step.

## Rules (never break)
- Work branch: `feat/pos-core-cash-register-18lsk6`. Commit and push there. No force-push, no `git reset --hard`,
  no deleting branches. The default branch on GitHub is `feat/pos-core-cash-register`.
- **PR #5** (`feat/pos-core-cash-register-18lsk6` → `feat/pos-core-cash-register`) is open. **Never merge it unless the owner
  says "merge it"** in the chat.
- Never commit `.env`, `scratch/*.env`, keys, passwords or backups. Never print secret values (SECRET_KEY,
  BACKUP_ENCRYPTION_KEY, database passwords, S3/Backblaze keys, Tauri key password) in chat or logs.
  `scratch/production.env` holds the LIVE production secrets: never print it, never regenerate it.
- Passwords (VPS root, key passwords) are typed **by the owner** in their own terminal, never pasted into the chat.
- Ask the owner before anything on the VPS that changes data, and before deleting anything.
- Do not re-add WhatsApp/SMS password recovery (forgotten password = `python -m app.admin_cli reset-password` on the server).
- No public download link for the installer.
- Server messages shown to people are French. Every new audited action needs a French name in `_AUDIT_ACTION_FR`.
- Keep everything green: `npm run lint`, `npm run test:backend`, `npm run test:e2e`.
- Commit messages end with the line `Co-Authored-By: Claude <noreply@anthropic.com>`.

## 1. Sync the local code with GitHub
The local folder may be old and may hold local edits. Do not throw anything away:
```powershell
git status                      # local edits? -> show them to the owner; keep them with: git stash push -u -m "pc-before-sync"
git fetch origin
git checkout feat/pos-core-cash-register-18lsk6
git pull --ff-only origin feat/pos-core-cash-register-18lsk6
git log --oneline -5            # the top commit must be a3c35ac (or newer)
```
If `--ff-only` refuses (the local branch has its own commits), stop and show `git log --oneline origin/feat/pos-core-cash-register-18lsk6..HEAD`
to the owner; merge (not rebase) only with their agreement.

Then read, in this order: `docs/README.md`, `docs/WORK_SUMMARY_2026-11-11.md` §36 (the PR #5 review fixes),
`docs/deployment/VPS_DEPLOYMENT.md`, `docs/cicd/SECRETS.md`, `docs/OPERATIONS_GUIDE.md` §5, `infrastructure/monitoring/README.md`.

### What changed in the last commits (PR #5, all on the work branch)
- Backend `main.py` split into routers (`backend/app/routers/*`), shared helpers in `common.py` / `deps.py`.
- Storefront split into modules (`apps/storefront/src/shop/*.js`); big CMS screens split into components.
- Two rounds of CodeRabbit review fixes, all with tests: concurrent clicks / two PCs apply status changes, expense deletion
  and offline sales once; archive/restore puts back exactly what it switched off (new columns
  `product_variants.archived_with_product`, `products.variants_marked_on_archive`, added automatically on start);
  unique barcodes; checkout keeps its idempotency key until the order is confirmed and shows what the shop recorded;
  CMS request address and token fixed per request (a late answer for an old session never logs the new one out);
  dialogs keep keyboard focus; XSS escaping in the shop; generated API docs in `docs/api/`.
- Expected results: **backend 386 tests OK**, **e2e 41 passed** (cloud run on `a3c35ac`).

## 2. Verify on Windows
1. Backend: `cd backend; pip install --upgrade -r requirements.txt; python -m unittest discover -s tests` → 386 tests OK.
   (`--upgrade` matters: the generated API docs test expects the FastAPI version from `requirements.txt`.)
2. Lint: `npm run lint`.
3. Browser tests: `npm install --prefix e2e; npx --prefix e2e playwright install chromium; npm run test:e2e` → 41 passed.
   They start their own server on ports 18000/11420/15173 with an empty database (PostgreSQL if `E2E_DATABASE_URL`
   is set, otherwise SQLite); they never touch real data.
4. Desktop app: `cd apps\desktop-cms; npm install; npm run build; npm run tauri build`; then in `src-tauri`: `cargo test`.
5. Quick hand check in the built app: login, Produits (delete dialog: Tab stays inside it), Caisse (a sale), Sauvegardes,
   Appareils → *Tester* on the receipt printer. Report what you see.

## 3. GitHub Actions is blocked by billing (owner, 2 minutes)
Since 2026-11-15 00:30 UTC, GitHub refuses to start CI jobs: *"The job was not started because recent account payments
have failed or your spending limit needs to be increased."* The code is fine (on `4bb8cd5` all 10 jobs passed; only the
final gate job could not start). Until this is fixed, **no CI, no merge, no release, no signed installer**.
- Owner: github.com → **Settings → Billing and plans** → fix the payment method or raise the Actions spending limit.
- Then: repository → Actions → the latest "CI" run on `a3c35ac` → **Re-run all jobs**. Check it goes green.

## 4. Connect to the VPS over SSH
VPS: `5.196.163.6` (Ubuntu, 1 vCPU / 2 GB / 40 GB, Octenium). It once timed out on port 22: if so, the owner
powers it on / reboots it in the Octenium control panel.
```powershell
Test-NetConnection 5.196.163.6 -Port 22          # TcpTestSucceeded : True
# A key for the owner's own logins (skip if %USERPROFILE%\.ssh\id_ed25519 exists). The owner chooses the passphrase.
ssh-keygen -t ed25519 -C "mus-luxury-owner-pc"
```
The owner then runs **in their own terminal** (they type the root password; never in the chat):
```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@5.196.163.6 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```
Check it works without a password: `ssh -o BatchMode=yes root@5.196.163.6 "hostname; uname -a; df -h /; free -h"`.
From then on, run VPS commands as `ssh root@5.196.163.6 "<command>"` (or the `luxe` deploy user once it exists).

## 5. Go-live (with the owner; ask before each step that changes the VPS)
1. **Bootstrap the VPS** (once): copy the repository's `infrastructure/scripts/vps-bootstrap.sh` up and run it as root:
   `scp infrastructure\scripts\vps-bootstrap.sh root@5.196.163.6:/root/` then `ssh root@5.196.163.6 "bash /root/vps-bootstrap.sh"`.
   It creates the `luxe` deploy user, Docker, firewall (22/80/443), `/opt/luxe` layout, backup cron, log rotation.
   Also add the owner's public key to `/home/luxe/.ssh/authorized_keys` so `ssh luxe@5.196.163.6` works.
2. **Server settings file**: the owner has `production.env` (from the cloud session; also in `scratch/production.env`
   on the cloud only — not in git). Check it on the PC without printing values:
   `Push-Location backend; python -m app.settings check <path to production.env>; Pop-Location`.
   Copy it: `scp <path> root@5.196.163.6:/opt/luxe/shared/.env`, then
   `ssh root@5.196.163.6 "chown luxe:luxe /opt/luxe/shared/.env && chmod 600 /opt/luxe/shared/.env"`.
   Do NOT regenerate it.
3. **GitHub secrets**: needs the GitHub CLI logged in (`gh auth login`). The app-update signing key ALREADY EXISTS (its
   public half is committed in `apps/desktop-cms/src-tauri/updater-key.pub`): the owner saves the private key and its
   password as `%USERPROFILE%\.tauri\mux_luxury.key` and `%USERPROFILE%\.tauri\mux_luxury.key.password`. Then:
   `powershell -ExecutionPolicy Bypass -File infrastructure\scripts\setup-github-secrets.ps1 -VpsHost 5.196.163.6`
   It proves the key matches the committed public key, creates the deploy SSH key, stores
   `TAURI_SIGNING_PRIVATE_KEY(_PASSWORD)`, `PRODUCTION_SSH_HOST/USER/PRIVATE_KEY`, `PRODUCTION_URL`,
   `PRODUCTION_HEALTH_URL`, and prints ONE public line: add it to `/home/luxe/.ssh/authorized_keys` on the VPS.
   It was never run on Windows before: report any error (it must stop on a failed `gh` write).
   Never create a new signing key while the public key is committed (every installed CMS would refuse updates).
4. **PR #5**: once CI is green, show the owner the PR and the review threads still open for them (security ones:
   CMS logout token, store-phone / gallery / commune XSS; plus the POS delta-sync watermark and catalogue cursor
   threads — all fixed with tests, left open for the owner to close). Merge **only** when the owner says "merge it".
   After merging, check the default branch's newest commit is that merge.
5. **First release v1.0.0**: GitHub → Releases → new tag `v1.0.0` on `feat/pos-core-cash-register` → Publish.
   This runs `cd-production.yml` (waits for green CI, builds, uploads over SSH, `release-deploy.sh`: backup first,
   migrations, switch, health check, automatic rollback) and `build-desktop-cms.yml` (signed Windows installer +
   updater file). Follow both runs and report each step. The installer stays private (no public download link).
6. **After the first deploy, once** (on the VPS):
   `sudo bash /opt/luxe/current/infrastructure/scripts/certificates.sh setup` (HTTPS + renewals),
   `bash /opt/luxe/current/infrastructure/scripts/health-check.sh`, then one manual
   `sudo bash /opt/luxe/current/infrastructure/backups/nightly_backup.sh` → must end with `[nightly-backup] OK`, and the
   files must appear in the Backblaze bucket. Then create the owner account in the CMS (first-start wizard).
7. **Uptime Kuma** (`infrastructure/monitoring/`): start it on the VPS, open it through an SSH tunnel
   (`ssh -L 3001:127.0.0.1:3001 luxe@5.196.163.6`, then http://localhost:3001), create HTTPS monitors for the shop and
   `https://api.mus-luxury.com/api/v1/health`, and a **Push** monitor (heartbeat interval 25 h). Put its push URL in
   `BACKUP_HEARTBEAT_URL=` in `/opt/luxe/shared/.env` (it is called only after a fully successful backup night).
   Kuma runs on the same VPS, so also propose a free outside uptime check for "whole VPS down".
8. **Backblaze key rotation** (owner, in the Backblaze web site): the cloud session used the current key. Create a new
   **Application Key** limited to the backup bucket only, Read and Write; put its keyID / applicationKey in
   `/opt/luxe/shared/.env` (the `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` lines — the owner edits the file on the
   VPS with `nano`, values never in the chat); run `nightly_backup.sh` once more → `[nightly-backup] OK`; then
   **regenerate the Master Application Key** so the old key stops working.
9. **SSH hardening** (after the `luxe` user and keys work for both the owner and GitHub Actions): propose
   `PasswordAuthentication no` and `PermitRootLogin prohibit-password` in `/etc/ssh/sshd_config`, keep the current SSH
   window open while testing a new login, then `systemctl reload ssh`.
10. Afterwards collect (no secrets): `nproc; free -h; df -h /; docker stats --no-stream; sudo du -sh /var/lib/luxe/backups`.

## 6. Finish
Update `docs/WORK_SUMMARY_2026-11-11.md` (new section: what was done on the PC and on the VPS) and this file's status,
commit and push to `feat/pos-core-cash-register-18lsk6`. End with a short report: what passed, what failed (with
output), what you fixed, what still needs the owner.
