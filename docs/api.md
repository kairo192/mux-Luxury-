# Référence API REST `/api/v1/`

## Endpoints Publics (Site Web Storefront)
- `GET /api/v1/store/layout` — Configuration complète du site (bannières, sections actives, personnalisation des cartes produits, catégories).
- `GET /api/v1/categories` & `GET /api/v1/categories/{slug}` — Catégories dynamiques et leurs attributs filtrables.
- `GET /api/v1/products` & `GET /api/v1/products/{slug}` — Catalogue produits (sans `purchase_cost_dzd`) et stock par variante.
- `GET /api/v1/delivery-zones` - Les 69 Wilayas d'Algérie, leurs 1 541 communes et tarifs Domicile / Stop-Desk.
- `POST /api/v1/orders` — Guest Checkout (calcul serveur des prix, coupons et frais de livraison Wilaya).
- `GET /api/v1/orders/track?reference=...&phone=...` — Suivi sécurisé de commande sans compte.

## Endpoints Administrateur (Tauri 2 Desktop CMS — Authentification Bearer Requise)
- `POST /api/v1/admin/auth/login` & `POST /api/v1/admin/auth/logout`
- `POST /api/v1/admin/auth/recovery/request` & `POST /api/v1/admin/auth/recovery/verify` — Récupération WhatsApp Cloud API / Code d'urgence hors-ligne.
- `GET /api/v1/admin/dashboard` — Statistiques temps réel, alertes stock et journaux d'audit.
- `POST /api/v1/admin/categories` & `POST /api/v1/admin/category-attributes` & `DELETE /api/v1/admin/category-attributes/{id}`
- `POST /api/v1/admin/products` & `PUT /api/v1/admin/products/{id}` (avec détection de conflit `expected_version`) & `POST /api/v1/admin/products/{id}/generate-variants`
- `GET /api/v1/admin/orders` & `PATCH /api/v1/admin/orders/{id}` (workflow 9 statuts + réintégration automatique du stock)
- `PUT /api/v1/admin/homepage-sections/{key}`, `POST /api/v1/admin/banners`, `POST /api/v1/admin/coupons`, `PUT /api/v1/admin/settings`
- `GET /api/v1/admin/backups` & `POST /api/v1/admin/backups`
