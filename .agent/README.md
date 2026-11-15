# `.agent/` — AI assistants' skills (not part of the shop)

Reference material the AI coding assistants use when working on this repository
(Antigravity / Gemini on the owner's PC reads `skills/*/SKILL.md`):

| Skill | Used for |
|---|---|
| `skills/apple-design/` | Interface guidelines (touch targets, legibility, modals) followed by the CMS and the till |
| `skills/ui-ux-pro-max/` | Design system data and scripts (palettes, typography, layouts) |
| `skills/backend-architect/` | Backend architecture notes and checks |
| `skills/security-audit/` | Security review checklists (client side, cloud, data isolation, desktop) |

Nothing here is built, shipped or run by the shop: it is excluded from the Docker images, from the
linter (`ruff.toml`) and from CodeRabbit reviews (`.coderabbit.yaml`). Keep it in git so every
machine's assistant has the same skills; deleting it here would delete it from those machines on
their next `git pull`.
