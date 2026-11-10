# Mus Luxury (LUXE) — API Versioning & Compatibility Policy

**Scope:** REST API (`backend/app/main.py`), Storefront Client (`apps/storefront/`), Desktop CMS / POS (`apps/desktop-cms/`)  
**Specification:** Semantic Versioning (SemVer 2.0.0)

---

## 1. Principles of Contract Immutability

Because the Windows Desktop POS is installed on physical store workstations and may remain offline for days or weeks, **backend API endpoints must never break backward compatibility with deployed desktop clients**.

### Core Tenets:
1. **Additive Schema Evolution:** New features must add new optional fields or new endpoints. Existing response keys must never be renamed or deleted.
2. **Fail-Safe Startup Verification:** Every desktop client must verify compatibility with the server during application boot before conducting cashier transactions.
3. **Graceful Degradation:** Unknown JSON fields received by the client must be ignored silently. Unknown JSON fields received by the backend must be discarded safely via Pydantic model configurations.

---

## 2. Startup Compatibility Probe (`/api/v1/pos/compat`)

The backend exposes a lightweight, unauthenticated compatibility probe:

### 2.1 Request Specification
```http
GET /api/v1/pos/compat?client_version=1.0.0 HTTP/1.1
Host: api.mus-luxury.com
```

### 2.2 Response Schema
```json
{
  "api_contract_version": "1.0.0",
  "min_supported_pos_version": "1.0.0",
  "latest_pos_version": "1.0.0",
  "client_version": "1.0.0",
  "supported": true,
  "deprecated": false
}
```

### 2.3 Client Behavioral States

| Response Condition | Client Action | User Experience |
| :--- | :--- | :--- |
| `supported: true, deprecated: false` | Normal Operation | App boots directly into login / dashboard. |
| `supported: true, deprecated: true` | Soft Warning | Non-blocking toast notification: *"Une version plus récente de Mus Luxury Caisse est disponible."* |
| `supported: false` | **Blocking Gate** | Modal dialog halts checkout: *"Version POS Obsolète : Votre version n'est plus supportée par le serveur. Veuillez mettre à jour l'application."* |

---

## 3. Versioning Lifecycles & Deprecation Windows

When breaking changes to business logic or database schemas are unavoidable:

```
[ Active Support ] --------> [ Deprecated (60-Day Window) ] --------> [ End-of-Life (Blocked) ]
     v1.0.0                           v1.0.0                                 v1.0.0
                          (Soft warning in Desktop UI)             (`supported: false` returned)
```

1. **60-Day Deprecation Window:** When an API contract changes, the minimum supported version remains set to the older version for at least 60 days.
2. **Store Owner Alerting:** Desktop CMS displays a persistent notification instructing the cashier or store manager to update the Windows application.
3. **End-of-Life Cutoff:** After the migration window lapses, `min_supported_pos_version` is bumped on the server, blocking further syncing of obsolete clients.

