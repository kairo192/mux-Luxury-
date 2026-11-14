import { test, expect } from "@playwright/test";
import { api, createProduct, ensureCategory, watch, cmsLogin, cmsOpen } from "../support/helpers";

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
