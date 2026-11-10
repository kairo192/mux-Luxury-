# MUS LUXURY — FULL PRODUCTION READINESS, SECURITY HARDENING, CODEBASE RESTRUCTURING & OCTENIUM VPS INTEGRATION

## ROLE

Act as a Senior Software Architect, DevSecOps Engineer, Backend Engineer, Database Engineer, Infrastructure Engineer, and Application Security Specialist.

Your mission is to take the existing **Mus Luxury** codebase and turn it into a properly engineered, secure, maintainable, production-ready e-commerce ecosystem.

This is an implementation task, not merely an audit.

You are authorized to inspect, modify, restructure, test, configure, and improve the project. You are also authorized to connect to my Octenium VPS using SSH to inspect and prepare the server.

Do not blindly rewrite the project. Understand the existing architecture and preserve working functionality.

---

# 1. PROJECT AND INFRASTRUCTURE CONTEXT

## Project

Name: Mus Luxury

Production domain:
- https://mus-luxury.com
- https://www.mus-luxury.com
- https://api.mus-luxury.com

Architecture:

1. Public e-commerce storefront: React, Vite, TypeScript.
2. Desktop CMS/POS: Tauri 2, Rust, React, TypeScript, installed locally on Windows computers.
3. Backend: Python 3.11, FastAPI, Uvicorn.
4. Production database: PostgreSQL.
5. Development/testing database: SQLite.
6. Desktop local database: SQLite, with offline POS operations and synchronization.
7. Reverse proxy: Nginx.
8. Infrastructure: Docker and Docker Compose.
9. CI/CD: GitHub Actions.
10. Repository: GitHub.

The desktop CMS is a Windows application, NOT a web-based administration dashboard.

The desktop CMS must communicate with the production backend through:

`https://api.mus-luxury.com`

The public storefront must communicate with the same backend.

The server must remain the authoritative source for shared production data.

## Octenium VPS

Existing server:

- Provider: Octenium
- OS: Ubuntu 24.04.5 LTS
- Public IPv4: 5.196.163.6
- CPU: 1 vCore
- RAM: 2 GB
- Disk: 40 GB actual provisioned capacity
- Bandwidth: 250 Mbps
- Swap: 2 GB
- cgroups: v2
- UFW enabled
- SSH port: 22
- HTTP: 80
- HTTPS: 443

Current known state:

- Docker is not installed.
- PostgreSQL is not installed.
- Nginx is not installed.
- No production application is currently listening on ports 80/443.
- SSH root access currently works.
- Root login and password authentication are currently enabled.
- UFW currently allows SSH, HTTP, and HTTPS.
- Runtime `vm.swappiness` was changed to 10, but persistence must be checked.
- Actual disk capacity is 40 GB, not 150 GB.

Do not assume any of these details are still unchanged. Verify them through SSH before acting.

---

# 2. PHASE ONE — COMPLETE CODEBASE DISCOVERY

Before modifying anything:

1. Inspect the entire repository.
2. Read the existing architecture documentation and previous audit report.
3. Identify all applications, services, packages, modules, dependencies, scripts, configuration files, and deployment infrastructure.
4. Map every frontend-to-backend connection.
5. Map every backend-to-database connection.
6. Map desktop CMS synchronization and offline workflows.
7. Identify duplicated code, unused modules, abandoned implementations, dead routes, unnecessary dependencies, and inconsistent naming.
8. Identify insecure defaults, hardcoded credentials, exposed secrets, missing validation, and incorrect configurations.
9. Verify that existing Git changes are preserved.

Produce an internal architecture map before making significant modifications.

Do not assume the previous audit report is accurate. Verify its findings against the actual source code.

---

# 3. PHASE TWO — RESTRUCTURE AND ORGANIZE THE CODEBASE

Organize the repository into a clean, professional, maintainable monorepo.

Target structure (adapt it to the existing project instead of forcing an unnecessary rewrite):

