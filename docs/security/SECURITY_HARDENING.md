# Mus Luxury (LUXE) — Security Architecture & Hardening Guide

**Target Environment:** Production E-Commerce & Windows POS Ecosystem  
**Compliance Standards:** OWASP Top 10 (2021/2026), ANPD Algeria Data Protection Standards  
**Domain Scope:** `https://mus-luxury.com`, `https://api.mus-luxury.com`

---

## 1. Threat Model & Defense-in-Depth Architecture

```text
Internet / Cash Register
          │
    [ UFW Firewall ] (Ports 22, 80, 443 only; 5432 and 8000 blocked)
          │
    [ Nginx SSL Proxy ]
      - TLS 1.3 / Modern Ciphers
      - HSTS Preload (63,072,000s)
      - CSP without external script CDNs
      - Sliding-Window Rate Limiting (5r/m auth, 10r/m orders)
      - Anti-Slowloris Timeouts (10s headers, 10s body)
          │
    [ FastAPI Backend ]
      - Real Client IP extraction (trusted proxy subnets only)
      - PBKDF2-SHA256 (600,000 iterations)
      - JWT with nano-timestamp `iat_ns` & instant revocation
      - Fail-closed SECRET_KEY validation
      - Parameterized SQL translation (%s escaping)
      - Zero default admin seed in production
          │
    [ PostgreSQL 16 ]
      - Internal Docker bridge only (no public host ports)
      - Non-root DB user with least privilege
```

---

## 2. Authentication & Credential Security

### 2.1 Password Hashing
- **Algorithm:** `PBKDF2-HMAC-SHA256` with **600,000 iterations** (OWASP recommendation).
- **Salt:** 16 bytes of cryptographically secure random bytes from `os.urandom()`.
- **Backward Compatibility:** The password verifier transparently verifies older 310,000-iteration hashes and rehashes them to 600,000 iterations upon successful login.

### 2.2 JWT Session Management & Instant Revocation
- **Token Claims:** `sub` (user ID), `role` (role name), `exp` (expiration), and `iat_ns` (issued-at nano timestamp).
- **Instant Revocation:** When a password is changed or an account is locked, `USER_SESSION_REVOKED_NS[user_id]` is updated. Any token issued prior to that timestamp is rejected with `401 Unauthorized` (`SESSION_REVOKED`), preventing replay of compromised tokens.

### 2.3 Zero-Admin Production Gate
When `APP_ENV=production`:
- The database seeder (`backend/app/seed.py`) strictly refuses to create default administrative accounts (e.g. `admin@mus-luxury.com`) or static emergency tokens.
- The `admin_users` table remains empty until the store owner executes the first-time setup wizard via the Desktop CMS.
- The setup wizard permanently locks itself upon owner registration.

---

## 3. Desktop POS Native Security (Tauri 2 / Rust)

### 3.1 OS Credential Manager Integration (`wincred`)
- The Windows Desktop CMS **NEVER** stores session tokens, refresh tokens, or HMAC secrets in browser `localStorage`.
- All credentials are encrypted and stored in the **Windows Credential Manager** via the Rust `keyring` crate under service name `com.musluxury.cms.wincred`.
- Web scripts or malicious extensions inside the WebView cannot inspect or exfiltrate tokens.

### 3.2 Offline Data Durability
- Offline sales are queued in `pos_mirror.sqlite3` on disk (`%APPDATA%/pos_mirror.sqlite3`).
- Clearing browser history or WebView cache leaves the SQLite database untouched.

---

## 4. Network & Rate Limiting Hardening

### 4.1 Nginx Memory-Backed Rate Limiting Zones
```nginx
# Sliding-window rate limit zones
limit_req_zone $binary_remote_addr zone=general_api:15m rate=15r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=orders_limit:10m rate=10r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
```

- **Brute-Force Protection:** `/api/v1/admin/auth/` is strictly capped at **5 requests per minute** per IP with burst=3.
- **Order Flooding / Bot Protection:** `/api/v1/orders` is capped at **10 requests per minute** with burst=5.
- **Concurrent Connections:** Bounded to 25 simultaneous TCP connections per IP.

### 4.2 Real Client IP Resolution
Because the backend sits behind Nginx, rate limiting and audit logs must not log the proxy's internal container IP (`172.x.x.x`). The backend implements `get_real_client_ip(request)`:
- Reads `X-Real-IP` and `X-Forwarded-For`.
- Only honors proxy headers when the direct peer is within trusted RFC 1918 private Docker subnets (`172.16.0.0/12`, `10.0.0.0/8`, `127.0.0.1/8`).

---

## 5. HTTP Security Headers & CSP

The following headers are returned on all responses:

```nginx
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https://mus-luxury.com https://api.mus-luxury.com; connect-src 'self' https://api.mus-luxury.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;
```

---

## 6. Input Validation & Upload Defenses

1. **Magic-Byte Image Validation:** All uploaded product images must match true `JPEG` (`FF D8 FF`), `PNG` (`89 50 4E 47`), or `WEBP` headers. Polyglot PHP/HTML scripts masked with image extensions are rejected.
2. **Path Traversal Shield:** Upload filenames are generated with cryptographically random hex strings (`secrets.token_hex(16)`). Original user-provided filenames are completely discarded.
3. **CSV Formula Injection:** Data export routines escape formulas starting with `=`, `+`, `-`, or `@` by prepending a single quote (`'`).

