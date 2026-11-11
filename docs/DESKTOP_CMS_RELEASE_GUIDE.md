# Mus Luxury (LUXE) — Desktop CMS & POS Windows Release Guide

**Application:** Windows Desktop CMS & POS (`apps/desktop-cms/`)  
**Framework:** Tauri 2 (Rust + React 18 / TypeScript)  
**Distribution Target:** Windows 10 & Windows 11 (64-bit x86_64)

---

## 1. Build Architecture: Off-Server CI/CD Compilation

Because the production VPS has only 1 vCore and 2 GB RAM, **the Windows Desktop application is NEVER compiled on the VPS**.

All Windows desktop artifacts (`.msi` / `.exe` / NSIS installers) are compiled on Microsoft-hosted GitHub Actions runners (`windows-latest`) using the workflow in `.github/workflows/build-desktop-cms.yml`.

---

## 2. GitHub Actions Automated Release Pipeline

### 2.1 One-time setup (the updater stays OFF until this is done)
1. Generate the signing key pair once, on a trusted machine:
   ```bash
   cd apps/desktop-cms
   npx tauri signer generate -w ~/.tauri/mux_luxury.key
   ```
2. In GitHub → Settings → Secrets and variables → Actions:
   - **Secret** `TAURI_SIGNING_PRIVATE_KEY` = content of `~/.tauri/mux_luxury.key`
   - **Secret** `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` = the password you chose
   - **Variable** `TAURI_UPDATER_PUBKEY` = content of `~/.tauri/mux_luxury.key.pub`
3. Keep the private key offline as well (password-protected USB + paper backup). Never commit it.

The public key is **not** stored in `tauri.conf.json`. It is baked into the
binary at compile time through the `LUXE_UPDATER_PUBKEY` environment variable
(`src-tauri/src/app_services.rs`). A build without it — local dev builds, CI
builds of `main`, a tag pushed before the secrets exist — runs normally with
the updater switched off. It never crashes at startup. That startup crash is
why the old updater was removed in `500116a`.

### 2.2 Releasing a new version
No file needs a version bump: the version comes from the tag.
```bash
git tag -a v1.0.1 -m "Mus Luxury CMS v1.0.1"
git push origin v1.0.1
```
`.github/workflows/build-desktop-cms.yml` then:
- builds the React bundle and the Rust binary on `windows-latest`,
- runs `tauri build --config '{"version":"1.0.1","bundle":{"createUpdaterArtifacts":true}}'`
  with the private key, which produces the NSIS installer and its `.sig` signature,
- runs `scripts/make-latest-json.mjs`, which copies the installer to
  `MusLuxuryCMS_1.0.1_x64-setup.exe` (no spaces, so the URL is stable) and
  writes `latest.json`,
- attaches the installer, `.sig`, MSI and `latest.json` to the GitHub release `v1.0.1`.

Set the release body afterwards if you want: the manifest's `notes` field
(shown in the update dialog under "Nouveautés") comes from the `RELEASE_NOTES`
env var, which defaults to "Mus Luxury CMS v1.0.1".

---

## 3. How installed CMS apps update

1. 15 s after start, then every 4 h, the app asks
   `https://github.com/kairo192/mux-Luxury-/releases/latest/download/latest.json`
   whether there is a newer version.
2. If there is one, the cashier gets:
   - a gold **"Mise à jour vX disponible"** chip in the header,
   - an in-app toast with an **Installer et redémarrer** button,
   - a Windows notification if the CMS is in the background.
3. Nothing installs on its own. The user clicks **Installer et redémarrer**, either in the toast or
   in the dialog opened from the version chip. If offline POS sales are still
   waiting to sync, the app warns first; they stay safe in the local queue and
   sync after the restart.
4. The download is verified against the baked-in public key. A file that is
   not signed with your private key is refused. The NSIS installer runs in
   passive mode and relaunches the CMS.

The version chip also offers **Rechercher une mise à jour** at any time.

---

## 4. Notifications (in-app + Windows)

- **Toasts** (bottom corner, bottom-left in Arabic) are for confirmations and non-blocking
  info. The newest sits nearest the corner, at most four are visible, and identical
  messages merge into "×N". Hovering a toast pauses its timer, and so does switching to another window.
- **Message boxes** are for errors and validations that need attention. They
  are queued, never overwritten. Several in a row show "1 sur 3" with
  **Suivant** / **Tout fermer**. **Entrée** or **Échap** closes the current one.
- **Bell** (header) keeps the session's history, with an unread badge and a
  **Notifications Windows** on/off switch.
- **Windows notifications** (`tauri-plugin-notification`, `os_notify` command)
  fire only while the CMS is not the active window, for:
  new online orders (polled every 45 s), a ready update, and background
  offline-sale sync results. The taskbar button also flashes.
  Windows only shows them for the installed app: the NSIS installer registers
  the app identity. Under `tauri dev` they may appear as "PowerShell" or not at all.

---

## 5. Local Testing & Development

To build and run the desktop application locally on a Windows development machine:

```powershell
cd apps/desktop-cms

# Install dependencies
npm.cmd install

# Start Vite dev server + Tauri native window with hot reload
npm.cmd run tauri dev

# Compile standalone debug executable
npm.cmd run tauri build -- --debug
```
The compiled executable is emitted at `apps/desktop-cms/src-tauri/target/debug/luxe-desktop-cms.exe`.

