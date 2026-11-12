import { defineConfig } from "vite";

// The shop is a single index.html (no React). In development the API runs on
// :8000; product/category pages and the sitemap go through the API exactly
// like in production (see infrastructure/nginx/nginx.conf), so link previews
// and schema.org tags can be checked locally. Start the API with
// STOREFRONT_INTERNAL_URL=http://localhost:5173 so it can read this page.
// LUXE_API_URL lets the end-to-end tests point the shop at their own server.
const API = process.env.LUXE_API_URL || "http://localhost:8000";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api/v1": { target: API, changeOrigin: true },
      "/uploads": { target: API, changeOrigin: true },
      "^/(produit|categorie)/[a-z0-9-]+/?$": {
        target: API,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/(produit|categorie)\/([a-z0-9-]+)\/?$/, "/api/v1/seo/render/$1/$2"),
      },
      "/sitemap.xml": {
        target: API,
        changeOrigin: false,
        rewrite: () => "/api/v1/seo/sitemap.xml",
      },
    },
  },
});