```text
mus-luxury/
│
├── apps/
│   ├── storefront/
│   └── desktop-cms/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── security/
│   │   ├── middleware/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   ├── scripts/
│   ├── monitoring/
│   └── backups/
│
├── .github/
│   └── workflows/
│
├── docs/
│   ├── architecture/
│   ├── deployment/
│   ├── security/
│   ├── operations/
│   └── troubleshooting/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Rules:

- Preserve all working features.
- Update import paths, build configurations, Dockerfiles, workflows, and scripts when moving files.
- Remove obsolete code only after verifying that nothing depends on it.
- Keep application boundaries clear.
- Avoid circular dependencies.
- Avoid unnecessary abstractions.
- Do not introduce additional technologies without a concrete technical reason.

---

# 4. PHASE THREE — ENVIRONMENT VARIABLES AND REAL SECRETS

This phase is critical.

Inspect the entire codebase for every configuration value, credential, token, password, secret, API key, certificate, and environment variable.

Search for:

- Hardcoded passwords.
- JWT secrets.
- Refresh token secrets.
- Database credentials.
- API keys.
- HMAC secrets.
- Encryption keys.
- Webhook secrets.
- SMTP credentials.
- WhatsApp credentials.
- Payment provider credentials.
- Shipping provider credentials.
- OAuth credentials.
- Tauri updater signing keys.
- Any other third-party integration secrets.

## 4.1 Build a complete environment configuration

Create a proper `.env.example` based on the ACTUAL codebase.

Do not generate random unused environment variables.

For every variable document:

- Variable name.
- Purpose.
- Required or optional.
- Which service consumes it.
- Whether it can be generated locally.
- Whether it must be obtained from an external provider.

Separate configuration logically where necessary:

- Backend environment.
- PostgreSQL environment.
- Storefront public build-time environment.
- Desktop CMS configuration.
- VPS production environment.
- CI/CD deployment secrets.

Never place server-only secrets in Vite `VITE_*` variables or frontend bundles.

Never expose backend secrets to the desktop application.

## 4.2 Generate application secrets

You are authorized to generate cryptographically secure secrets for application-owned systems, including:

- JWT signing secrets.
- Refresh token secrets.
- HMAC keys.
- Session secrets.
- Encryption keys where the existing architecture requires them.
- Database passwords.
- Internal service credentials.

Use cryptographically secure random generation.

Use suitable lengths and formats.

Do not use:

- Predictable strings.
- Default passwords.
- Example secrets.
- Repeated secrets across unrelated services.
- Weak development keys in production.

If an existing production secret is already in use, do not rotate it blindly. Assess compatibility and create a safe rotation procedure.

## 4.3 Real third-party credentials

Do not invent real external provider credentials.

For credentials that require an external account, identify exactly where they must be obtained.

Examples:

- WhatsApp Business Cloud API.
- SMTP/email provider.
- Payment gateway.
- Shipping/logistics provider.
- OAuth providers.
- External analytics or monitoring services.

If a credential is missing:

1. Mark the integration as not configured.
2. Explain where to obtain the credential.
3. Identify the exact environment variable name.
4. Keep the integration disabled or safely unavailable.
5. Never pretend that a fake token is a real working integration.

## 4.4 Secret storage

Local development:

- Use local `.env` files.
- Ensure `.env` is ignored by Git.
- Keep `.env.example` committed.
- Verify no actual secrets are tracked.

Production:

- Store secrets on the VPS in a protected location.
- Prefer Docker Compose secrets or protected environment files according to compatibility.
- Restrict file permissions.
- Never expose secrets through logs, API responses, error messages, frontend assets, or GitHub artifacts.

Use appropriate file permissions such as `600` for sensitive environment files.

GitHub Actions:

- Store deployment credentials and signing keys in GitHub Actions Secrets.
- Never commit private SSH keys, updater private keys, or production secrets.
- Do not print secret values during workflows.

If any real credential is already exposed in Git history, report it and recommend revocation and rotation. Removing it from the current file is not sufficient.

---

# 5. PHASE FOUR — APPLICATION SECURITY HARDENING

Perform a real security review and implement fixes.

## Backend security

Verify and harden:

- Authentication and authorization.
- Password hashing.
- JWT creation and validation.
- Refresh token handling.
- Token revocation.
- Session expiration.
- Role-based access control.
- Input validation.
- SQL injection protection.
- CORS configuration.
- CSRF protection where applicable.
- Rate limiting.
- Request size limits.
- File upload validation.
- MIME type validation.
- Path traversal protection.
- Error handling.
- Logging.
- Security headers.
- Sensitive data exposure.
- API documentation exposure.
- Dependency vulnerabilities.

Use parameterized database queries.

Do not trust the frontend to enforce permissions.

Every sensitive operation must be authorized by the backend.

## Storefront security

Verify:

- API communication uses HTTPS.
- No private credentials are included in JavaScript bundles.
- Checkout validation happens on the server.
- Prices and totals are calculated or verified by the backend.
- Stock availability is checked server-side.
- Product image uploads are validated.
- Customer information is protected.
- No unauthorized access to CMS functions is possible.

## Desktop CMS security

Verify:

- Tauri capabilities are minimal.
- Dangerous permissions are not unnecessarily enabled.
- IPC commands validate their inputs.
- Local database access is protected.
- Credentials are stored using Windows Credential Manager where supported.
- Tokens are not stored in plaintext localStorage.
- API communication validates TLS certificates normally.
- Offline queues cannot be modified into unauthorized transactions without server-side validation.
- Update signing is configured correctly.

Do not disable TLS verification to make API connections work.

## Database security

Verify:

- PostgreSQL is not publicly exposed.
- Database users have minimum required permissions.
- Application credentials are separate from administrative credentials.
- Backups are protected.
- Database migrations are version-controlled.
- Sensitive information is not unnecessarily stored.
- Transaction integrity is preserved.

---

# 6. PHASE FIVE — OCTENIUM VPS SSH CONNECTION AND SERVER PREPARATION

You are authorized to connect to my Octenium VPS through SSH.

Server:

`root@5.196.163.6`

Use the existing SSH credentials or SSH key already configured in the environment.

Do not request that I paste passwords, private keys, or tokens into source code or chat.

If authentication is unavailable, stop and tell me exactly what access is missing. Do not attempt to bypass SSH authentication.

## 6.1 Initial server inspection

Connect and inspect:

- Ubuntu version.
- CPU and RAM.
- Disk usage.
- Swap.
- Running processes.
- Open ports.
- Firewall rules.
- SSH configuration.
- Installed packages.
- Docker status.
- Existing containers.
- Existing databases.
- Existing Nginx configuration.
- Existing system services.
- Existing application directories.
- Existing users and permissions.
- Existing backups.
- Existing DNS resolution where relevant.

Do not overwrite existing server configurations without understanding them.

## 6.2 VPS optimization

The server has only 1 vCore and 2 GB RAM.

Optimize conservatively.

Do not apply generic optimization scripts.

Do not disable essential Ubuntu services.

Do not disable swap.

Do not install unnecessary software.

Check memory pressure, disk usage, CPU usage, and I/O before recommending tuning.

Use appropriate resource limits for Docker containers.

Use Docker log rotation.

Avoid building React applications or compiling Tauri/Rust applications on the VPS. Build them on GitHub Actions runners.

## 6.3 Install and configure Docker

If Docker is not installed, install it using the official Docker APT repository for Ubuntu 24.04.

Do not use Snap Docker.

Configure:

- Docker Engine.
- Docker Compose plugin.
- Docker daemon.
- Log rotation.
- Restart policies.
- Resource limits.
- Persistent volumes.
- Secure permissions.

Verify Docker installation and Compose functionality.

Do not expose Docker API over TCP.

## 6.4 Production server architecture

Prepare this architecture:

```text
                    INTERNET
                       |
                       |
                HTTPS / TLS
                       |
                       |
                 NGINX REVERSE
                    PROXY
                       |
          +------------+------------+
          |            |            |
          |            |            |
      Storefront    FastAPI API   Static/media
      mus-luxury    api.mus-luxury
          |            |
          |            |
       React/Vite   Backend service
                       |
                       |
                   PostgreSQL
                       |
                       |
                Persistent storage
