# Storefront (`apps/storefront`)

This app is the public boutique served at `https://mus-luxury.com`.

## What ships

A plain HTML page with vanilla JavaScript (FR / AR-RTL / EN, catalog, product
window, cart, COD checkout, order tracking, information pages). It calls the
FastAPI backend through same-origin `/api/v1/*` and is built with Vite:

```bash
npm install
npm run dev      # http://localhost:5173  (proxies /api/v1 and /uploads to :8000)
npm run build    # outputs dist/ (HTML + one hashed JS bundle + compiled CSS + public assets)
```

| File | What it holds |
|---|---|
| `index.html` | The page's markup only (header, home, catalogue, product / cart / tracking windows, footer) and the SEO block the server fills for product and category pages (`<!-- SEO:START -->`) |
| `src/shop/main.js` | Loads the shop code below, in order |
| `src/shop/core.js` | Settings data (pictures, colours, texts in 3 languages, wilayas) and the shared `state` |
| `src/shop/helpers.js` | API calls, amounts, languages, escaping of text put into the page |
| `src/shop/content.js` | Shop content from the CMS (contacts, opening hours, banners, home blocks), page meta tags |
| `src/shop/catalog.js` | Address router (`#/…`, `/produit/…`, `/categorie/…`), catalogue, search and filters |
| `src/shop/product.js` | Product window: pictures, colour / size choices, quantity, delivery estimate |
| `src/shop/cart.js` | Cart and guest checkout (cash on delivery) |
| `src/shop/pages.js` | Order tracking, information pages, delivery prices by wilaya |
| `src/shop/sync.js` | Keeping the page in step with the server, and start-up |
| `src/index.css`, `src/shop.css` | Tailwind (compiled at build time) and the few styles Tailwind classes do not cover |

The HTML calls the code from `onclick="…"` attributes, so each file puts what it
defines on `window` at its end (the files also use each other's functions that
way). A file may use, while it loads, only what earlier files defined; anything
is usable from event handlers and once the page has loaded. Tailwind is compiled
by PostCSS, with no runtime CSS CDN, so the strict Nginx CSP does not need
`unsafe-eval`.

`public/` holds the brand logos, category tiles and product photography; the
Docker image (`Dockerfile`) builds with Vite and serves `dist/` behind Nginx.
The browser tests (`e2e/`) run against the production bundle in CI
(`E2E_SHOP_BUILT=1`).

The Tauri 2 desktop CMS (`apps/desktop-cms`) is a separate app that talks to the
same API and controls this storefront's content (categories, products, banners,
homepage sections, pages, delivery rates).
