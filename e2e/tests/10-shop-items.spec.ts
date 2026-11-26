import { test, expect, type Page } from "@playwright/test";
import { api, publicApi, ensureCategory, watch, cmsLogin, cmsOpen, uid } from "../support/helpers";

// Shop items: the owner adds a boutique article with its colours, quantities and
// barcodes in one form, prints a label per piece, records an arrival, finds it
// by scanning — and the article is the same product the till sells and the
// Products screen edits; "shop only" keeps it off the website.

/** A valid EAN-13 (manufacturer-style code, not in the shop's 20… range). */
function ean13(): string {
  const body = "590" + String(Math.floor(Math.random() * 1e9)).padStart(9, "0");
  const sum = body.split("").reduce((s, d, i) => s + Number(d) * (i % 2 ? 3 : 1), 0);
  return body + ((10 - (sum % 10)) % 10);
}

const printedLabels = (page: Page) => page.frameLocator("iframe[data-luxe-print]").locator(".page");
const item = (page: Page, name: string) => page.locator(`[data-testid="shop-item"][data-item-name="${name}"]`);
const variant = (page: Page, name: string, title: string) => item(page, name).locator(`[data-testid="shop-variant"][data-variant-title="${title}"]`);

test("shop items: quick add with colours and barcodes, labels, arrival, scan, website", async ({ page }) => {
  test.setTimeout(120_000);
  const cat = await ensureCategory();
  const name = `Pochette Boutique ${uid()}`;
  const scanned = ean13();
  const w = watch(page);
  await cmsLogin(page, undefined, "en");
  await cmsOpen(page, "Shop items");
  const main = page.locator("main");

  // ---- quick add: 3 colours (one new), quantities, one barcode scanned
  await main.getByRole("button", { name: "New item" }).click();
  const form = page.getByRole("dialog", { name: "New shop item" });
  await form.getByPlaceholder("e.g. Leather tote bag").fill(name);
  await form.locator("select").first().selectOption(String(cat.id));
  await form.getByPlaceholder("9000").fill("7000");
  await form.getByRole("button", { name: "Noir", exact: true }).click();
  await form.getByRole("button", { name: "Rouge", exact: true }).click();
  await form.getByRole("textbox", { name: /New value/ }).fill("Bleu");
  await form.getByRole("textbox", { name: /New value/ }).press("Enter");
  await expect(form.getByTestId("quick-row")).toHaveCount(3);
  await form.getByRole("textbox", { name: "Quantity — Noir" }).fill("2");
  await form.getByRole("textbox", { name: "Quantity — Rouge" }).fill("1");
  await form.getByRole("textbox", { name: "Quantity — Bleu" }).fill("3");
  await form.getByRole("textbox", { name: "Barcode — Rouge" }).fill(scanned);
  await expect(form.getByTestId("quick-summary")).toHaveText("3 colour(s) / size(s), 6 piece(s)");
  await form.getByRole("button", { name: "Save and print 6 label(s)" }).click();

  // saved, and one label per piece went to the print window
  await expect(page.getByTestId("shop-success")).toContainText(`“${name}” added (3 colour(s) / size(s)).`);
  await expect(printedLabels(page)).toHaveCount(6);
  await expect(item(page, name)).toContainText("Shop only");
  await expect(variant(page, name, "Rouge").getByTestId("variant-barcode")).toHaveText(scanned);
  const codes: Record<string, string> = {};
  for (const t of ["Noir", "Bleu"]) {
    codes[t] = (await variant(page, name, t).getByTestId("variant-barcode").innerText()).trim();
    expect(codes[t]).toMatch(/^20\d{11}$/);
  }

  // ---- same product everywhere: the till finds it by scanning, the website does not show it
  const found = await api<any>(`/admin/pos/lookup?code=${codes.Bleu}`);
  expect([found.match_type, found.variant.variant_title, found.variant.stock_qty]).toEqual(["variant", "Bleu", 3]);
  expect((await publicApi<any>(`/products?q=${encodeURIComponent(name)}`)).body.items).toHaveLength(0);
  const inProducts = (await api<any>("/admin/products")).items.find((p: any) => p.name_fr === name);
  expect([inProducts.status, inProducts.sales_channel]).toEqual(["published", "store"]);

  // ---- arrival of 3 black pieces (no labels this time)
  await variant(page, name, "Noir").getByRole("textbox", { name: "Pieces arrived — Noir" }).fill("3");
  await variant(page, name, "Noir").getByRole("button", { name: "Add to stock — Noir" }).click();
  const ask = page.locator('[aria-labelledby="active-confirm-title"]');
  await expect(ask).toContainText("3 piece(s) added");
  await ask.getByRole("button", { name: "No labels" }).click();
  await expect(variant(page, name, "Noir").getByTestId("variant-stock")).toHaveText("5");

  // ---- labels for the whole article: one per piece in stock (5 + 1 + 3)
  await item(page, name).getByRole("button", { name: "Labels", exact: true }).click();
  const labels = page.getByRole("dialog", { name: `Labels — ${name}` });
  await labels.getByRole("button", { name: "Print 9 label(s)" }).click();
  await expect(printedLabels(page)).toHaveCount(9);

  // ---- scanning finds the article; an unknown code offers to create it
  const search = main.getByRole("textbox", { name: "Search" });
  await search.fill(scanned);
  await search.press("Enter");
  await expect(page.getByTestId("shop-item")).toHaveCount(1);
  await expect(item(page, name)).toBeVisible();
  const unknown = ean13();
  await search.fill(unknown);
  await search.press("Enter");
  await expect(main).toContainText(`No item with code “${unknown}”.`);
  await main.getByRole("button", { name: "Create the item with this code" }).click();
  await expect(page.getByRole("textbox", { name: "Barcode — Single item" })).toHaveValue(unknown);
  await page.keyboard.press("Escape");

  // ---- a barcode already used by another article is refused
  await main.getByRole("button", { name: "New item" }).click();
  await form.getByPlaceholder("e.g. Leather tote bag").fill(`${name} bis`);
  await form.locator("select").first().selectOption(String(cat.id));
  await form.getByPlaceholder("9000").fill("100");
  await form.getByRole("textbox", { name: "Barcode — Single item" }).fill(scanned);
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect(form.getByRole("alert")).toContainText("Barcode already used");
  await page.keyboard.press("Escape");

  // ---- now sell it on the website too
  await search.fill(scanned);
  await search.press("Enter");
  await item(page, name).getByRole("button", { name: "Edit" }).click();
  const edit = page.getByRole("dialog", { name: "Edit item" });
  await edit.getByRole("checkbox").check();
  await edit.getByRole("button", { name: "Save" }).click();
  // the website shows a photo for every article
  await expect(edit.getByRole("alert")).toContainText("To sell on the website, add a photo");
  await page.keyboard.press("Escape");
  const p = (await api<any>("/admin/products")).items.find((x: any) => x.name_fr === name);
  await api(`/admin/products/${p.id}`, { method: "PUT", body: {
    expected_version: p.version, name_fr: name, selling_price_dzd: 7000, main_image_url: "/assets/mus_luxury_logo.png" } });
  await search.press("Enter");
  await item(page, name).getByRole("button", { name: "Edit" }).click();
  await edit.getByRole("checkbox").check();
  await edit.getByRole("button", { name: "Save" }).click();
  await expect(item(page, name)).toContainText("Website + shop");
  expect((await publicApi<any>(`/products?q=${encodeURIComponent(name)}`)).body.items.map((p: any) => p.name_fr)).toContain(name);

  w.expectClean([/409 POST \/admin\/store\/items$/, /422 PUT \/admin\/store\/items\/\d+$/]);
});