```

Desktop CMS:

```text
Windows Desktop CMS
        |
        | HTTPS
        |
api.mus-luxury.com
        |
        |
FastAPI Backend
        |
        |
PostgreSQL
```

PostgreSQL must remain private and accessible only to authorized services.

Only necessary public ports should be exposed:

- 22: SSH.
- 80: HTTP redirect and certificate validation.
- 443: HTTPS.

Do not publish PostgreSQL port 5432.

Review Docker networking and firewall behavior. Docker-published ports can bypass ordinary UFW filtering. Verify actual externally reachable ports instead of assuming UFW alone protects them.

## 6.5 Nginx and HTTPS

Configure:

- `mus-luxury.com`
- `www.mus-luxury.com`
- `api.mus-luxury.com`

Use HTTPS with valid certificates.

Configure:

- HTTP to HTTPS redirects.
- Reverse proxy headers.
- API request limits.
- Appropriate timeouts.
- Static asset caching.
- Compression where appropriate.
- Security headers.
- Correct upload limits.
- WebSocket support only if required.

Do not assume DNS is configured.

Inspect DNS records before requesting certificates.

Preserve existing email-related DNS records such as MX, SPF, DKIM, and DMARC.

If DNS changes are required, document the exact records and wait for my approval before modifying them.

---

# 7. PHASE SIX — DATABASE AND BACKEND PRODUCTION READINESS

Inspect all database operations.

Verify:

- PostgreSQL connection management.
- Connection lifecycle.
- Connection pooling where justified.
- Transaction handling.
- Migration ordering.
- Foreign keys.
- Indexes.
- Constraints.
- Data integrity.
- Concurrent operations.
- Error recovery.

Do not blindly introduce an ORM if the existing raw SQL architecture is appropriate.

If connection pooling is needed, implement it carefully and size it for the 2 GB VPS.

Check all critical workflows:

- Product creation and updates.
- Categories and attributes.
- Variants.
- Colors and sizes.
- Stock management.
- Purchase records.
- Sales.
- Orders.
- Customer data.
- POS transactions.
- Treasury/accounting.
- Inventory movement ledger.
- Reports.
- Audit logs.
- Backups and restoration.

Verify that purchase prices, sale prices, margins, totals, discounts, and stock calculations are correct.

Never allow negative stock or inconsistent inventory unless explicitly supported by the business rules.

---

# 8. PHASE SEVEN — OFFLINE POS AND DESKTOP SYNCHRONIZATION

This is a critical component.

The desktop CMS must continue operating during temporary internet outages where the existing design supports offline operation.

Verify:

- SQLite local database.
- Offline product lookup.
- Offline transaction creation.
- Persistent synchronization queue.
- Unique transaction IDs.
- Idempotent synchronization.
- Duplicate transaction prevention.
- Retry handling.
- Conflict detection.
- Conflict resolution.
- Transaction integrity.
- Recovery after application restart.
- Recovery after Windows restart.
- Handling server timeouts.
- Handling partial synchronization failures.

Do not silently discard failed transactions.

Do not report a transaction as synchronized before the server confirms it.

The backend must independently validate transactions.

If two terminals sell the same remaining stock while offline, explain the unavoidable consistency limitation and implement a safe reconciliation strategy. Do not claim that offline multi-terminal inventory is perfectly consistent.

Test the synchronization process under realistic failure conditions.

---

# 9. PHASE EIGHT — CI/CD AND GITHUB INTEGRATION

Inspect existing GitHub Actions workflows.

Improve or implement:

## Continuous Integration

On pull requests and relevant pushes:

- Backend tests.
- Python linting.
- Type checking where configured.
- Dependency security checks.
- Frontend linting.
- TypeScript checks.
- Storefront production build.
- Desktop CMS frontend checks.
- Rust formatting and checks.
- Rust tests.
- Docker build validation.
- Configuration validation.
- Migration checks.

Fail workflows when critical checks fail.

Do not silently ignore errors.

## Continuous Deployment

Implement separate deployment stages:

1. CI validation.
2. Build production artifacts on GitHub runners.
3. Deploy to staging if staging exists and is configured.
4. Run health checks.
5. Require manual approval for production.
6. Back up the database before production migrations.
7. Deploy application artifacts.
8. Apply migrations safely.
9. Verify application health.
10. Roll back application releases if deployment fails.

Do not claim zero downtime unless the actual infrastructure supports it.

For a single VPS, document realistic downtime risks.

## Desktop CMS releases

Create a separate Windows build and release workflow.

Build signed Windows installers.

Configure Tauri updater properly.

Generate a real updater signing key only through a secure process.

Keep the private signing key outside the repository.

Store it in an appropriately protected GitHub Actions secret.

Never use placeholder public keys in production.

Do not publish an update until the signing and verification process is tested.

---

# 10. PHASE NINE — BACKUPS, MONITORING AND RECOVERY

Implement a practical backup strategy for the available storage.

Back up:

- PostgreSQL.
- Product media.
- Important application data.
- Required configuration, excluding secrets where possible.

Implement:

- Automated backup scheduling.
- Retention policy.
- Compression.
- Integrity verification.
- Backup logs.
- Restore procedure.
- Restore testing.

Do not treat a successful backup command as proof that recovery works.

Document how to restore the application and database after VPS failure.

Monitor:

- CPU.
- RAM.
- Disk.
- Container health.
- API availability.
- Database availability.
- Disk growth.
- Backup success.
- Application errors.

Avoid heavy monitoring stacks that consume excessive memory on this VPS.

Use lightweight monitoring where appropriate.

---

# 11. PHASE TEN — COMPLETE INTEGRATION AND FUNCTIONAL VERIFICATION

Do not stop after successful compilation.

Trace and verify the complete application flow.

Storefront:

- Product listing.
- Product details.
- Categories.
- Variants.
- Cart.
- Checkout.
- Order creation.
- Stock validation.
- API error handling.

Desktop CMS:

- Authentication.
- Dashboard.
- Product management.
- Category management.
- Inventory.
- Purchasing.
- POS.
- Sales.
- Customers.
- Accounting.
- Reports.
- Settings.
- Backup operations.
- Offline mode.
- Synchronization.

Backend:

- Every API route.
- Authentication dependencies.
- Role permissions.
- Database queries.
- Request and response schemas.
- Error handling.
- Audit logging.

For every visible button and form:

1. Identify its intended action.
2. Verify its event handler.
3. Verify the API or local operation.
4. Verify loading state.
5. Verify success and failure handling.
6. Verify validation.
7. Verify that it does not silently fail.

Identify disconnected, mocked, placeholder, or fake functionality.

Do not present mock functionality as production-ready.

Test the complete workflow from storefront to backend to database and from desktop CMS to backend to database.

---

# 12. PHASE ELEVEN — DOMAIN, DNS AND PRODUCTION CONFIGURATION

Verify that all project configuration uses the correct domain:

- `mus-luxury.com`
- `www.mus-luxury.com`
- `api.mus-luxury.com`

Search the entire repository for incorrect old domains, including:

- `.dz`
- `musluxury.dz`
- Old localhost production URLs.
- Hardcoded development IP addresses.
- Obsolete API endpoints.

Update only where technically appropriate.

Do not modify DNS records without my approval.

Produce a DNS checklist with exact record types, names, values, and purposes.

Do not assume a DNS record exists because the domain was purchased from Octenium.

---

# 13. STRICT EXECUTION AND SAFETY RULES

You have permission to:

- Inspect the repository.
- Modify project source code.
- Restructure the repository.
- Install project dependencies.
- Generate application-owned secrets.
- Create production configuration templates.
- Connect to the VPS using authorized SSH credentials.
- Install Docker and required server packages.
- Prepare Docker Compose.
- Prepare Nginx.
- Prepare the database environment.
- Configure firewall rules where necessary and safe.
- Create deployment and backup scripts.
- Implement CI/CD workflows.
- Run tests.
- Verify services.

However, these operations require my explicit approval before execution:

1. Changing public DNS records.
2. Deploying the public storefront or API to production.
3. Replacing or deleting existing production data.
4. Running destructive database migrations.
5. Deleting existing server directories or Docker volumes.
6. Rotating an existing production credential that could break running services.
7. Changing SSH authentication in a way that could lock me out.
8. Disabling password SSH authentication.
9. Changing root access.
10. Publishing desktop releases.
11. Making irreversible changes to the live environment.

Do not:

- Invent external API credentials.
- Print secrets in terminal output or logs.
- Commit `.env` files.
- Commit private keys.
- Disable TLS verification.
- Expose PostgreSQL publicly.
- Open unnecessary firewall ports.
- Use unverified third-party installation scripts.
- Run destructive cleanup commands without inspecting their targets.
- Delete existing backups.
- Overwrite existing configuration blindly.
- Push code to GitHub without authorization.
- Deploy production without approval.

Maintain a clear distinction between:

- Local development.
- Staging.
- Production.

Never mix their credentials or databases.

---

# 14. IMPLEMENTATION STRATEGY

Work in controlled phases.

At the beginning of each phase:

1. Explain what you discovered.
2. Identify the problems.
3. State the planned changes.
4. Identify any risk.
5. Implement the changes that are authorized.
6. Run relevant tests.
7. Report the results.

Do not stop after generating a plan. Implement the authorized work.

Do not perform a massive refactor in one uncontrolled operation.

Keep changes incremental and reviewable.

Maintain Git checkpoints or branches where appropriate without overwriting existing work.

If a change could break a working feature, investigate before modifying it.

If a required credential, permission, DNS record, or external provider account is missing, document the blocker instead of fabricating a solution.

---

# 15. FINAL HANDOVER — REQUIRED DELIVERABLES

At completion, provide a detailed handover report.

Create or update:

1. `README.md`
2. `docs/architecture/SYSTEM_ARCHITECTURE.md`
3. `docs/deployment/VPS_DEPLOYMENT.md`
4. `docs/deployment/CI_CD.md`
5. `docs/security/SECURITY_HARDENING.md`
6. `docs/security/SECRETS_MANAGEMENT.md`
7. `docs/operations/BACKUP_AND_RESTORE.md`
8. `docs/operations/MAINTENANCE.md`
9. `docs/operations/TROUBLESHOOTING.md`
10. `.env.example`

The final report must include:

### A. Codebase
- Previous structure.
- New structure.
- Files changed.
- Files removed and justification.
- Dependencies added or removed.

### B. Architecture
- Storefront architecture.
- Desktop CMS architecture.
- Backend architecture.
- Database architecture.
- Offline synchronization.
- Network communication.
- Security boundaries.

### C. Secrets
- All required environment variables.
- Which secrets were generated.
- Where they are stored.
- Which external credentials are still missing.
- Which GitHub Actions secrets must be configured.
- Any credentials that require rotation.

Never include actual secret values in this report.

### D. VPS
- SSH connection status.
- Installed packages.
- Docker status.
- PostgreSQL status.
- Nginx status.
- Firewall configuration.
- Publicly exposed ports.
- Storage layout.
- Resource limits.
- Server configuration.
- Remaining infrastructure tasks.

### E. CI/CD
- Workflows implemented.
- Build process.
- Test process.
- Deployment process.
- Approval gates.
- Rollback process.
- Desktop release process.

### F. Verification
- Backend tests.
- Frontend tests.
- Rust tests.
- Integration tests.
- Security checks.
- Docker builds.
- API health checks.
- Database migration checks.
- Offline synchronization tests.
- Remaining untested physical hardware.

For each test, report the actual result. Do not claim success for a test that was not executed.

### G. Production readiness assessment

Give separate scores with evidence:

- Architecture: /100
- Code quality: /100
- Backend security: /100
- Storefront security: /100
- Desktop security: /100
- Database reliability: /100
- Offline POS reliability: /100
- Infrastructure security: /100
- CI/CD: /100
- Backup and recovery: /100
- Overall production readiness: /100

A score must reflect verified implementation, not intentions or documentation.

### H. Final status

Clearly classify every major component as:

- COMPLETED AND VERIFIED
- IMPLEMENTED BUT NOT VERIFIED
- BLOCKED — REQUIRES OWNER ACTION
- NOT IMPLEMENTED
- REQUIRES PRODUCTION APPROVAL

Finish with an exact checklist of what I personally need to do before the first real production deployment.

---

# FINAL OBJECTIVE

Deliver a secure, maintainable, fully integrated Mus Luxury ecosystem consisting of:

- A production-ready public storefront.
- A reliable Windows desktop CMS/POS.
- A secure FastAPI backend.
- A properly protected PostgreSQL database.
- Reliable offline POS synchronization.
- A hardened and optimized Octenium VPS.
- Secure domain and HTTPS configuration.
- Automated CI/CD.
- Signed desktop releases and updates.
- Verified backups and recovery.
- Complete technical documentation.

The objective is not to make the project merely look production-ready.

The objective is to make the actual code, infrastructure, security controls, deployment process, and business workflows production-ready.

Be strict. Verify everything. Do not hide technical debt. Do not fabricate success. Do not sacrifice security or existing functionality just to finish faster.