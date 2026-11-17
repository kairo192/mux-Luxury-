# Documentation — where to look

Start with the first table. The guides there are kept up to date with the code.

## Current guides

| Need | Read |
|---|---|
| Run the shop day to day (owner): backups, restore, new database, updates, keys | [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md) |
| Use the desktop CMS, screen by screen (staff and owner, English PDF with screenshots) | [user-guide/Mus_Luxury_CMS_User_Guide_EN.pdf](user-guide/Mus_Luxury_CMS_User_Guide_EN.pdf) |
| Every `.env` key, how to check a file | [CONFIGURATION.md](CONFIGURATION.md) |
| Put the shop on the VPS | [deployment/VPS_DEPLOYMENT.md](deployment/VPS_DEPLOYMENT.md) |
| CI, deploys, releases, rollback, migrations | [cicd/README.md](cicd/README.md) (and the files next to it) |
| Off-site backup copy (Backblaze B2 / Cloudflare R2), monitoring, disaster recovery | [cicd/BACKUP_OFFSITE.md](cicd/BACKUP_OFFSITE.md) · [cicd/ROLLBACK.md](cicd/ROLLBACK.md) |
| Windows desktop CMS: build, signing, updates | [DESKTOP_CMS_RELEASE_GUIDE.md](DESKTOP_CMS_RELEASE_GUIDE.md) |
| Printers, cash drawer, offline till | [cicd/POS_HARDWARE.md](cicd/POS_HARDWARE.md) · [POS_OFFLINE_ARCHITECTURE.md](POS_OFFLINE_ARCHITECTURE.md) |
| How the system fits together | [architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) · [../apps/desktop-cms/ARCHITECTURE.md](../apps/desktop-cms/ARCHITECTURE.md) |
| Secrets and security | [security/SECRETS_MANAGEMENT.md](security/SECRETS_MANAGEMENT.md) · [security/SECURITY_HARDENING.md](security/SECURITY_HARDENING.md) |
| Tests (backend, browser) | [TESTING.md](TESTING.md) · [../e2e/README.md](../e2e/README.md) |
| The API: every endpoint and who may call it (generated), request/response shapes, main endpoints explained | [api/ENDPOINTS.md](api/ENDPOINTS.md) · [api/openapi.json](api/openapi.json) · [api/API_INVENTORY.md](api/API_INVENTORY.md) · [api/API_CONTRACT.md](api/API_CONTRACT.md) · [api/API_COMPATIBILITY_POLICY.md](api/API_COMPATIBILITY_POLICY.md) |
| What was changed, round by round | [WORK_SUMMARY_2026-11-11.md](WORK_SUMMARY_2026-11-11.md) |

## Other folders

| Folder | Content |
|---|---|
| [../.agent/](../.agent/README.md) | The AI assistants' skills (design guidelines, security-audit checklists): not part of the shop, never shipped |
| [handoff/](handoff/) | Notes and prompts for the AI assistants working on the PC (Antigravity, Claude) |
| [specs/](specs/) | The owner's original requests and specifications, kept as written: file names they ask for are those of the time (e.g. `BACKUP_RESTORE.md`, `TEST_REPORT.md`, since moved to `archive/`). For the current version of any document, use the table above |
| [archive/](archive/) | Older documents replaced by the guides above — kept for history, may be out of date |
| [brand-images/](brand-images/) | Source brand pictures (logo banner, product scenes) |
| [operations/](operations/) | Server runbooks for the system administrator: backup & restore, maintenance, troubleshooting, incident runbook, database maintenance, monitoring & logs, VPS tuning |
| [deployment/](deployment/), [security/](security/) | VPS deployment and pre-flight checklist; security hardening and secrets |
| [api/](api/) | The API reference (see the table above). `ENDPOINTS.md` and `openapi.json` are generated: `cd backend && python3 scripts/generate_api_docs.py` |
