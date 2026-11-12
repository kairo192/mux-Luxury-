# Prompt for Antigravity: sync the PC with the cloud work, then finish the owner's to-do list

> Copy everything below the line into Antigravity.

---

You are working on the Mus Luxury project on the owner's Windows PC (your branch: `feat/pos-core-cash-register`).
Claude Code (cloud) pushed new work to the branch `feat/pos-core-cash-register-18lsk6`. Your job:
**(A)** bring that work onto this PC, **(B)** verify it on real Windows, **(C)** carry out the owner's
remaining tasks. Work step by step, report after each part, and stop to ask the owner whenever a
step needs something only they have (passwords, VPS IP, provider accounts).

## Rules (do not break these)
- Never force-push, never `git reset --hard`, never rewrite history. Merge, don't rebase shared branches.
- Never commit secrets: no `.env`, `*.key`, `*.password`, `scratch/production.env`, `*.sqlite3`, backups.
- Do **not** regenerate the production `.env`. Its secrets are already generated, and changing
  `POSTGRES_PASSWORD` would lock the server out of its own database.
- Do **not** re-create `backend/scripts/restore_demo_products.py`. It was deleted on purpose because it
  wiped staff accounts.
- Do not add a backup **download** endpoint. Backups stay on the server, encrypted.
- Never print private keys or passwords in the chat or in logs.
- Keep commits small, with clear messages that say what changed and why.

## Part 0. Read first (10 minutes)
1. `docs/WORK_SUMMARY_2026-11-11.md`: what was done and the owner's to-do list.
2. `docs/OPERATIONS_GUIDE.md`: how the PC, the VPS, GitHub, backups and updates work.
3. `HANDOFF_FOR_ANTIGRAVITY.md`, sections **0** (newest) and **0 LATEST ROUND**: technical details for you.

## Part A. Update the codebase on this PC
```powershell
cd <repo folder>
git status                      # must be clean; if not, commit or stash your own work first
git fetch origin
git checkout feat/pos-core-cash-register
git pull origin feat/pos-core-cash-register
git merge origin/feat/pos-core-cash-register-18lsk6
```
- The commits you must end up with include `d789d5f`, `0db9dbc`, `e9bea80`, `c32dfd3`, `f7088b4` (check with
  `git log --oneline -8`).
- If there are conflicts: keep **both** sides' intent. In `HANDOFF_FOR_ANTIGRAVITY.md`, keep all
  sections. In code, prefer the cloud version for the files listed in the summary (§5–§8) unless your
  change is newer and unrelated. Then run the tests (Part B) before committing the merge.
- Install and refresh dependencies:
```powershell
cd apps\desktop-cms
npm ci
cd src-tauri
cargo build                      # downloads tauri-plugin-notification + tauri-plugin-updater
cd ..\..\..
```
- **Old example banners / promo codes:** nothing to run by hand. The owner's PC uses the CMS app
  against the server; the server removes them once at its first start after the deploy (see
  `docs/WORK_SUMMARY_2026-11-11.md` §15). If this PC also runs a LOCAL backend (SQLite, training mode),
  just restart that backend once after pulling: the same one-time cleanup runs there. Check the result
  in CMS → Journal d'audit (action `remove_legacy_demo_content`).
- Push the merge: `git push origin feat/pos-core-cash-register`

## Part B. Verify on real Windows (things the cloud could not test)
1. **Backend tests** (from `backend`): `python -m unittest discover -s tests`. Expected: 300 tests,
   **all passing** on this PC (the 4 `@babel/core` failures only happen in the cloud container). Report
   any failure with its output; do not skip or delete tests.
2. **CMS build:** `cd apps\desktop-cms; npm run build` then `npm run tauri dev`.
   **Browser tests:** `npm install --prefix e2e; npx --prefix e2e playwright install chromium; npm run test:e2e` (28 tests, expected all green).
3. Check by hand in the running app, and report what you see:
   - Bottom-corner toasts; a message box queue ("1 sur 2"); the bell with history.
   - **Windows notification:** put the CMS in the background, create a test online order (or run the
     notification from the console), and confirm a Windows toast appears and the taskbar flashes.
     Under `tauri dev` it may show as "PowerShell"; that's expected, the installed app shows its own name.
   - Version chip → update dialog shows "mises à jour non activées" (normal until Part C1 is done).
   - **Catégories:** delete one ("Supprimer définitivement"), archive one, reload twice → they must
     NOT come back; the **Archivées** tab shows the archived one with **Restaurer**.
   - **Sauvegardes & Sécurité → Base de données & sauvegardes:** the panel loads (SQLite on the PC),
     **Sauvegarder maintenant** works.
   - **Appareils → Tester** on a receipt printer (Windows printer name filled in): a real test ticket
     prints and the status becomes "OK"; unplug it and test again → a clear error, status "Erreur".
     **Impr. test** asks whether the ticket came out and records the answer.
   - **Times:** a sale made now shows the Windows clock time (not 1 hour earlier) in Commandes,
     Trésorerie and Journal d'audit.
