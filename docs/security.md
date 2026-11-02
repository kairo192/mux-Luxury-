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


## 4. Matrice de Défense Complète Contre Tous les Types d'Attaques (OWASP & E-Commerce)

Le système implémente une défense en profondeur validée par 54 tests unitaires et d'intégration automatisés (`Ran 54 tests — OK`) :

| Vecteur d'Attaque | Risque Potentiel | Défense Active Implémentée & Validée |
| :--- | :--- | :--- |
| **1. Replay Attacks (Rejeu de paquets)** | Un attaquant intercepte une requête signée et la rejoue pour dupliquer une action ou vider un stock. | **Cache de Nonces cryptographiques** (`X-Luxe-Nonce`) + fenêtre temporelle stricte de 300s (`X-Luxe-Timestamp`). Rejeu rejeté avec `HTTP 401 Unauthorized` (`test_16`). |
| **2. Man-in-the-Middle (MitM) & Altération de trafic** | Interception et modification d'un montant, d'un statut ou d'un paramètre en transit. | **Chiffrement TLS 1.3** + **Signature HMAC-SHA256** calculée sur `METHOD \| PATH \| TIMESTAMP \| NONCE \| SHA256(BODY)`. Altération d'un seul octet rejetée (`test_17`). |
| **3. Écoute de réseau (Sniffing)** | Espionnage du trafic entre le PC de gestion et le serveur. | **Double protection** : TLS 1.3 strict (HSTS 2 ans préchargé) + **Tunnel WireGuard chiffré en ChaCha20-Poly1305** (`infrastructure/vpn/wireguard-server.conf`). |
| **4. Brute-Force & Credential Stuffing** | Attaque automatisée par dictionnaire sur les mots de passe administrateur. | **Fenêtres glissantes de rate limiting** (max 5 req/min sur `/login`, verrouillage progressif `HTTP 429`) + hachage ultra-résistant **Argon2id / PBKDF2 (310 000 itérations)**. |
| **5. DDoS & Inondation de requêtes (HTTP Flood / Slowloris)** | Saturation de la bande passante ou épuisement des sockets de connexion. | **Zones Nginx de limitation par IP** (`limit_req_zone`, `limit_conn 25`), timeouts agressifs (10s pour headers et body), et seuils d'inondation sur `/orders`. |
| **6. Injection SQL (SQLi)** | Injection de code SQL (`' OR 1=1;--`) dans les filtres ou l'authentification. | **100% de requêtes paramétrées via SQLAlchemy 2.0 ORM**. Aucune concaténation de chaînes SQL brute (`test_19`). |
| **7. Cross-Site Scripting (XSS)** | Injection de scripts JavaScript malveillants dans les avis ou le catalogue. | **Politique de Sécurité du Contenu (CSP)** stricte, `X-XSS-Protection: 1; mode=block`, `X-Content-Type-Options: nosniff`, et neutralisation des entrées. |
| **8. Clickjacking & Détournement d'interface** | Intégration du site dans une iframe piégée pour tromper les utilisateurs. | En-têtes `X-Frame-Options: DENY` et `frame-ancestors 'none'` interdisant tout encapsulage. |
| **9. Cross-Site Request Forgery (CSRF)** | Déclenchement d'actions non sollicitées via des requêtes inter-sites. | Architecture basée sur jetons d'autorisation `Bearer` cryptographiques (HMAC-SHA256) sans sessions de cookies implicites vulnérables. |
| **10. Insecure Direct Object References (IDOR)** | Un client consulte ou modifie la commande ou les données d'un autre client. | **Autorisation duale obligatoire** : `GET /api/v1/orders/track` exige la correspondance stricte de la référence ET du téléphone mobile du client (`test_10`). |
| **11. Manipulation de Prix & Stocks (Tampering)** | Un client malveillant modifie le prix d'un produit (ex: 1 DA) ou le total dans le navigateur. | **Calcul 100% côté serveur** : Les totaux, coupons et frais Wilayas sont recalculés dans une transaction atomique (`test_06`), ignorant tout prix envoyé par le navigateur. |
| **12. Path Traversal & Téléversement de WebShell** | Téléversement d'un script exécutable (ex: `shell.php`) maquillé en image JPG. | **Vérification des Magic Bytes binaires** (`JPEG`, `PNG`, `WEBP`), détection de signatures malveillantes (`eval(`, `<?php`), renommage en hachage SHA-256, et interdiction d'exécution dans Nginx (`test_18`). |
| **13. Server-Side Request Forgery (SSRF)** | Incitation du serveur à contacter des adresses internes (ex: `localhost`, AWS metadata). | Aucune URL externe n'est récupérée par le backend sans liste blanche stricte. |
| **14. Exposition directe de la Base de Données** | Scanners scannant le port PostgreSQL 5432 sur l'IP publique. | **PostgreSQL s'exécute sur un réseau Docker interne isolé** (`backend_net: internal: true`) sans aucun port mappé vers l'extérieur. |
