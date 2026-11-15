import { test, expect } from "@playwright/test";
import { api, createProduct, ensureCategory, watch, cmsLogin, cmsOpen, uid } from "../support/helpers";

// The parts split out of the big CMS screens (App.tsx, CategoryBuilderPage.tsx,
// PosPage.tsx) each open, show their content and close again, with no error.
let cat: Awaited<ReturnType<typeof ensureCategory>>;

test.beforeAll(async () => {
  cat = await ensureCategory();
  await createProduct({ name: "Pochette Découpe", price: 5000, stock: 3, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
});

test("category builder: create form, edit, add attribute and delete dialogs", async ({ page }) => {
  const w = watch(page);
  await cmsLogin(page);
  await cmsOpen(page, "Catégories");
  const main = page.locator("main");

  await main.getByRole("button", { name: /Créer une Catégorie/ }).click();
  await expect(main.getByRole("button", { name: /Fermer le configurateur/ })).toBeVisible();
  await main.getByRole("button", { name: /Fermer le configurateur/ }).click();

  const card = main.locator("div").filter({ hasText: "Sacs E2E" }).filter({ has: page.getByRole("button", { name: "Modifier" }) }).last();
  await card.getByRole("button", { name: "Modifier" }).click();
  await expect(page.getByText("Modifier la Catégorie : Sacs E2E")).toBeVisible();
  await page.locator("div.fixed.inset-0").last().getByRole("button", { name: "Fermer" }).click();
  await expect(page.getByText("Modifier la Catégorie : Sacs E2E")).toHaveCount(0);

  await card.getByRole("button", { name: /^Ajouter$/ }).first().click();
  await expect(page.getByText("Ajouter un attribut à « Sacs E2E »")).toBeVisible();
  await page.locator("div.fixed.inset-0").last().getByRole("button", { name: "Fermer" }).click();

  await card.getByRole("button", { name: /^Supprimer$/ }).click();
  await expect(page.getByText("Supprimer ou Archiver la Catégorie")).toBeVisible();
  await page.locator("div.fixed.inset-0").last().getByRole("button", { name: "Annuler" }).click();
  await expect(page.getByText("Supprimer ou Archiver la Catégorie")).toHaveCount(0);
  w.expectClean();
});

test("products: the delete / archive dialog opens and cancels", async ({ page }) => {
  const w = watch(page);
  await cmsLogin(page);
  await cmsOpen(page, "Produits");
  const row = page.locator("main tr, main div").filter({ hasText: "Pochette Découpe" })
    .filter({ has: page.getByRole("button", { name: "Supprimer" }) }).last();
  const opener = row.getByRole("button", { name: "Supprimer" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Suppression / Archivage du Produit" });
  await expect(dialog).toBeVisible();
  // Keyboard focus starts on the safe choice and never leaves the dialog.
  await expect(dialog.getByRole("button", { name: "Annuler" })).toBeFocused();
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
  }
  await dialog.getByRole("button", { name: "Annuler" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();           // back on the button that opened it
  w.expectClean();
});

test("products: after a deletion, keyboard focus lands on the product search", async ({ page }) => {
  const w = watch(page);
  const name = `Pochette Jetable ${uid()}`;
  await createProduct({ name, price: 3000, stock: 1, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
  await cmsLogin(page);
  await cmsOpen(page, "Produits");
  const rows = () => page.locator("main tr:visible").filter({ hasText: name }); // other screens stay mounted, hidden
  await rows().getByRole("button", { name: "Supprimer" }).click();
  const dialog = page.getByRole("dialog", { name: "Suppression / Archivage du Produit" });
  await dialog.getByRole("button", { name: /Supprimer Définitivement/ }).click();
  await expect(dialog).toHaveCount(0);
  await expect(rows()).toHaveCount(0);          // its row (and « Supprimer » button) is gone
  await expect(page.locator("[data-products-search]")).toBeFocused();
  w.expectClean();
});

test("till: register history, customer and close-register sheets", async ({ page }) => {
  const w = watch(page);
  const cur = await api("/admin/pos/register/current");
  if (!cur.session) await api("/admin/pos/register/open", { body: { register_name: "Découpe", opening_float_dzd: 0 } });
  await cmsLogin(page);
  await cmsOpen(page, "Point de vente");
  const main = page.locator("main");

  // Hold the history list until the sheet is closed, then let it arrive: a late
  // answer must not reopen the sheet.
  let release!: () => void;
  const held = new Promise<void>((r) => { release = r; });
  await page.route("**/admin/pos/register/sessions*", async (route) => { await held; await route.continue(); });
  // "requestfinished": the whole body has arrived (not just the headers).
  const listDone = page.waitForEvent("requestfinished", (r) => r.url().includes("/admin/pos/register/sessions"));
  await main.getByRole("button", { name: /Historique/ }).first().click();
  await expect(page.getByText("Historique des caisses")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Historique des caisses")).toHaveCount(0);
  release();
  await listDone;
  // Let the page's own handler run and React render: two animation frames.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(null)))));
  await expect(page.getByText("Historique des caisses")).toHaveCount(0);
  await page.unroute("**/admin/pos/register/sessions*");

  await main.getByRole("button", { name: /Rattacher un client/ }).click();
  await expect(page.getByRole("heading", { name: "Rattacher un client" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Rattacher un client" })).toHaveCount(0);

  await main.getByRole("button", { name: /Clôturer/ }).first().click();
  await expect(page.getByText("Espèces comptées")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Espèces comptées")).toHaveCount(0);
  w.expectClean();
});

test("a request retried after logout and a change of server never takes the old session to the new server", async ({ page }) => {
  await cmsLogin(page);
  const other = "http://other-server.e2e.invalid";
  const seenOnOther: string[] = [];
  await page.route(`${other}/**`, (route) => {
    seenOnOther.push(route.request().headers()["authorization"] || "");
    return route.fulfill({ status: 503, body: "" });
  });
  // The first categories request is held, then answered 503 so the client retries it.
  let release!: () => void;
  const held = new Promise<void>((r) => { release = r; });
  const calls: { url: string; auth: string }[] = [];
  await page.route("**/admin/categories?*", async (route) => {
    const req = route.request();
    calls.push({ url: req.url(), auth: req.headers()["authorization"] || "" });
    if (calls.length === 1) { await held; return route.fulfill({ status: 503, body: "" }); }
    return route.continue();
  });

  await page.locator("header").getByRole("button", { name: /Actualiser/ }).click();
  await expect.poll(() => calls.length).toBeGreaterThanOrEqual(1);
  const oldAuth = calls[0].auth;
  expect(oldAuth).toMatch(/^Bearer \S+/);

  // While it is held: sign out and point the CMS at another server.
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await expect(page.locator("#login-email")).toBeVisible();
  await page.getByRole("button", { name: /Modifier/ }).click();
  await page.locator("#cms-api-server-url").fill(`${other}/api/v1`);
  release();

  // The retry goes back to the server the request started on…
  await expect.poll(() => calls.length).toBeGreaterThanOrEqual(2);
  expect(new URL(calls[1].url).origin).toBe(new URL(calls[0].url).origin);
  await page.waitForTimeout(1500);              // room for any further retry
  // …and the new server never receives the old session's token.
  expect(seenOnOther.filter((a) => a === oldAuth)).toEqual([]);
  // A late refusal for the old session leaves the login screen as it is.
  await expect(page.locator("#login-email")).toBeVisible();
  await page.unroute("**/admin/categories?*");
});
