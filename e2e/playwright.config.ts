import { defineConfig, devices } from "@playwright/test";

// One isolated stack per run, on its own ports (never the dev servers):
// a fresh production-mode API, the CMS and the shop dev servers.
const API = process.env.E2E_API_URL ||= "http://127.0.0.1:18000";
const CMS = process.env.E2E_CMS_URL ||= "http://localhost:11420";
const SHOP = process.env.E2E_SHOP_URL ||= "http://localhost:15173";
const port = (u: string) => new URL(u).port;

export default defineConfig({
  testDir: "./tests",
  // The specs build on each other (first-time setup -> catalogue -> orders),
  // like a real shop's first days: one worker, files in order.
  fullyParallel: false,
  workers: 1,
  // No retries: the specs share one database, a retry would run against the
  // state left by the failed attempt and hide the real problem.
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    timezoneId: "Africa/Algiers",
    locale: "fr-FR",
    trace: "off",
    screenshot: "only-on-failure",
    acceptDownloads: true,
  },
  webServer: [
    {
      command: "node support/start-api.mjs",
      url: `${API}/api/v1/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: "pipe",
    },
    {
      command: `npx vite --port ${port(CMS)} --strictPort`,
      cwd: "../apps/desktop-cms",
      url: CMS,
      env: { VITE_CMS_API_URL: `${API}/api/v1` },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${port(SHOP)} --strictPort`,
      cwd: "../apps/storefront",
      url: SHOP,
      env: { LUXE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
