# Storefront (`apps/storefront`)

This app is the public boutique served at `https://mus-luxury.com`.

## What ships

`index.html` is the **single live storefront**: a self-contained HTML page with
vanilla JavaScript (FR / AR-RTL / EN, catalog, PDP, cart, COD checkout, order
tracking, static pages). It calls the FastAPI backend through same-origin
`/api/v1/*` endpoints and is developed/served with Vite:

```bash
npm install
npm run dev      # http://localhost:5173  (proxies /api/v1 and /uploads to :8000)
npm run build    # outputs dist/ (HTML + compiled Tailwind CSS + public assets)
```

Tailwind is compiled at build time by PostCSS (`tailwind.config.js` +
`src/index.css`). There is no runtime CSS CDN, so the strict Nginx CSP does not
need `unsafe-eval`.

`public/` holds the brand logos, category tiles and product photography; the
Docker image (`Dockerfile`) builds with Vite and serves `dist/` behind Nginx.

## `src/`

`src/` contains an **earlier React module** (`App.tsx`, `main.tsx`,
`api/client.ts`) that is type-checked by `tsc` and covered by the backend test
suite, but is **not mounted** by `index.html` and is not part of the shipped
bundle. It is kept for reference and for a possible future SPA build — do not
assume it renders anything in production.

The Tauri 2 desktop CMS (`apps/desktop-cms`) is a separate app that talks to the
same API and controls this storefront's content (categories, products, banners,
homepage sections, pages, delivery rates).
