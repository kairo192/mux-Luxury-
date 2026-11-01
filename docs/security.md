# Documentation de Sécurité & Contrôles Testés

## 1. Contrôles Implémentés et Vérifiés par Tests Automatisés

- **Hachage des mots de passe** : Argon2id / PBKDF2-HMAC-SHA256 (310 000 itérations) avec sel aléatoire unique.
- **Contrôle d'accès basé sur les rôles (RBAC — 6 rôles)** : `super_admin` (Owner), `admin`, `product_manager`, `order_manager`, `inventory_manager`, `readonly` vérifiés côté serveur sur chaque route `/api/v1/admin/*`.
- **Récupération WhatsApp Business Cloud API** : Codes OTP à usage unique hachés en SHA-256, expiration stricte à 5 minutes (`300s`), maximum 3 tentatives, révocation des sessions après changement de mot de passe, et erreur explicite `HTTP 503` si l'API officielle n'est pas configurée.
- **Intégrité des prix et des stocks** : Le serveur recalcule systématiquement les prix unitaires en DA, les coupons de réduction, et les tarifs de livraison des 58 Wilayas dans une transaction atomique (`BEGIN IMMEDIATE`), ignorant tout total envoyé par le navigateur.
- **Protection IDOR sur le suivi de commande** : `GET /api/v1/orders/track` exige la correspondance simultanée de la référence de commande et du numéro de téléphone du client.
- **Validation binaire des fichiers uploadés** : Vérification des magic bytes (`JPEG`, `PNG`, `WEBP`) et limite stricte de taille (5 Mo).

## 2. Risques Résiduels & Recommandations d'Exploitation
- Maintenir les mises à jour de sécurité Ubuntu LTS et renouveler régulièrement les certificats TLS Let's Encrypt.
- Stocker les sauvegardes chiffrées sur une destination externe indépendante du VPS principal.


## 3. Initialisation Unique du Propriétaire & Verrouillage Permanent Multi-PC

- **Premier lancement (Setup Vierge)** :
  - Le CMS vérifie `GET /api/v1/admin/auth/setup-status`. Si aucun propriétaire n'existe, l'assistant d'initialisation requiert :
    1. Nom & Prénom du Propriétaire.
    2. Email / Identifiant de connexion.
    3. Mot de passe fort (Argon2id / PBKDF2-SHA256).
    4. Numéro WhatsApp Principal pour la récupération d'accès.
    5. Second numéro de téléphone de secours / urgence.
  - La soumission via `POST /api/v1/admin/auth/initialize-owner` enregistre le Super Administrateur, configure les deux canaux de récupération, et active le marqueur `system_initialized = true` dans la table `store_settings`.
- **Verrouillage Permanent & Comportement Multi-PC** :
  - Dès validation, l'endpoint `POST /initialize-owner` renvoie strictement `HTTP 403 Forbidden` à toute tentative ultérieure.
  - **Même si le logiciel est installé et ouvert sur un autre PC**, le CMS interroge la base centrale PostgreSQL sur le serveur VPS (`/setup-status`), constate que l'initialisation a déjà été effectuée, et **affiche directement le formulaire de connexion standard** (Email, Mot de passe, Mot de passe oublié) sans jamais réafficher l'écran de configuration.
