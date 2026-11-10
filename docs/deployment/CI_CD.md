# Mus Luxury (`LUXE`) — CI/CD Pipeline & Release Engineering

## 1. Pipeline Overview

The Mus Luxury continuous integration and delivery architecture utilizes **GitHub Actions** across four specialized workflows:

```text
               Pull Request / Push to Main
                           │
                           ▼
          ┌─────────────────────────────────┐
          │     1. CI Matrix (ci.yml)       │
          │ - Backend Tests (pytest)        │
          │ - Flake8 & Python Typecheck     │
          │ - Storefront Vite Build         │
          │ - Desktop CMS TypeScript Check  │
          │ - Rust Cargo Test & Check       │
          │ - Schema Migration Parity       │
          └────────────────┬────────────────┘
                           │ (All Checks Green)
                           ▼
          ┌─────────────────────────────────┐
          │ 2. Desktop Build & Sign         │
          │    (build-desktop-cms.yml)      │
          │ - Windows Runner (windows-2022) │
          │ - MSVC Rust Toolchain           │
          │ - Tauri 2.0 Binary Build        │
          │ - Release Artifacts (.exe, .msi)│
          └────────────────┬────────────────┘
                           │ (Triggered Deployment)
                           ▼
          ┌─────────────────────────────────┐
          │ 3. CD Production Pipeline       │
          │    (cd-production.yml)          │
          │ - Environment Protection Rule   │
          │ - Database Pre-Flight Backup    │
          │ - Zero-Downtime Container Deploy│
          │ - Post-Deploy Health Check      │
          │ - Automated Rollback on Failure │
          └─────────────────────────────────┘
```

---

## 2. Workflows Specification

### 1. `ci.yml` (Continuous Integration)
- **Triggers:** Push to `main`, push to `feat/*`, pull requests.
- **Jobs:**
  - `backend-test`: Runs pytest against SQLite with full coverage of COD checkout, 69 Wilayas, rate limiting, and RBAC authentication.
  - `storefront-build`: Runs `npm run build` in `apps/storefront` to ensure production bundle compiles without errors.
  - `desktop-cms-check`: Runs TypeScript typecheck (`tsc --noEmit`) and Vite build in `apps/desktop-cms`.
  - `rust-check`: Runs `cargo check` and `cargo test` on `apps/desktop-cms/src-tauri` for POS mirror and ESC/POS peripheral integration.
  - `migration-check`: Validates SQLite and PostgreSQL 16 schema parity across all 41 tables.

### 2. `build-desktop-cms.yml` (Windows Release)
- **Triggers:** Version tags (`v*`), workflow dispatch.
- **Environment:** Windows Server 2022 runner.
- **Steps:**
  - Installs Node.js 20 and Rust stable MSVC.
  - Builds frontend bundle (`npm run build`).
  - Compiles Tauri release binary with embedded assets (`npx tauri build`).
  - Uploads compiled artifacts: `luxe-desktop-cms.exe` and `.msi` installer.

### 3. `cd-production.yml` (Continuous Deployment)
- **Triggers:** Push to `main` with changes to `backend/`, `apps/storefront/`, `infrastructure/`, `docker-compose.yml`.
- **Deployment Gates:** Requires manual production approval via GitHub Environment settings.
- **Pre-Deployment Safety:**
  - Automatically triggers PostgreSQL dump before executing migrations.
  - Executes health probes against `/api/v1/health` post-launch.
  - Rolls back to the previous stable release container if health probes fail.

---

## 3. GitHub Secrets Configuration

The following repository secrets must be configured in GitHub Settings (`Settings -> Secrets and variables -> Actions`):

| Secret Name | Purpose | Example / Format |
| :--- | :--- | :--- |
| `VPS_SSH_HOST` | Production server IP | `5.196.163.6` |
| `VPS_SSH_USER` | Deployment user | `root` |
| `VPS_SSH_KEY` | Private SSH key for server authentication | OpenSSH private key format |
| `PRODUCTION_SECRET_KEY` | Backend token signing key | 64-byte hex (`openssl rand -hex 64`) |
| `PRODUCTION_POSTGRES_PASSWORD` | PostgreSQL database user password | 32-byte base64 |
| `TAURI_SIGNING_PRIVATE_KEY` | Windows desktop updater private key | Minisign private key |

