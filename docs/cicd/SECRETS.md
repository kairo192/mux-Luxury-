# Secrets

Two stores, strictly separate.

## 1. GitHub Actions Secrets (build + deploy only)

Set under **Settings → Secrets and variables → Actions → Secrets**.

| Name                               | Used by               | What it is                                          |
| ---------------------------------- | --------------------- | --------------------------------------------------- |
| `STAGING_SSH_HOST`                 | cd-staging.yml        | `<ip>` or `staging.mus-luxury.com`                  |
| `STAGING_SSH_USER`                 | cd-staging.yml        | `luxe`                                              |
| `STAGING_SSH_PRIVATE_KEY`          | cd-staging.yml        | Ed25519 PEM, matching VPS authorized_keys           |
| `PRODUCTION_SSH_HOST`              | cd-production.yml     | `<ip>` or `mus-luxury.com`                          |
| `PRODUCTION_SSH_USER`              | cd-production.yml     | `luxe`                                              |
| `PRODUCTION_SSH_PRIVATE_KEY`       | cd-production.yml     | Ed25519 PEM                                         |
| `TAURI_SIGNING_PRIVATE_KEY`        | build-desktop-cms.yml | `tauri signer generate` output                      |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | build-desktop-cms.yml | password used when generating the signing key     |
| `GITHUB_TOKEN`                     | all workflows         | provided by GitHub automatically; do not add        |

## 2. GitHub Actions Variables (non-sensitive)

Under **Variables** in the same screen.

| Name                      | Example value                                  |
| ------------------------- | ---------------------------------------------- |
| `STAGING_URL`             | `https://staging.mus-luxury.com`               |
| `STAGING_HEALTH_URL`      | `https://staging-api.mus-luxury.com/api/v1/health` |
| `PRODUCTION_URL`          | `https://mus-luxury.com`                       |
| `PRODUCTION_HEALTH_URL`   | `https://api.mus-luxury.com/api/v1/health`     |

## 3. VPS runtime secrets

Live at `/opt/luxe/shared/.env`, `chmod 0600`, owner `luxe`. Created by hand
once from `infrastructure/environments/production.env.example`. docker
compose reads it via `env_file`, so a container restart picks up changes.

**Never** check in a filled copy. The `.env.example` files only contain
placeholders.

## 4. Rotation

| Secret                                          | Rotation cadence                     |
| ----------------------------------------------- | ------------------------------------ |
| `SECRET_KEY`, `CMS_HMAC_SIGNING_SECRET`         | Every 6 months, or on compromise     |
| `BACKUP_ENCRYPTION_KEY`                         | On compromise only — rotating orphans old backups |
| `POSTGRES_PASSWORD`                             | Yearly, or on compromise             |
| SSH deploy keys                                 | Yearly, or when staff leaves         |
| `TAURI_SIGNING_PRIVATE_KEY`                     | **Never** without a plan — see below |
| WhatsApp / Chargily / S3 tokens                 | On provider rotation or compromise   |

**Rotating the Tauri signing key** forces every existing POS installation
to reinstall because `tauri-plugin-updater` refuses manifests signed by a
different public key than the one baked into the running binary. Plan a
coordinated reinstall if you ever have to.

## 5. Accidentally committed a secret?

1. Rotate it. Nothing committed to a git history is "unleaked".
2. Remove it from `main` (a new commit is enough — history still has it).
3. Run `gitleaks detect --redact` locally to confirm there are no others.
4. Consider rewriting history with `git filter-repo` only for repositories
   that never left your control.

The `gitleaks` CI job catches most of this before it merges.
