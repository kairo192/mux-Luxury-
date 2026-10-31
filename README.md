# Mus Luxury (`LUXE`) — E-Commerce Platform & Dynamic CMS

Production-oriented e-commerce platform built for **Mus Luxury (`LUXE`)** targeting the Algerian market (`DZD / DA`), featuring mobile-first **Guest Checkout (Cash on Delivery across 58 Wilayas)**, **FR / AR (RTL) / EN** localization, a **Dynamic Category & Attribute Builder**, real **Variant-Level Inventory**, and a **Tauri 2 Desktop CMS**.

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
- **Authentic Assets**: Uses the owner's supplied **Mus Luxury** neon/gold insignia (`storefront/public/assets/mus_luxury_logo.png`) and product photography.

---

## 2. System Architecture

```
luxe-ecommerce/
├── .github/workflows/ci.yml       # Automated GitHub Actions CI (Backend + Security + Frontend)
├── .env.example                   # Environment template (no secrets committed)
├── docker-compose.yml             # Production stack (PostgreSQL 16 + FastAPI + Storefront + Nginx)
├── backend/                       # Python 3.11 + FastAPI + PostgreSQL/SQLite REST API (/api/v1/)
│   ├── app/
│   │   ├── main.py                # Versioned public & RBAC-protected admin endpoints
│   │   ├── security.py            # PBKDF2/Argon2 hashing, signed tokens, rate limiting, MIME checks
│   │   ├── database.py            # Relational connection & transaction management
│   │   └── seed.py                # 9 initial dynamic categories, attributes, products & Algerian Wilayas
│   ├── migrations/
│   │   └── 001_initial_schema.sql # 22 normalized relational tables
│   └── tests/
│       └── test_luxe_api.py       # Automated test suite (Auth, RBAC, Dynamic Categories, Variants, Orders)
├── storefront/                    # React 18 + TypeScript + Vite + Tailwind CSS Public Storefront
├── desktop-cms/                   # Tauri 2 + React + TypeScript Windows Desktop CMS (HTTPS API client)
└── infra/nginx/nginx.conf         # Reverse proxy, rate limiting & security headers
```

---

## 3. Smartphone & Cloud Workflow (GitHub + Codespaces)

Because you are managing the project from a smartphone:

1. **Create Private GitHub Repository**:
   - Open [github.com/new](https://github.com/new) in your mobile browser, name the repository **`luxe-ecommerce`**, set visibility to **Private**, and tap **Create repository**.
2. **Import This Repository Bundle**:
   - In GitHub Mobile/browser, open **GitHub Codespaces** (or upload `luxe-ecommerce-repo.zip`) and run:
     ```bash
     git remote add origin https://github.com/<your-username>/luxe-ecommerce.git
     git push -u origin main
     ```
3. **Run Backend & Automated Tests in the Cloud**:
   ```bash
   cd backend
   python3 -m unittest discover -s tests -v
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Deploy to an Algerian VPS (e.g., Icosnet, Djaweb, or Cloud VPS)**:
   ```bash
   cp .env.example .env
   # Edit .env with strong POSTGRES_PASSWORD and SECRET_KEY
   docker compose up -d --build
   ```
