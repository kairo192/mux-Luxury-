# CI/CD architecture

```
developer                                                                   VPS
   │                                                                         │
   │  git push feat/*                                                        │
   ▼                                                                         │
┌──────────────┐    pull request      ┌──────────────┐                       │
│ GitHub repo  │ ───────────────────▶ │  CI (ci.yml) │                       │
│ main branch  │                      │ every PR +   │                       │
│ protected    │ ◀──── review ──────  │ push to feat │                       │
└──────┬───────┘   approval + green   └──────┬───────┘                       │
       │           CI required               │ required:                     │
       │           for merge                 │   lockfiles                   │
       │                                     │   lint                        │
       │                                     │   migrations-validate         │
       │                                     │   backend-tests-sqlite        │
       │                                     │   backend-tests-postgres      │
       │                                     │   build-storefront            │
       │                                     │   build-cms                   │
       │                                     │   build-backend-image         │
       │                                     │   dependency-audit            │
       │                                     │   ci-complete (gate)          │
       │                                                                     │
       ▼                                                                     │
  merge to main                                                              │
       │                                                                     │
       │ cd-staging.yml                                                      │
       │   waits for CI green on this SHA                                    │
       │   builds release tarball (GitHub runner, not VPS)                   │
       │   ssh deploys to staging VPS ───────────────────────────────────────┤
       │                                                                     │
       │                                                        ┌────────────┴───────┐
       │                                                        │ staging VPS        │
       │                                                        │ /opt/luxe/releases │
       │                                                        │ release-deploy.sh  │
       │                                                        │   preflight        │
       │                                                        │   encrypted backup │
       │                                                        │   migrate (locked) │
       │                                                        │   symlink swap     │
       │                                                        │   health check     │
       │                                                        │   auto-rollback    │
       │                                                        └────────────┬───────┘
       │                                                                     │
       │   manual sign-off from staging (docs/cicd/RELEASES.md)              │
       ▼                                                                     │
  git tag v<semver> && git push --tags                                       │
       │                                                                     │
       │ cd-production.yml                                                   │
       │   environment:production ─ requires reviewer approval in GitHub UI  │
       │   waits for CI green                                                │
       │   downloads release tarball                                         │
       │   ssh deploys to production VPS ────────────────────────────────────┤
       │   creates GitHub release                                            │
       │                                                        ┌────────────┴───────┐
       │                                                        │ production VPS     │
       │                                                        │ same release-deploy│
       │                                                        └────────────────────┘
       │
       │ build-desktop-cms.yml on the same v* tag:
       │   builds signed .msi / .exe on a Windows runner
       │   archives them on the GitHub release (repository is private)
       │   copies installer + .sig + latest.json to the VPS over SSH
       │
       ▼
   Logged-in CMS apps ask the API for latest.json (HTTPS + staff login;
   refused without one), verify the tauri-updater signature, and offer
   the update.
```

## Design choices

**Builds happen on GitHub-hosted runners, never on the VPS.** The VPS has
2 GB of RAM and one vCPU — a Vite + TypeScript build would evict the
Postgres cache for an hour. The release tarball shipped to the VPS contains
pre-built frontend assets and a Dockerfile that only installs Python runtime
deps.

**Symlink releases, not blue/green.** With one VPS and 2 GB of RAM we can't
keep two full stacks hot. The symlink swap takes ~5–10 seconds and docker
compose up handles the container restart; browsers automatically retry the
next request. For instant rollback we keep the previous five releases on
disk, and `rollback.sh` flips the symlink back.

**Forward-only migrations.** Every schema change is an additive, nullable
column or new table. There is no "down" script. The expand/contract pattern
(§`MIGRATIONS.md`) is the safe way to remove a column. If a migration goes
wrong, we restore from the backup that `release-deploy.sh` took right before
it ran.

**Secrets split in two.** Build/deploy secrets live in GitHub Actions
Secrets; runtime secrets (DB password, WhatsApp token) live at
`/opt/luxe/shared/.env` on the VPS. The deploy user never reads runtime
secrets, the runtime never reads deploy secrets. See `SECRETS.md`.

**Monitoring runs in a separate compose file** (`infrastructure/monitoring/
docker-compose.monitoring.yml`) so a broken app release cannot take down
the only thing that would tell us the app release is broken.

## Files involved

| Role                         | Path                                                   |
| ---------------------------- | ------------------------------------------------------ |
| CI                           | `.github/workflows/ci.yml`                             |
| CD → staging                 | `.github/workflows/cd-staging.yml`                     |
| CD → production              | `.github/workflows/cd-production.yml`                  |
| Desktop CMS signed build     | `.github/workflows/build-desktop-cms.yml`              |
| Migration runner             | `backend/app/migration_runner.py`                      |
| Migrations                   | `backend/migrations/versions/`                         |
| VPS bootstrap                | `infrastructure/scripts/vps-bootstrap.sh`              |
| Release deploy               | `infrastructure/scripts/release-deploy.sh`             |
| Rollback                     | `infrastructure/scripts/rollback.sh`                   |
| Health probe                 | `infrastructure/scripts/health-check.sh`               |
| VPS metrics sampler          | `infrastructure/scripts/vps-metrics.sh`                |
| Encrypted backup             | `infrastructure/backups/backup_postgres_and_media.sh`  |
| Backup restore               | `infrastructure/backups/restore_backup.sh`             |
| Monitoring                   | `infrastructure/monitoring/docker-compose.monitoring.yml` |
| Environment templates        | `infrastructure/environments/*.env.example`            |
| Dependabot                   | `.github/dependabot.yml`                               |
| Secret scan config           | `.gitleaks.toml`                                       |
| Python lint config           | `ruff.toml`                                            |