4. **Dry-run the PowerShell script syntax** (no keys created yet):
   `powershell -NoProfile -Command "$null = [ScriptBlock]::Create((Get-Content -Raw infrastructure\scripts\setup-github-secrets.ps1)); 'syntax OK'"`
   Fix any syntax error you find, commit, push.

## Part C. Owner's to-do list (from the summary)

### C1. GitHub keys (signing + deploy). **Ask the owner first.**
- Needs: GitHub CLI installed and logged in (`winget install GitHub.cli`, then `gh auth login`, which the
  owner does in the browser), and the **VPS IP address** (ask the owner; if there is no VPS yet, run without `-VpsHost`).
```powershell
powershell -ExecutionPolicy Bypass -File infrastructure\scripts\setup-github-secrets.ps1 -VpsHost <VPS IP>
```
- Expected: "OK" lines, secrets and variables stored in GitHub, and a public `DEPLOY_PUBLIC_KEY=...` line
  printed for the VPS. Re-running is safe: existing keys are re-used, never overwritten.
- Then tell the owner to copy these two files to a USB key kept in a safe:
  `%USERPROFILE%\.tauri\mux_luxury.key` and `%USERPROFILE%\.tauri\mux_luxury.key.password`.
- Verify in GitHub (repo → Settings → Secrets and variables → Actions) that these exist:
  secrets `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`, `PRODUCTION_SSH_PRIVATE_KEY`,
  `PRODUCTION_SSH_USER` (+ `PRODUCTION_SSH_HOST` if an IP was given); variables `TAURI_UPDATER_PUBKEY`,
  `PRODUCTION_URL`, `PRODUCTION_HEALTH_URL`. Report names only, never values.

### C2. Off-site backup copy. **The owner must choose a provider.**
- Explain the choice to the owner in two lines: an S3-compatible bucket (Backblaze B2, Wasabi, Scaleway, OVH),
  a few euros per month, so backups survive the loss of the VPS.
- Once the owner has the 5 values (endpoint, region, bucket, access key, secret key), put them into the
  **private** production `.env` (`S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`,
  `S3_SECRET_ACCESS_KEY`) and set `S3_BACKUP_ENABLED=true`. Edit only these lines; never commit the file.

### C3. Backup key safety
- Remind the owner to store `BACKUP_ENCRYPTION_KEY` (from the private production `.env`) in a password
  manager. Do not display it yourself; let the owner open the file.

### C4. Empty the local PC database. The owner wants "everything empty and clear".
- Takes a safety backup first, keeps staff accounts, wilayas and settings:
```powershell
cd backend
python -m app.backup_cli info          # shows the 9 demo categories etc.
python -m app.backup_cli reset --yes   # empties the shop (safety backup is kept in backend\backups)
python -m app.backup_cli info          # categories/products must now be 0
```
- Then open the CMS: Catégories is empty, and nothing comes back after restarting the backend
  (the demo catalog is no longer seeded outside tests).
- If the owner prefers, do it from the CMS instead: Sauvegardes & Sécurité → **Créer une base vide**.

### C5. After the first VPS deploy: restore drill (15 minutes, with the owner)
Follow `docs/OPERATIONS_GUIDE.md` §9: backup now → create a "TEST-RESTAURATION" category → restore →
the test category is gone. Then check on the server:
`tail -50 /opt/luxe/logs/backup.log` and `cat /var/lib/luxe/backups/last_backup_status.json` (must say `"ok":true`).

## Part D. Report back
Write `docs/ANTIGRAVITY_REPORT_<date>.md` with:
- Merge result (commit hash, conflicts and how you solved them).
- Test results (numbers + any failure output).
- What you checked by hand on Windows (notifications, categories, database panel): OK / problem + screenshot path.
- C1–C5: done / waiting for owner (say exactly what is missing).
Commit it and push `feat/pos-core-cash-register`. Then add a short "section 0" at the top of
`HANDOFF_FOR_CLAUDE.md` so Claude Code can continue from where you stopped.
