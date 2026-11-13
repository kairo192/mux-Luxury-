import { test, expect } from "@playwright/test";
import { SHOP, ensureCategory, publicApi, watch, cmsLogin, cmsOpen, fieldAfter, uid } from "../support/helpers";

test.describe("catalogue: CMS -> shop", () => {
  test("a product created in the CMS editor is on sale in the shop", async ({ page }) => {
    const cat = await ensureCategory();
    const s = uid();
    const name = `Sac Atelier ${s}`;
    const w = watch(page);
    await cmsLogin(page);
    await cmsOpen(page, "Produits");
    await page.getByRole("button", { name: "Nouveau produit" }).first().click();
    const ed = page.locator("div.fixed.inset-0").last();
    await expect(ed).toContainText("Nouvelle pièce de collection");

    await ed.getByRole("combobox", { name: "Catégorie *" }).selectOption(String(cat.id));
    await fieldAfter(ed, "Nom (FR) *").fill(name);
    await fieldAfter(ed, "SKU *").fill(`ATL-${s.toUpperCase()}`);
    await fieldAfter(ed, "Coût d'achat (DA) *").fill("7000");
    await fieldAfter(ed, "Prix de vente (DA) *").fill("15500");
    await fieldAfter(ed, "Statut").selectOption("published").catch(() => undefined);

    await ed.getByRole("button", { name: /Déclinaisons/ }).first().click();
    await ed.getByLabel("Stock par défaut").fill("3");
    const noir = ed.getByRole("button", { name: "Noir", exact: true });
    if ((await noir.getAttribute("aria-pressed")) !== "true") await noir.click();
    await expect(noir).toHaveAttribute("aria-pressed", "true");
    await ed.getByRole("button", { name: /Ajouter 1 combinaison/ }).click();

    // A main photo is required to publish (the editor refuses otherwise).
    await ed.getByRole("button", { name: /Visuels/ }).first().click();
    await ed.locator('input[type="file"]').first().setInputFiles(require("node:path").join(__dirname, "..", "fixtures", "sac.jpg"));
    await expect(ed.locator("img").first()).toBeVisible();
    await page.waitForTimeout(800);

    await ed.getByRole("button", { name: /Créer le produit/ }).click();
    await expect(page.locator("div.fixed.inset-0").filter({ hasText: "Nouvelle pièce de collection" })).toHaveCount(0, { timeout: 15_000 });

    // Server: published with its variant and stock.
    const list = await publicApi<any>("/products?page_size=50");
    const prod = list.body.items.find((p: any) => p.name_fr === name);
    expect(prod, "product visible on the public API").toBeTruthy();
    expect(prod.selling_price_dzd).toBe(15500);
    expect(prod.variants.length).toBe(1);
    expect(String(prod.main_image_url || "")).toMatch(/uploads|\.(jpe?g|webp|png)/);

    // Shop: product page with price and stock.
    await page.goto(`${SHOP}/produit/${prod.slug}`);
    const modal = page.locator("#product-detail-modal");
    await expect(modal).toContainText(name);
    await expect(modal).toContainText("15 500 DA");
    await expect(modal).toContainText("En stock (3)");
    w.expectClean();
  });

  test("an archived product disappears from the shop at once", async ({ page }) => {
    const { createProduct, api } = await import("../support/helpers");
    const cat = await ensureCategory();
    const p = await createProduct({ name: "Pochette Archive", price: 6000, stock: 2, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
    await page.goto(`${SHOP}/produit/${p.slug}`);
    await expect(page.locator("#product-detail-modal")).toContainText("Pochette Archive");
    await api("/admin/products/bulk-status", { body: { product_ids: [p.productId], status: "archived" } });
    expect((await publicApi(`/products/${p.slug}`)).status).toBe(404);
    await page.goto(`${SHOP}/produit/${p.slug}`);
    await expect(page.locator("body")).toContainText("plus disponible");
  });
});
