# Documentation — where to look

Start with the first table. The guides there are kept up to date with the code.

## Current guides

| Need | Read |
|---|---|
| Run the shop day to day (owner): backups, restore, new database, updates, keys | [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md) |
| Every `.env` key, how to check a file | [CONFIGURATION.md](CONFIGURATION.md) |
| Put the shop on the VPS | [deployment/VPS_DEPLOYMENT.md](deployment/VPS_DEPLOYMENT.md) |
| CI, deploys, releases, rollback, migrations | [cicd/README.md](cicd/README.md) (and the files next to it) |
| Off-site backup copy (Backblaze B2 / Cloudflare R2), monitoring, disaster recovery | [cicd/BACKUP_OFFSITE.md](cicd/BACKUP_OFFSITE.md) · [cicd/ROLLBACK.md](cicd/ROLLBACK.md) |
| Windows desktop CMS: build, signing, updates | [DESKTOP_CMS_RELEASE_GUIDE.md](DESKTOP_CMS_RELEASE_GUIDE.md) |
| Printers, cash drawer, offline till | [cicd/POS_HARDWARE.md](cicd/POS_HARDWARE.md) · [POS_OFFLINE_ARCHITECTURE.md](POS_OFFLINE_ARCHITECTURE.md) |
| How the system fits together | [architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) · [../apps/desktop-cms/ARCHITECTURE.md](../apps/desktop-cms/ARCHITECTURE.md) |
| Secrets and security | [security/SECRETS_MANAGEMENT.md](security/SECRETS_MANAGEMENT.md) · [security/SECURITY_HARDENING.md](security/SECURITY_HARDENING.md) |
| Tests (backend, browser) | [TESTING.md](TESTING.md) · [../e2e/README.md](../e2e/README.md) |
| What was changed, round by round | [WORK_SUMMARY_2026-11-11.md](WORK_SUMMARY_2026-11-11.md) |

## Other folders

| Folder | Content |
|---|---|
| [handoff/](handoff/) | Notes and prompts for the AI assistants working on the PC (Antigravity, Claude) |
| [specs/](specs/) | The owner's original requests and specifications, kept as written: file names they ask for are those of the time (e.g. `BACKUP_RESTORE.md`, `TEST_REPORT.md`, since moved to `archive/`). For the current version of any document, use the table above |
| [archive/](archive/) | Older documents replaced by the guides above — kept for history, may be out of date |
| [brand-images/](brand-images/) | Source brand pictures (logo banner, product scenes) |
| [operations/](operations/), [deployment/](deployment/), [security/](security/) | Runbooks referenced from the root README |

## Earlier reference documents

These top-level files come from earlier audit rounds. Some automated tests check that they exist. When one of
them disagrees with a guide in the first table, the guide in the first table is right:
`API_COMPATIBILITY_POLICY.md`, `API_CONTRACT.md`, `API_INVENTORY.md`, `ARCHITECTURE.md`, `BACKUP_AND_RECOVERY.md`,
`DATABASE_MAINTENANCE.md`, `DEPLOYMENT.md`, `MONITORING_AND_LOGGING.md`, `OPERATIONS_RUNBOOK.md`,
`PRODUCTION_ACCEPTANCE_REPORT.md`, `PRODUCTION_AUDIT.md`, `PRODUCTION_CHECKLIST.md`, `SECURITY.md`,
`SECURITY_HARDENING.md`, `STOREFRONT_DEPLOYMENT.md`, `VPS_OPTIMIZATION.md`, `VPS_SETUP.md`, `openapi.json`.
