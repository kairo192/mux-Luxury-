# Resume prompt — paste this into Antigravity

Copy-paste everything inside the fenced block below as your first message to
Antigravity (running in the local codebase at
`C:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce`). It tells Antigravity
what the cloud Claude session just did and where to pick up.

```text
You are resuming Mus Luxury (LUXE) development. I'm running you on my local
Windows machine while a cloud Claude session has been pushing to
`feat/pos-core-cash-register-18lsk6` on GitHub. Before you do anything:

1. `git fetch origin && git log --oneline origin/feat/pos-core-cash-register-18lsk6 -10`
   to see what the cloud session just pushed. The three most recent commits
   on that branch are:
     - f59ac77  feat(cms): i18n foundation (FR + EN + AR with RTL) + shell translated
     - 0e44047  feat(cleanup): strip WhatsApp recovery + backup UI; blank-slate seed; production .env
     - 11eaccc  fix(storefront+cms): CSP-safe Tailwind, hardened fetch, touch-friendly prompts

2. Read `docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md` at the repo root (the cloud session
   maintains it between sessions). It lists exactly what landed, what is
   dirty vs committed, which blockers are mine, and the four priorities
   stacked in order.

3. Read `docs/cicd/I18N_AUDIT.md`. This is the new audit + recipe for the
   bilingual translation work the owner requested in docs/specs/lang.md. §3 is the
   step-by-step recipe. §7 is the priority queue of pages to translate.
   Follow that recipe verbatim — do not re-architect the i18n system; the
   cloud session already built it.

4. Pick up at priority #1 from the handoff: finish the CMS i18n
   translation pass. The next three pages, in order, are:
     a. BusinessDashboardPage
     b. PurchasesPage + SuppliersPage
     c. ProductEditor + VariantManager
   For each page:
     - Add FR / EN / AR keys to apps/desktop-cms/src/i18n/translations.ts
       in the SAME ORDER across all three dictionaries.
     - Replace hardcoded French strings with t("key") calls.
     - Apply the RTL polish from I18N_AUDIT.md §3 point 5.
     - Run `npx tsc --noEmit` and `npm run build` in apps/desktop-cms/.
     - Commit one page per commit with the trailer from
       docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md §6.

5. Ground rules the cloud session agreed on:
   - You own branch `feat/pos-core-cash-register` (local).
   - The cloud session owns `feat/pos-core-cash-register-18lsk6` (remote).
   - DO NOT merge the two automatically. The user merges both into the PR.
   - DO NOT re-add the WhatsApp recovery flow or the admin-facing backup UI.
     They were removed intentionally — the owner said so.
   - DO NOT regenerate the production .env. The owner already has the
     values; re-run backend/scripts/generate_production_env.py --force
     only if explicitly asked.
   - Three blockers (BLOCKER-01/02/03 in the earlier docs/handoff/HANDOFF_FOR_CLAUDE.md)
     still need the owner's confirmation — do not guess them.

6. If you hit your own usage limit, write a fresh handoff for the next
   Claude session at docs/handoff/HANDOFF_FOR_CLAUDE.md at the repo root. Document
   what you committed, what is dirty, what tests pass, and which page you
   are mid-translation on so the next session resumes cleanly.

Confirm you've read the handoff + audit before touching any file. Then
start on BusinessDashboardPage.
```

## What the cloud session (Claude) just did

Branch: `feat/pos-core-cash-register-18lsk6`
Latest commit on remote: `f59ac77`

| Commit | Scope | Why |
| --- | --- | --- |
| `f59ac77` | CMS i18n foundation + shell translated | Deliver the bilingual EN / AR + RTL infrastructure the `lang.md` audit asked for. 3-way language toggle in the header, zero new deps, Tailwind `rtl:` variant wired. Shell (topbar, sidebar) + PosPage translated as the pattern reference. Audit doc enumerates the remaining pages + per-page string counts and gives Antigravity a step-by-step recipe. |
| `0e44047` | Strip WhatsApp recovery + backup UI; blank-slate seed; production .env | Owner request: no more WhatsApp admin password recovery, no admin-facing backup UI. Production first-boot now gives an empty catalogue (`LUXE_SEED_DEMO_PRODUCTS=1` or `APP_ENV != "production"` to re-enable demo). Production `.env` generator writes a full ready-to-use file to `scratch/production.env` with cryptographically strong values. |
| `11eaccc` | CSP-safe compiled Tailwind, hardened storefront fetch, touch-friendly prompts | Production bug: storefront loaded `cdn.tailwindcss.com` but Nginx CSP blocks it. Storefront `fetch()` calls lacked retry/timeout/sanitisation; `window.prompt` in VariantManager + PurchasesPage was unusable on a till. All three fixed. |

## Files produced or changed in the very last round (`f59ac77`)

- `apps/desktop-cms/src/i18n/translations.ts` — new, FR/EN/AR dictionaries.
- `apps/desktop-cms/src/i18n/index.tsx` — new, Context + hooks + `<LanguageToggle />`.
- `apps/desktop-cms/tailwind.config.js` — added `rtl:` / `ltr:` plugin + Cairo/Noto Sans Arabic in the font stack.
- `apps/desktop-cms/src/main.tsx` — wrapped the app in `<I18nProvider>`.
- `apps/desktop-cms/src/App.tsx` — imported `useT` + `LanguageToggle`; translated topbar (status chip, Refresh, Logout) + sidebar's 14 nav labels; added `<LanguageToggle />` next to the online chip.
- `apps/desktop-cms/src/pages/PosPage.tsx` — translated loading state, Matériel / Historique / Clôturer buttons, scan-input label, Encaisser CTA.
- `docs/cicd/I18N_AUDIT.md` — new, per-page string counts + recipe + priority queue + RTL-sensitive spots.
- `docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md` — updated §4 to put the i18n translation pass at priority #1.

## Related artefacts already in the repo

- `backend/scripts/generate_production_env.py` — run with
  `--domain mus-luxury.com --admin-email … --admin-whatsapp +213…` to
  produce `scratch/production.env` (git-ignored by the `*.env` catch-all).
- `scratch/README.md` — explains the gitignore policy for the scratch dir.
- `docs/handoff/HANDOFF_FOR_ANTIGRAVITY.md` — the complete living handoff.
