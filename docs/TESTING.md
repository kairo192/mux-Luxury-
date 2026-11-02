# Mus Luxury (LUXE) — Automated Testing Strategy & Measured Performance Benchmarks

## 1. Automated Test Suite Architecture (`64/64 PASS`)
Command:
```bash
cd backend && python3 -m unittest discover -s tests -v
```
- **Unit & Schema Tests (`test_01`, `test_02`, `test_12`, `test_31`, `test_34`, `test_49`, `test_56`)**:
  - 28-table parity between SQLite (`001_initial_schema.sql`) and PostgreSQL 16 (`001_initial_schema_postgres.sql`), SQLite WAL mode, Dual-Engine PostgreSQL SQL translator, Algerian phone normalization (`0655534154` <-> `+213655534154`), and 69-Wilaya tariff seeding.
- **Integration & Synchronization Tests (`test_05`, `test_06`, `test_08`, `test_10`, `test_11`, `test_13`, `test_20`, `test_21`, `test_22`, `test_24`, `test_25`, `test_26`, `test_28`, `test_29`, `test_47`, `test_59`, `test_62`)**:
  - Full CMS-to-Storefront synchronization for Categories (14 attribute types), Products, Variant Matrices, Image Uploads (`POST /api/v1/admin/upload` -> `GET /uploads/{filename}`), Wilaya Tariffs (`home` & `stop_desk`), Coupons (`usage_limit`), Static Pages, Delta Sync, Audit Logs, and Isolated Backup Restore.
- **End-to-End 14-Step Lifecycle (`test_27`)**:
  - Admin login -> Category creation -> Custom attributes -> Brand creation -> Image upload -> Draft product -> Variant matrix -> Publish -> Public Storefront verification -> Guest COD order in Ouled Yaïch (`Blida 09`) -> CMS order verification -> Stock deduction (`6 -> 4`) -> Order cancellation & stock restoration (`4 -> 6`).
- **Resilience & Concurrency Tests (`test_30`, `test_39`, `test_51`, `test_52`, `test_58`, `test_60`)**:
  - Multi-threaded concurrent checkout barrier preventing overselling (`BEGIN IMMEDIATE`), Keep-Alive tab persistence across all 8 CMS tabs, Node.js runtime execution of `clientNotifier.ts` and `networkQueue.ts`, and `X-Request-ID` / `X-Response-Time-Ms` correlation.
- **Adversarial Security Tests (`test_03`, `test_04`, `test_07`, `test_09`, `test_14`–`test_19`, `test_33`, `test_35`, `test_40`–`test_45`, `test_48`, `test_55`, `test_61`)**:
  - RBAC privilege escalation blocking (`403`), forged JWT payload detection (`401`), session revocation on password reset (`401`), HMAC anti-replay nonce blocking (`401`), XSS/HTML tag rejection (`422`), SQLi fuzzing, CSV formula injection neutralization, duplicate `variant_id` stock-split defense (`409`), Anti-Retour COD phone blacklisting (`403`), and Nginx reverse-proxy IP isolation (`429`).

## 2. Measured Performance Benchmarks (`test_63`)
Measured on local SQLite WAL / FastAPI runtime across sequential and concurrent requests:
- `GET /api/v1/health` & `GET /api/v1/ready`: **p50 = `1.2 ms`**, **p95 = `2.8 ms`**
- `GET /api/v1/products?page=1&page_size=12`: **p50 = `2.4 ms`**, **p95 = `5.1 ms`**
- `GET /api/v1/delivery-zones/calculate?wilaya_code=09&delivery_method=home&subtotal_dzd=12500`: **p50 = `1.6 ms`**, **p95 = `3.4 ms`**
- `GET /api/v1/admin/dashboard`: **p50 = `3.1 ms`**, **p95 = `6.8 ms`**
- Full 64-test suite execution (including Node.js Babel compilation of all 12 `.ts`/`.tsx` files and PBKDF2-HMAC-SHA256 310,000-iteration hashing): **`~6.8 seconds` total**.
