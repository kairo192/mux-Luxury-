import { test, expect, type Page } from "@playwright/test";
import { api, createProduct, ensureCategory, watch, cmsLogin, cmsOpen, uid } from "../support/helpers";

// Purchases, treasury, reports and accounting: figures agree, files download.
async function downloadFrom(page: Page, click: () => Promise<void>) {
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15_000 }), click()]);
  const path = await dl.path();
  const text = require("node:fs").readFileSync(path!, "utf8").replace(/^﻿/, "");
  return { name: dl.suggestedFilename(), text };
}

test.describe("CMS finance", () => {
  test("supplier purchase: stock in, landed cost, supplier debt, payment from the bank", async () => {
    const cat = await ensureCategory();
    const p = await createProduct({ name: "Sac Fournisseur", price: 10000, cost: 4000, stock: 0, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
    const sup = await api("/admin/suppliers", { body: { name: `Atelier ${uid()}` } });
    const po = await api("/admin/purchases", { body: { supplier_id: sup.id, shipping_dzd: 1000, items: [{ product_id: p.productId, variant_id: p.variantId, quantity: 10, unit_cost_dzd: 5000 }] } });
    expect(po.total_cost_dzd).toBe(51000);
    const bank0 = (await api("/admin/treasury/summary")).bank_balance_dzd;
    await api(`/admin/purchases/${po.id}/receive`, { body: {} });
    const prod = (await api("/admin/products")).items.find((x: any) => x.id === p.productId);
    expect(prod.variants[0].stock_qty).toBe(10);
    expect(prod.purchase_cost_dzd).toBe(5100); // 5 000 + 1 000 shipping spread over 10
    expect((await api(`/admin/suppliers/${sup.id}`)).balance_dzd).toBe(51000);
    await api(`/admin/purchases/${po.id}/pay?payment_method=bank_transfer`, { body: {} });
    expect((await api(`/admin/suppliers/${sup.id}`)).balance_dzd).toBe(0);
    expect((await api("/admin/treasury/summary")).bank_balance_dzd - bank0).toBe(-51000);
  });

  test("reports open and export French CSV files", async ({ page }) => {
    const w = watch(page);
    await cmsLogin(page);
    for (const [screen, file] of [["Rapport de ventes", /sales_/], ["Rapport dépenses", /expense|depense/], ["Rapport trésorerie", /tresorerie|treasury/], ["Mouvements de stock", /inventory|mouvements|movements/]] as const) {
      await cmsOpen(page, screen);
      const main = page.locator("main");
      const csv = main.getByRole("button", { name: /CSV|Exporter|Télécharger/ }).first();
      await expect(csv).toBeVisible();
      const { name, text } = await downloadFrom(page, () => csv.click());
      expect(name).toMatch(file);
      expect(text.split(/\r?\n/)[0]).toContain(";"); // Excel (French) separator
    }
    w.expectClean();
  });

  test("accounting: same result as Analytique, each tab exports its own CSV", async ({ page }) => {
    const w = watch(page);
    const pnl = await api("/admin/accounting/pnl");
    const biz = await api("/admin/dashboard/business");
    // Everything in this test database happened this month.
    expect(biz.margin_month.revenue_dzd).toBe(pnl.total_revenue_dzd);
    expect(biz.margin_month.net_profit_dzd).toBe(pnl.net_operating_profit_dzd);

    await cmsLogin(page);
    await cmsOpen(page, "Comptabilité");
    const main = page.locator("main");
    const csv = () => main.getByRole("button", { name: "CSV", exact: true }).click();
    const pl = await downloadFrom(page, csv);
    expect(pl.name).toMatch(/^compte_de_resultat_/);
    expect(pl.text).toContain(`Chiffre d'affaires;${pnl.total_revenue_dzd}`);
    await main.getByRole("button", { name: /Rentabilité par produit/ }).click();
    expect((await downloadFrom(page, csv)).name).toMatch(/^rentabilite_produits_/);
    await main.getByRole("button", { name: "Journal achats & dépenses" }).click();
    await expect(main).toContainText("Journal équilibré");
    expect((await downloadFrom(page, csv)).name).toMatch(/^journal_achats_depenses_/);
    w.expectClean();
  });

  test("a cashier cannot see the money", async () => {
    const { CASHIER } = await import("../support/helpers");
    for (const path of ["/admin/accounting/pnl", "/admin/treasury/summary", "/admin/dashboard/business", "/admin/expenses", "/admin/purchases"]) {
      await api(path, { as: CASHIER.email, expect: [403] });
    }
    const dash = await api("/admin/dashboard", { as: CASHIER.email });
    expect(dash.finance_visible).toBe(false);
    expect(dash.total_revenue_dzd).toBeNull();
  });
});
