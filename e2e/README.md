# End-to-end tests — shop + back office (CMS)

Real browser tests (Playwright, Chromium) of the online shop and the desktop
CMS **together**, against a **fresh production-mode API** started for the run.
Nothing touches your own database or dev servers: the suite starts its own
stack on separate ports.

| Port | What |
|---|---|
| 18000 | API (`APP_ENV=production`, random secrets, empty database) |
| 11420 | CMS (Vite) pointed at that API |
| 15173 | Shop (Vite) pointed at that API |

## Run

```bash
npm install --prefix e2e          # once
npx playwright install chromium   # once, if no Chromium is installed
npm run test:e2e                  # from the repo root (SQLite, temporary folder)
```

On PostgreSQL (as in CI), give an **empty** database:

```bash
E2E_DATABASE_URL=postgresql://user:pass@localhost:5432/luxe_e2e npm run test:e2e
```

Useful: `npm --prefix e2e run test:shop`, `npm --prefix e2e run test:cms`,
`npx playwright test tests/03-shop.spec.ts --headed` (from `e2e/`).

## What is covered

| File | Scenario |
|---|---|
| `01-first-installation` | Setup wizard creates the owner; second setup refused; production shop starts empty; wrong password; owner creates a cashier |
| `02-catalogue` | Product created in the CMS editor (info, price, variant, stock, photo) is on sale in the shop; archived product disappears at once |
| `03-shop` | Home, Arabic/English, product page, cart, phone validation, promo code checkout (server order = what the customer saw), stock reserved, order tracking, sold-out item |
| `04-cms-operations` | Online order through every status (cash collected on delivery, cancel puts stock back); till sale with change, refund, register close with a shortage; damaged-stock loss; unpaid expense then payment |
| `05-cms-finance` | Supplier purchase (stock, landed cost, debt, bank payment); every report exports a French CSV; Comptabilité = Analytique, each tab exports its CSV; a cashier cannot read the money |
| `07-backups` | Owner backs up, copies the encrypted file to the PC, sends it back (listed for restore, audited); a cashier is refused |
| `06-cms-all-screens` | Every CMS screen in FR / EN / AR for the owner and a cashier: no crash, no console error, no refused call, no `NaN` / `undefined` / raw key on screen |

Every test fails on a page crash, a console error or an unexpected failed
API call (`support/helpers.ts → watch()`).

The specs run in order, like a shop's first days (one worker, no retries: a
retry would run on the data left by the failed attempt). The first file creates
the owner and the cashier through the screens; any other spec run on its own
creates the accounts it needs (`ensureAccount`), so
`npx playwright test 03-shop` works alone.

Covered too: `07-backups` (backup, encrypted copy to the PC, send it back).
