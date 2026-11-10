# Mus Luxury (LUXE) — Application Security Architecture & Incident Response

## 1. Defense-in-Depth Security Controls
1. **Authentication & Session Revocation (`backend/app/security.py`)**:
   - Passwords hashed with **PBKDF2-HMAC-SHA256 (`310,000` OWASP iterations)** and 128-bit random salt (`secrets.token_hex(16)`), verified via constant-time `hmac.compare_digest`.
   - Access tokens carry `sub`, `role`, `perms`, `iat`, `iat_ns`, `exp`, and `jti`, signed with HMAC-SHA256.
   - Explicit logout adds the token to `REVOKED_TOKENS`, and password recovery verification (`POST /api/v1/admin/auth/recovery/verify`) calls `revoke_all_user_sessions(user_id)` (`USER_SESSION_REVOKED_NS`), immediately invalidating all prior tokens issued for that account (`test_61`).
2. **Role-Based Access Control (RBAC)**:
   - Enforced server-side via `Depends(require_permission("..."))` across every `/api/v1/admin/*` route (`test_03`, `test_04`, `test_45`).
3. **Cryptographic Request Signing & Anti-Replay (`Section 8`)**:
   - Sensitive mutations verify `X-Luxe-Signature` (`HMAC-SHA256(method|path|timestamp|nonce|sha256(body))`), enforce a 300-second clock skew window on `X-Luxe-Timestamp`, and block replayed nonces via bounded `SEEN_NONCES` (`test_16`, `test_17`).
4. **Windows Credential Manager (`wincred`) Desktop Token Storage**:
   - The Tauri 2 Desktop CMS (`apps/desktop-cms/src-tauri/src/main.rs`) binds `luxe_cms_access_token` and `luxe_cms_hmac_secret` to the native OS Keychain (`service = "dz.musluxury.cms.wincred"`) via `keyring` (`windows-native`) and `tauri-plugin-store`. Zero tokens are ever stored in `window.localStorage` (`test_41`).
5. **Input Validation, XSS, SQLi, & CSV Formula Injection Defenses**:
   - All SQL queries use parameterized placeholders (`?` / `%s`).
   - `GuestOrderCreate` rejects `<script>`, `<iframe>`, `<svg>`, `<img>`, `javascript:`, `onerror=`, and `< >` angle brackets (`422 Unprocessable Entity`, `test_42`).
   - `GET /api/v1/admin/orders/export.csv` neutralizes Excel/DDE formula prefixes (`=`, `-`, `@`, `+`) with a leading single quote while preserving `+213...` phone numbers (`test_44`).
   - `POST /api/v1/admin/upload` inspects magic bytes (`JPEG`, `PNG`, `WEBP`), enforces a 5 MB ceiling, blocks path traversal (`..`, `/`, `\`), and scans for embedded polyglot script tags (`<?php`, `<script`, `eval(`, `test_07`, `test_18`, `test_47`).
6. **Client-Side Error Sanitization (`apps/desktop-cms/src/utils/clientNotifier.ts`)**:
   - Strips all raw backend exceptions, SQLite/PostgreSQL errors, Python tracebacks, and `[object Object]` validation arrays, translating every error into polite French Modal Message Boxes (`test_51`, `test_52`).

## 2. Operational Incident Response Runbook
- **Scenario A — Suspected Administrator Credential or Token Compromise**:
  1. Run the offline CLI emergency reset on the VPS:
     `docker compose exec api python3 scripts/emergency_reset_owner.py --email admin@mus-luxury.com --phone 0655534154`
  2. Rotate `SECRET_KEY` in `.env` and restart `api` (`docker compose up -d api`) to invalidate all active tokens globally.
  3. Inspect `/api/v1/admin/audit-logs` (Tab 8 in Desktop CMS) to review all actions performed during the window.
- **Scenario B — Database Corruption or Accidental Bulk Modification**:
  1. Trigger or select the latest verified `.sql.gz` archive in Tab 8 (`Sauvegardes & Sécurité`) and run **Tester la restauration isolée** (`POST /api/v1/admin/backups/{id}/verify-restore`).
  2. Restore onto PostgreSQL via `./infrastructure/backups/restore_backup.sh /var/lib/luxe/backups/<archive>.sql.gz`.
- **Scenario C — Abusive COD Non-Pickup / Repeat Return Fraud**:
  1. Open Tab 5 (`5. Commandes & Factures`) in the Desktop CMS, inspect the automatic `cod_risk` badge next to the customer phone, and click **🚫 Bloquer Numéro (Anti-Retour)** (`POST /api/v1/admin/cod-risk/blacklist`). Future guest checkouts from that phone are blocked at `POST /api/v1/orders` with `HTTP 403`.
