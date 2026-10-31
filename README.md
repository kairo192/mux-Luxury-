# Mus Luxury (LUXE) — Algerian E-Commerce Platform

Mus Luxury (`LUXE`) is a modern, enterprise-grade e-commerce platform tailored specifically for the Algerian market (`DZD / DA`, `FR / AR RTL / EN`). It supports Guest Checkout with Cash on Delivery (COD) across all 58 Wilayas.

## Architectural Separation

The platform enforces a strict separation between three core components:

### 1. Storefront (`storefront/`)
- Public customer web application built with **React**, **TypeScript**, **Vite**, and **Tailwind CSS**.
- Contains **0% CMS code** or administrative logic.
- Fast, responsive, localized interface supporting guest checkout and Wilaya delivery selection.

### 2. Desktop CMS (`desktop-cms/`)
- Standalone Windows Desktop CMS application built with **Tauri 2**, **React**, and **TypeScript**.
- Requires mandatory Administrator Authentication via `POST /api/v1/admin/auth/login`.
- Controls and manages the entire website remotely over secure HTTPS APIs.

### 3. Backend (`backend/`)
- High-performance API server built with **FastAPI** and **PostgreSQL** (`/api/v1/`).
- Features 22 normalized relational tables.
- Dynamic Category & 14-type Attribute Builder.
- Variant-level inventory management.
- Server-side Wilaya delivery calculation and order processing.
