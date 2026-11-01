# SECURITY ARCHITECTURE & THREAT MODEL — MUS LUXURY (`LUXE`)

---

## 1. Authentication, Password Hashing & Session Security

1. **Password Hashing (`backend/app/security.py`)**:
   - Uses **PBKDF2-HMAC-SHA256** with **310,000 OWASP-recommended iterations** and a cryptographically random 128-bit salt per password.
   - Verification uses constant-time `hmac.compare_digest` to prevent timing side-channel attacks.
2. **One-Time First-Run Owner Provisioning (`POST /api/v1/admin/auth/initialize-owner`)**:
   - On an uninitialized database, the first launch of the Desktop CMS requires setting the Owner's credentials, primary WhatsApp recovery phone, and secondary emergency phone.
   - Immediately sets `system_initialized = 'true'` in `store_settings`. All subsequent calls to `/api/v1/admin/auth/initialize-owner` from any machine return **`403 Forbidden`** (verified by `test_15_one_time_owner_initialization_lockout`).
3. **Session Expiration & Token Revocation (`POST /api/v1/admin/auth/logout`)**:
   - Access tokens carry a signed `exp` timestamp and unique `jti`.
   - Logging out adds the token to `REVOKED_TOKENS`, immediately rejecting any subsequent request using that token with `401 Unauthorized` (verified by `test_03`).
4. **Role-Based Access Control (`RBAC`)**:
   - Every `/api/v1/admin/*` endpoint enforces granular permission checks via `require_permission(...)` (`dashboard:read`, `products:write`, `categories:write`, `orders:write`, `content:write`, `settings:write`, `backups:write`).
   - Verified in `test_04_rbac_permission_enforcement` where a `product_manager` is allowed to manage products but blocked (`403 Forbidden`) from triggering system backups.

---

## 2. API & Transport Security Controls

| Threat / Vulnerability | Implemented Defense | Verification Test |
| :--- | :--- | :--- |
| **Client-Side Price & Delivery Fee Tampering** | `POST /api/v1/orders` ignores `client_tampered_price` and `client_submitted_total_dzd`, querying authoritative variant prices and Wilaya `home` / `stop_desk` fees from the database inside a `BEGIN IMMEDIATE` transaction. | `test_06`, `test_22` |
| **IDOR on Guest Order Tracking** | `GET /api/v1/orders/track` requires **both** `order_reference` and the matching `customer_phone`, and strips `internal_notes` and `idempotency_hash`. | `test_10` |
| **Replay Attacks & Man-in-the-Middle Tampering** | High-security CMS actions (`POST /api/v1/admin/secure-action`) verify HMAC-SHA256 signatures (`X-Luxe-Signature`) over `METHOD\|PATH\|TIMESTAMP\|NONCE\|BODY_SHA256`, enforce a 300s clock-skew window (`X-Luxe-Timestamp`), and reject reused nonces (`X-Luxe-Nonce` in `SEEN_NONCES`). | `test_16`, `test_17` |
| **SQL Injection (`SQLi`)** | 100% of SQL queries use parameterized `?` placeholders; malicious SQL payloads in search, category filters, and login fields are neutralized safely. | `test_19_sql_injection_resilience` |
| **Malicious File Upload & Path Traversal** | `validate_uploaded_image` inspects binary magic bytes (`JPEG`, `PNG`, `WEBP`), enforces a 5 MB limit, rejects `..` / `/` / `\` path traversal characters, scans for embedded PHP/JS polyglot payloads (`<?php`, `<script`, `eval(`), and renames files to `img_<sha256>.<ext>`. | `test_07`, `test_18` |
| **Brute-Force Login & Recovery Abuse** | Sliding-window IP rate limiter (`check_rate_limit`) restricts login (`5/min`), owner initialization (`3/5min`), recovery requests (`3/5min`), recovery verification (`5/5min`), and order creation (`15/min`), returning `429 Too Many Requests`. | `test_07` |
| **Private Cost Data Exposure** | `serialize_product(..., include_private=False)` strips `purchase_cost_dzd` from all public storefront endpoints. | `test_02`, `test_27` |
| **Silent Concurrent Overwrites** | `PUT /api/v1/admin/products/{id}` checks `expected_version` against the database `version` column, returning `409 Conflict` if another administrator updated the record first. | `test_11` |

---

## 3. WhatsApp Password Recovery & Honest Fallback

- **No Fake Delivery**: `POST /api/v1/admin/auth/recovery/request` checks for `WHATSAPP_CLOUD_API_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`. When absent, it returns `503 Service Unavailable` rather than pretending a WhatsApp message was sent.
- **Single-Use Hashed OTPs**: Recovery codes are hashed with `SHA-256` before storage in `admin_recovery_codes`, expire after 5 minutes (`300s`), allow at most 3 verification attempts, and are marked `is_used = 1` immediately upon use (verified by `test_09`).
- **Offline Emergency Fallback**: During First-Time Owner Setup, a high-entropy `offline_emergency` recovery code (`EMERGENCY-...`) hashed in `admin_recovery_codes` is issued for the owner's secondary emergency phone so the owner can always recover access even if Meta's WhatsApp API is unreachable.
