# Branching strategy

Trunk-based with short-lived feature branches. Only `main` is deployable.

## Branches

| Prefix              | Purpose                                     | Lifetime     |
| ------------------- | ------------------------------------------- | ------------ |
| `main`              | Always-deployable; protected                | forever      |
| `feat/<slug>`       | New feature or user-visible change          | days–weeks   |
| `fix/<slug>`        | Bug fix (ideally also a regression test)    | hours–days   |
| `chore/<slug>`      | Dependencies, docs, tooling                 | hours        |
| `hotfix/<slug>`     | Urgent production fix branched from a tag   | hours        |

## main protection rules

Configure in **Settings → Branches → Branch protection rules**:

- **Require a pull request before merging** — 1 approving review, dismiss stale reviews on push.
- **Require status checks to pass before merging** — tick `CI complete (branch-protection gate)` (and any others you want to enforce).
- **Require branches to be up to date before merging** — avoids stale CI results.
- **Require conversation resolution before merging**.
- **Require signed commits** — recommended, not strictly required.
- **Do not allow bypassing the above settings** — includes admins.
- **Restrict pushes that create matching branches** — only via PR, no direct push to `main`.
- **Allow force pushes: everyone → off**.
- **Allow deletions: off**.

## Merging

Default to **squash-merge**. Each PR becomes one commit on `main` with the PR
title as its subject. This keeps the git log readable and the release notes
automatic (`gh release create --generate-notes`).

Exception: when landing a multi-step refactor whose intermediate commits are
meaningful on their own, use a **merge commit**. Rebase-merge is disabled to
avoid accidental history rewrites.

## Release tags

Semantic version tags on `main` only:

```
v1.4.0           # minor feature release
v1.4.1           # patch
v2.0.0-rc.1      # pre-release — deploys to staging only by convention
```

A `v*` tag triggers `cd-production.yml` and `build-desktop-cms.yml`
concurrently, so the server + the Desktop CMS always version in lockstep.

## Hotfixes

```
git fetch origin
git checkout -b hotfix/order-null-pointer v1.4.1
# ...fix + test...
git commit -am "fix(orders): guard null ship_address"
git push -u origin hotfix/order-null-pointer
# Open PR to main, get review, merge, tag v1.4.2, push tag.
```

A hotfix follows the full CI pipeline. The only shortcut is that the staging
deploy may be skipped if the owner invokes `cd-production.yml` manually with
`inputs.skip_health_gate=false` after staging on a pre-release tag.
