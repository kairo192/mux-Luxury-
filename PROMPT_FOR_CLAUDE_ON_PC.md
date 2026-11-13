# Prompt for Claude Code on the owner's Windows PC

Copy everything below the line into Claude Code, opened in the project folder.

---

You are continuing the Mus Luxury project (online shop + desktop CMS/POS + FastAPI server) on the owner's
Windows PC. Previous work was done in a cloud session that could not reach Windows, the shop's printers or the
VPS. Your job: sync, verify on real Windows, then finish what only this PC can do. Work step by step, report
results honestly (paste real command output for failures), and commit + push after each finished step.

## Rules (never break)
- Branch: `feat/pos-core-cash-register-18lsk6`. Commit and push there; never force-push; no `git reset --hard`.
- Never commit `.env`, `scratch/*.env`, keys, passwords or backups. The repository is **public**.
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
Read, in this order: `docs/WORK_SUMMARY_2026-11-11.md` (sections 17–32), `HANDOFF_FOR_ANTIGRAVITY.md` (sections 0e–0n),
`docs/OPERATIONS_GUIDE.md` (§5 backups, §7c), `docs/deployment/VPS_DEPLOYMENT.md`, `e2e/README.md`.

## 2. Verify on Windows
1. Backend: `cd backend; pip install -r requirements.txt; python -m unittest discover -s tests`
   → expect **334 tests, all passing** (the 4 `@babel/core` tests that fail in the cloud should pass here if Node + babel are installed; report otherwise).
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

## 4. With the owner (ask first)
1. **Deploy to the VPS** (1 vCPU, 2 GB RAM, **40 GB disk**) so the new backup script, nginx limits, image library
   (Pillow) and server code take effect — via the production deploy workflow (`.github/workflows/cd-production.yml`,
   tag `v*` + approval) or `infrastructure/scripts/release-deploy.sh` as documented. A backup is taken before.
   Afterwards, with the owner logged in on the VPS, collect (no secrets):
   `nproc; free -h; swapon --show; df -h /; docker stats --no-stream; sudo du -sh /var/lib/luxe/backups`
   and check `/var/lib/luxe/backups/last_backup_status.json` after the next night (03:30).
   If the VPS was set up before 12 Nov 2026: after this deploy run `sudo bash infrastructure/backups/install_backup_cron.sh`
   once (nightly backup now reads the .env safely), then `sudo bash infrastructure/scripts/certificates.sh setup`
   (HTTPS renewal, VPS_DEPLOYMENT §6) and `bash infrastructure/scripts/health-check.sh`.
2. **SSH safety**: prefer the deploy user with an SSH key + sudo; propose disabling password and root logins.
3. **Unused photos**: `apps/storefront/public/assets` has 12 photos referenced nowhere (~16 MB, e.g.
   `store_photo_01…04.jpg`, `01…05.jpg`). Ask the owner: remove them, or use them on the site (CMS → Contenu).
4. **Backup key**: confirm the owner keeps `BACKUP_ENCRYPTION_KEY` in a password manager (PC copies are useless without it).
5. Off-site copy (guide §5.4) is still not switched on — remind the owner.

## 5. Then keep improving
Fix anything found in steps 2–4 first. Then, if time remains: keep `npm run test:e2e` green while working; add an e2e
test for any screen you change; keep French messages; update `docs/WORK_SUMMARY_2026-11-11.md` (new section) and
`HANDOFF_FOR_ANTIGRAVITY.md` (new 0-section) at the end, then commit and push.

Finish with a short report: what passed, what failed (with output), what you fixed, what still needs the owner.
