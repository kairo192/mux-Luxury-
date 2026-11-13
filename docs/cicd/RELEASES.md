# Releases

Semantic versioning. Every production deploy maps 1:1 to a git tag and a
GitHub release.

## Numbering

- **Major** — breaking API or breaking POS protocol change. Rare.
- **Minor** — new feature, new endpoint, new UI surface. Common.
- **Patch** — bug fix, security fix, dependency bump. Common.
- **Pre-release** — `v1.4.0-rc.1`; goes to staging only (by convention; the
  production workflow accepts them but the approver should decline).

## Cutting a release

```bash
# From main, after the PR has merged and CI is green:
git checkout main && git pull
git tag -a v1.4.0 -m "v1.4.0 — supplier bill endpoints, POS refund flow"
git push origin v1.4.0
```

Pushing the tag:

1. Fires `cd-production.yml`. GitHub pauses at the `environment: production`
   approval gate — approve it from the Actions UI from a device with
   `environment: production` reviewer rights.
2. Fires `build-desktop-cms.yml`. Builds the signed Windows installer,
   archives it on the matching GitHub release, and copies `latest.json` + the
   signed installer to the VPS, where the API serves them to logged-in CMS
   apps only.
3. After production deploy succeeds, `cd-production.yml` creates the GitHub
   release with auto-generated notes (`generate_release_notes: true`).

Within ~10 minutes of the tag push, the server is on the new version and
every POS installation sees the new installer on its next launch.

## Release notes

`generate_release_notes: true` pulls from the squash-commit messages since
the previous tag. Keep commit subjects tight — they become the public
changelog. Prefix convention:

- `feat(scope): …`     — a new user-visible capability
- `fix(scope): …`       — a bug fix
- `perf(scope): …`      — a measurable performance improvement
- `refactor(scope): …`  — code change with no behavior change
- `chore(scope): …`     — dependencies, infra, non-functional
- `docs(scope): …`      — documentation only
- `test(scope): …`      — tests only

## Hotfix release

```bash
git checkout -b hotfix/v1.4.1 v1.4.0
# fix
git commit -am "fix(orders): guard null ship_address"
git push -u origin hotfix/v1.4.1
# Open PR to main, CI green, merge.
git checkout main && git pull
git tag -a v1.4.1 -m "v1.4.1 — fix null ship_address"
git push origin v1.4.1
```

Hotfixes skip nothing — they still require CI green and the production
environment approval. The only speed-up is not going through staging.

## What's "the current release"?

- GitHub: the latest `v*` tag, pinned to the GitHub Releases page.
- VPS: `readlink /opt/luxe/current` (it points at
  `/opt/luxe/releases/<version>`), or `cat /opt/luxe/current/.release-version`.
- API clients: `GET /api/v1/health` returns `timestamp` only — version is
  deliberately not exposed to anonymous callers. For an authenticated
  read use `GET /api/v1/admin/system/info` once it's implemented.
