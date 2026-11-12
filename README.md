# Mus Luxury (`LUXE`) — E-Commerce Platform & Dynamic CMS

Production-oriented e-commerce platform built for **Mus Luxury (`LUXE`)** targeting the Algerian market (`DZD / DA`), featuring mobile-first **Guest Checkout (Cash on Delivery across all 69 Wilayas and their 1,541 communes)**, **FR / AR (RTL) / EN** localization, a **Dynamic Category & Attribute Builder**, real **Variant-Level Inventory**, and a **Tauri 2 Desktop CMS**.

---

## 1. Brand Identity & Design System

| Token | Hex | Usage |
| :--- | :--- | :--- |
| **Deep Emerald Green** | `#063D2E` | Primary headers, navigation, primary action buttons |
| **Dark Forest Green** | `#02291F` | Deep backgrounds, hero overlays, footer, desktop CMS sidebar |
| **Reflective Gold** | `#D4AF62` | Brand accents, primary CTAs, active borders, badges |
| **Light Gold** | `#E8D4A5` | Secondary highlights, subtle borders, hover states |
| **Cream Background** | `#F8F6F0` | Main storefront canvas background |
| **Main Text** | `#202923` | High-contrast body typography |
| **White** | `#FFFFFF` | Product cards, forms, modals |

- **Typography**: `Playfair Display` (serif headings), `Montserrat` (FR/EN interface), `Cairo` (Arabic RTL interface).
- **Authentic Assets**: Uses the owner's supplied **Mus Luxury** neon/gold insignia (`apps/storefront/public/assets/mus_luxury_logo.png`) and product photography.

---

## 2. System Architecture

```text
luxe-ecommerce/
├── .github/workflows/            # CI/CD (ci.yml, cd-production.yml, build-desktop-cms.yml)
├── .env.example                  # Environment template (zero secrets committed)
├── docker-compose.yml            # Production stack (PostgreSQL 16 + FastAPI + Storefront + Nginx ~608MB RAM)
├── backend/                      # Python 3.11 + FastAPI + PostgreSQL/SQLite REST API (/api/v1/)
│   ├── app/
│   │   ├── main.py               # Public storefront & RBAC-protected admin endpoints
│   │   ├── security.py           # PBKDF2 (600,000 iter), JWT instant revocation, HMAC signing, rate limits
│   │   ├── database.py           # Dual SQLite / PostgreSQL 16 connection & transaction adapter
│   │   └── seed.py               # 14 dynamic categories, attributes, products & 69 Algerian Wilayas
│   ├── migrations/
│   │   ├── 001_initial_schema.sql          # SQLite schema (41 relational tables)
│   │   └── 001_initial_schema_postgres.sql # PostgreSQL 16 schema (100% parity)
│   └── tests/                    # 300 automated backend tests (SQLite + PostgreSQL 16)
├── apps/
│   ├── storefront/               # Online shop: one index.html (vanilla JS, FR/AR/EN) + Vite/Tailwind (guest COD, 69 wilayas)
│   └── desktop-cms/              # Tauri 2.0 + Rust Windows Desktop CMS & POS (wincred token storage)
├── e2e/                          # Browser tests of the shop + CMS together (Playwright), see e2e/README.md
├── infrastructure/               # Nginx reverse proxy, automated backup & deploy scripts
├── scripts/windows/              # Windows helpers (VC++ build tools, local CMS window)
└── docs/                         # Production documentation & runbooks (docs/specs: original specifications)
    ├── architecture/             # SYSTEM_ARCHITECTURE.md (Topology & 41 tables)
    ├── deployment/               # VPS_DEPLOYMENT.md (Octenium setup) & CI_CD.md
    ├── security/                 # SECURITY_HARDENING.md & SECRETS_MANAGEMENT.md
    └── operations/               # BACKUP_AND_RESTORE.md, MAINTENANCE.md & TROUBLESHOOTING.md
```

---

## 3. Production Documentation Index

- [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [Desktop CMS / POS architecture](apps/desktop-cms/ARCHITECTURE.md) — folders, data flow, permissions, how to add a screen
- [Operations guide for the owner](docs/OPERATIONS_GUIDE.md)
- [Octenium VPS Deployment Guide](docs/deployment/VPS_DEPLOYMENT.md)
- [CI/CD & GitHub Actions](docs/deployment/CI_CD.md)
- [Security Hardening Standards](docs/security/SECURITY_HARDENING.md)
- [Secrets Management Policy](docs/security/SECRETS_MANAGEMENT.md)
- [Backup & Disaster Recovery Runbook](docs/operations/BACKUP_AND_RESTORE.md)
- [Operations & Routine Maintenance](docs/operations/MAINTENANCE.md)
- [Troubleshooting & Diagnostics](docs/operations/TROUBLESHOOTING.md)

---

## 4. Production Deployment & Cloud Workflow

Because you are managing the project from a smartphone:

1. **Create Private GitHub Repository**:
   - Open [github.com/new](https://github.com/new) in your mobile browser, name the repository **`luxe-ecommerce`**, set visibility to **Private**, and tap **Create repository**.
2. **Import This Repository Bundle**:
   - In GitHub Mobile/browser, open **GitHub Codespaces** (or upload `luxe-ecommerce-repo.zip`) and run:
     ```bash
     git remote add origin https://github.com/<your-username>/luxe-ecommerce.git
     git push -u origin main
     ```
3. **Run the tests** (all run in CI on every push, see `.github/workflows/ci.yml`):
   ```bash
   npm run lint          # ruff (backend) + TypeScript (CMS, no unused code allowed)
   npm run test:backend  # 300 backend tests (SQLite; CI also runs them on PostgreSQL 16)
   npm run test:e2e      # 28 browser tests: shop + CMS together on a fresh production-mode API
   ```
   Local development: `cd backend && uvicorn app.main:app --reload --port 8000`,
   then `npm run dev:cms` and `npm run dev:storefront`.
4. **Deploy to an Algerian VPS (e.g., Icosnet, Djaweb, or Cloud VPS)**:
   ```bash
   cp .env.example .env
   # Edit .env with strong POSTGRES_PASSWORD and SECRET_KEY
   docker compose up -d --build
   ```
