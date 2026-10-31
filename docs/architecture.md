# Architecture Système — Mus Luxury (`LUXE`) E-Commerce & Desktop CMS

## 1. Vue d'ensemble des 3 composants interconnectés

1. **`apps/storefront` (Site Web E-Commerce Public)** :
   - Application React 18 + TypeScript + Vite + Tailwind CSS destinée aux clients en Algérie (Mobile-first, FR / AR RTL / EN).
   - **0% de code CMS ou d'administration** n'est présent dans le site public.
   - Fonctionne en **Guest Checkout** (sans création de compte client) avec **Paiement à la livraison (Cash on Delivery)** sur les **58 Wilayas d'Algérie**.
2. **`apps/desktop-cms` (Logiciel Bureau Windows Tauri 2)** :
   - Application native Windows 10/11 construite avec **Tauri 2 + React + TypeScript** (`Mus Luxury CMS.exe` / `.msi`).
   - Protégée par une **authentification administrateur obligatoire** (`POST /api/v1/admin/auth/login`), 6 rôles RBAC, et une récupération de mot de passe via l'**API officielle WhatsApp Business Cloud** (`/api/v1/admin/auth/recovery/*`) + codes d'urgence hors-ligne.
   - Ne se connecte **jamais** directement à PostgreSQL : toutes les opérations passent par l'API HTTPS `/api/v1/admin/*`.
3. **`backend/` (API Centrale & Base de Données sur VPS Algérien)** :
   - Python 3.11 + FastAPI + PostgreSQL 16 + migrations versionnées.
   - Source unique de vérité (`Single Source of Truth`) avec contrôle de concurrence optimiste (`version`) pour éviter les conflits d'édition simultanée.
