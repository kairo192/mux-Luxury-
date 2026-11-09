# Branch protection setup

Settings → Branches → Branch protection rules → `main`:

- **Require a pull request before merging** — 1 approving review.
- **Dismiss stale pull request approvals when new commits are pushed** — on.
- **Require review from Code Owners** — on. CODEOWNERS enforces who reviews
  infrastructure, migrations, workflows.
- **Require status checks to pass before merging** — add:
  - `CI complete (branch-protection gate)` — the catch-all from `ci.yml`.
- **Require branches to be up to date before merging** — on.
- **Require conversation resolution before merging** — on.
- **Do not allow bypassing the above settings** — on (includes admins).
- **Restrict who can push to matching branches** — only the deploy workflow.
- **Allow force pushes: everyone → off; specific people → off.**
- **Allow deletions: off.**

## Environment protections

Settings → Environments:

- **staging** — no required reviewers (auto-deploy on main push).
- **production** — required reviewers: repo owner + (optional) one more
  trusted operator. Wait timer: 0 minutes; the review itself is the gate.
  Deployment branches: tags matching `v*` and the `main` branch.
