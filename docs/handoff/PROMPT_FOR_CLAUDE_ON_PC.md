# Prompt for Claude Code on the owner's Windows PC

Copy everything below the line into Claude Code, opened in the project folder.

---

You are continuing the Mus Luxury project (online shop + desktop CMS/POS + FastAPI server) on the owner's
Windows PC. Previous work was done in a cloud session that could not reach Windows, the shop's printers or the
VPS. Your job: sync, verify on real Windows, then finish what only this PC can do. Work step by step, report
results honestly (paste real command output for failures), and commit + push after each finished step.

## Rules (never break)
- Branch: `feat/pos-core-cash-register-18lsk6`. Commit and push there; never force-push; no `git reset --hard`.
- Never commit `.env`, `scratch/*.env`, keys, passwords or backups (the repository is private, but secrets still never go in git).
- The default branch on GitHub is `feat/pos-core-cash-register` (it holds everything merged so far).
- Never print secret values (BACKUP_ENCRYPTION_KEY, SECRET_KEY, database passwords) in chat or logs.
- Do not re-add WhatsApp/SMS password recovery. Forgotten password = `python -m app.admin_cli reset-password` on the server.
- Ask the owner before anything on the VPS that changes data, and before deleting anything.
- Server messages shown to people are French. Every new audited action needs a French name in
  `_AUDIT_ACTION_FR` (a test enforces it).
- Keep everything green: `npm run lint`, `npm run test:backend`, `npm run test:e2e`.

## 1. Sync and read (10 min)
```powershell
git fetch origin feat/pos-core-cash-register-18lsk6
git checkout feat/pos-core-cash-register-18lsk6
git pull origin feat/pos-core-cash-register-18lsk6
```
Read, in this order: `docs/README.md` (index), `docs/WORK_SUMMARY_2026-11-11.md` (sections 17–35), `docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md` (sections 0e–0q),
`docs/OPERATIONS_GUIDE.md` (§5 backups, §7c), `docs/deployment/VPS_DEPLOYMENT.md`, `e2e/README.md`.

## 2. Verify on Windows
1. Backend: `cd backend; pip install -r requirements.txt; python -m unittest discover -s tests`
   → expect **346 tests, all passing** (the 4 `@babel/core` tests that fail in the cloud should pass here if Node + babel are installed; report otherwise).
2. Lint: `npm run lint` (ruff + TypeScript with no unused code allowed).
3. Browser tests: `npm install --prefix e2e; npx --prefix e2e playwright install chromium; npm run test:e2e`
   → expect **34 passed**. They start their own server on ports 18000/11420/15173 with an empty database; they never touch real data.
4. Desktop app: `cd apps\desktop-cms; npm install; npm run build; npm run tauri build`
   (needs Rust + Visual C++ build tools; `scripts\windows\install_visual_cpp_build_tools.bat` helps).
   The new Rust module `src-tauri/src/backup_copies.rs` was only `cargo check`-ed in the cloud: make sure it builds and
   run `cargo test backup_copies` in `apps\desktop-cms\src-tauri`.

## 3. Check by hand in the installed desktop app (things the cloud could not test)
Report what you see for each, with screenshots if something is wrong:
- **Backup copies on this PC**: log in as the owner, wait ~20 s → a notice "Sauvegarde copiée sur ce PC" and a file in
  `Documents\Mus Luxury\Sauvegardes` (only if the server already has a backup; otherwise click *Sauvegarder maintenant*
  first in *Sauvegardes & Sécurité*). In that screen: *Copier sur ce PC*, the *Copies sur ce PC* list, *Renvoyer au serveur*.
- **Printers**: *Appareils* → *Tester* on the receipt printer (Windows printer name filled in) → a real ticket prints and
  the status becomes OK; unplug it → a clear error. *Impr. test* asks whether the ticket came out.
- **Times**: a sale made now shows the Windows clock time in Commandes, Trésorerie and Journal d'audit.
- **Windows notifications**: a new online order raises a Windows notification while the CMS is in the background.
- **Photo upload**: add a product photo taken with a phone (5–12 MB): it is accepted, upright, and small once uploaded.
- **Network printer** (if the shop has one on Wi-Fi/Ethernet): *Appareils* → printer with its IP (port 9100) → *Tester*:
  the ticket prints (the desktop app now sends over TCP; this was only tested against a simulated printer).

