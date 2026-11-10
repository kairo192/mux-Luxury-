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

### 2.1 Triggering a Desktop Release
To build and release a new version of the Desktop POS:
1. Bump the version number in `apps/desktop-cms/package.json` and `apps/desktop-cms/src-tauri/tauri.conf.json` (e.g. `1.0.1`).
2. Tag the Git commit with a version tag:
   ```bash
   git tag -a v1.0.1 -m "Release Mus Luxury Desktop POS v1.0.1"
   git push origin v1.0.1
   ```
3. GitHub Actions triggers `.github/workflows/build-desktop-cms.yml`:
   - Checks out the repository.
   - Installs Node.js 20 and Rust toolchain (`stable-x86_64-pc-windows-msvc`).
   - Executes `npm run build` in `apps/desktop-cms` (TypeScript verification + Vite build).
   - Executes `cargo tauri build` to compile the native Rust binary.
   - Packages the NSIS passive installer (`Mus_Luxury_Setup_1.0.1_x64-setup.exe`).
   - Signs the installer with Minisign (`minisign-verify`).
   - Generates the update manifest (`latest.json`).
   - Publishes all artifacts to GitHub Releases under tag `v1.0.1`.

---

## 3. Cryptographic Code Signing & Minisign

Tauri 2 uses **Minisign** to cryptographically sign update bundles:

### 3.1 Key Generation
Generate a Minisign key pair once for the organization:
```bash
minisign -G -p tauri.pub -s tauri.key
```

### 3.2 Key Placement:
- **Public Key:** Base64 string pasted into `apps/desktop-cms/src-tauri/tauri.conf.json` under `plugins.updater.pubkey`.
- **Private Key:** Stored securely as a GitHub Repository Secret (`TAURI_SIGNING_PRIVATE_KEY`).

---

## 4. Automatic In-App Updates (`tauri-plugin-updater`)

The Desktop CMS checks for updates against GitHub Releases:

1. On boot, `tauri-plugin-updater` queries `https://github.com/kairo192/mux-Luxury-/releases/latest/download/latest.json`.
2. If `latest.json` indicates a newer version than currently installed:
   - Downloads the new installer bundle in the background.
   - Verifies the cryptographic Minisign signature against the embedded public key.
   - Prompts the cashier: *"Une mise à jour importante de Mus Luxury est disponible. Redémarrer maintenant pour appliquer ?"*
   - Replaces the executable cleanly and relaunches.

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