## 4. With the owner (ask first) — the first production deploy
The owner has the server settings file `production.env` (sent from the cloud session; it holds every secret,
including `BACKUP_ENCRYPTION_KEY` and the Backblaze key). Never ask them to paste it in the chat: they copy it
to the VPS themselves (`scp`), as `/opt/luxe/shared/.env`, `chmod 600`.

1. **Prepare the VPS** (1 vCPU, 2 GB RAM, 40 GB disk): `infrastructure/scripts/vps-bootstrap.sh` (Docker, rclone,
   sqlite3, firewall, deploy user), then the `.env` above. Guide: `docs/deployment/VPS_DEPLOYMENT.md`.
   Check the file on the PC **before** copying it (values are never printed; Push/Pop-Location keeps the
   shell in the repository folder): `Push-Location backend; python -m app.settings check <path to production.env>; Pop-Location`.
2. **GitHub secrets for the deploy**: run `infrastructure/scripts/setup-github-secrets.ps1` (needs `gh auth login`).
   It creates the deploy SSH key and stores `PRODUCTION_SSH_HOST/USER/PRIVATE_KEY`, `PRODUCTION_URL`,
   `PRODUCTION_HEALTH_URL`. The app-update signing key ALREADY EXISTS (its public half is committed): the owner
   received the private key + password; before running, save them as `%USERPROFILE%\.tauri\mux_luxury.key` and
   `mux_luxury.key.password`. The script signs a test file to prove the key matches the committed public key,
   then stores `TAURI_SIGNING_PRIVATE_KEY(_PASSWORD)` (or skips them if the owner already added them in GitHub).
   It was never run on Windows: check that it stops on any failed `gh` write (`Assert-Stored`) and report. Put the deploy key's public half in the deploy user's
   `~/.ssh/authorized_keys` on the VPS. Optional: GitHub Settings → Environments → `production` → required reviewer = owner.
3. **First release** — release exactly what you tested on Windows: first push your fixes to
   `feat/pos-core-cash-register-18lsk6`, open a pull request into `feat/pos-core-cash-register`, wait for green CI
   (and CodeRabbit), merge it, then check that the default branch's newest commit is that merge.
   Then GitHub → Releases → new tag `v1.0.0` on `feat/pos-core-cash-register` → Publish. This runs
   `cd-production.yml` (waits for green CI, builds, uploads over SSH, `release-deploy.sh`: backup first, migrations,
   switch, health check, automatic rollback) and `build-desktop-cms.yml` (signed Windows installer + updater file).
   Follow the run; report each step.
4. **After the deploy, once**: `sudo bash infrastructure/backups/install_backup_cron.sh`,
   `sudo bash infrastructure/scripts/certificates.sh setup` (HTTPS renewal, VPS_DEPLOYMENT §6),
   `bash infrastructure/scripts/health-check.sh`, then one manual
   `sudo bash infrastructure/backups/nightly_backup.sh`: it must end with `[nightly-backup] OK` and the files must
   appear in the Backblaze bucket `musluxury` (off-site copy is already configured and was tested from the cloud).
5. **Uptime Kuma** (`infrastructure/monitoring/`): start it, open it through an SSH tunnel, create HTTPS monitors
   for the shop and `/api/v1/health`, and a **Push** monitor (25 h) whose URL goes into `BACKUP_HEARTBEAT_URL` in
   `/opt/luxe/shared/.env` (called only after a fully successful backup night). Note: Kuma runs on the same VPS, so
   it cannot warn if the whole VPS is down — propose a free outside check for that (e.g. a free uptime service).
   Afterwards, collect (no secrets): `nproc; free -h; df -h /; docker stats --no-stream; sudo du -sh /var/lib/luxe/backups`.
6. **SSH safety**: prefer the deploy user with an SSH key + sudo; propose disabling password and root logins.
7. **Unused photos**: `apps/storefront/public/assets` has 12 photos referenced nowhere (~16 MB). Ask the owner:
   remove them, or use them on the site (CMS → Contenu).

## 5. Then keep improving
Fix anything found in steps 2–4 first. Then, if time remains: keep `npm run test:e2e` green while working; add an e2e
test for any screen you change; keep French messages; update `docs/WORK_SUMMARY_2026-11-11.md` (new section) and
`docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md` (new 0-section) at the end, then commit and push.

Finish with a short report: what passed, what failed (with output), what you fixed, what still needs the owner.
