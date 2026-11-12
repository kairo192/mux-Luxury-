import { test, expect } from "@playwright/test";
import { api, createProduct, ensureCategory, watch, cmsLogin, cmsOpen, confirmDialog, uid } from "../support/helpers";

// Daily operations in the back office, checked on screen AND on the server.
let cat: Awaited<ReturnType<typeof ensureCategory>>;
let bag: Awaited<ReturnType<typeof createProduct>>;

const stockOf = async (variantId: number) => {
  const items = (await api("/admin/products", { method: "GET" })).items as any[];
  for (const p of items) for (const v of p.variants) if (v.id === variantId) return v.stock_qty as number;
  throw new Error("variant not found");
};
const treasury = async () => {
  const t = await api("/admin/treasury/summary");
  return { cash: t.cash_balance_dzd as number, bank: t.bank_balance_dzd as number };
};

test.beforeAll(async () => {
  cat = await ensureCategory();
  bag = await createProduct({ name: "Cabas Opérations", price: 8000, cost: 3000, stock: 10, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
  const cur = await api("/admin/pos/register/current");
  if (cur.session) await api("/admin/pos/register/close", { body: { counted_cash_dzd: cur.session.expected_cash_dzd ?? 0 } });
});

test.describe("CMS operations", () => {
  test("online order: confirm, deliver (cash collected), cancel another (stock back)", async ({ page }) => {
    const w = watch(page);
    const place = async (phone: string) => (await (await fetch(`${process.env.E2E_API_URL}/api/v1/orders`, {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": `op-${phone}` },
      body: JSON.stringify({ full_name: "Karim Commande", phone, wilaya_code: "16", commune: "Alger Centre",
        delivery_address: "8 rue des Commandes, Alger", delivery_method: "home", items: [{ variant_id: bag.variantId, quantity: 1 }] }),
    })).json());
    const a = await place("0771" + String(Date.now()).slice(-6));
    const b = await place("0772" + String(Date.now()).slice(-6));
    expect(await stockOf(bag.variantId)).toBe(8);
    const t0 = await treasury();

    await cmsLogin(page);
    await cmsOpen(page, "Commandes");
    const cardA = page.locator(`[data-order-ref="${a.order_reference}"]`);
    await expect(cardA).toContainText("Cabas Opérations");
    for (const st of ["confirmed", "preparing", "ready_for_shipment", "shipped", "delivered"]) {
      await cardA.locator("select").selectOption(st);
      await page.waitForTimeout(500);
    }
    await expect.poll(async () => (await api("/admin/orders")).items.find((o: any) => o.id === a.order_id).status).toBe("delivered");
    expect((await treasury()).cash - t0.cash).toBe(a.total_dzd);

    const cardB = page.locator(`[data-order-ref="${b.order_reference}"]`);
    await cardB.locator("select").selectOption("cancelled");
    await confirmDialog(page);
    await expect.poll(() => stockOf(bag.variantId)).toBe(9);
    await expect(cardB.locator("select")).toBeDisabled();
    w.expectClean();
  });

  test("till: sale with change, refund, close with the counted cash", async ({ page }) => {
    const w = watch(page);
    const t0 = await treasury();
    const s0 = await stockOf(bag.variantId);
    await cmsLogin(page);
    await cmsOpen(page, "Point de vente");
    const open = page.getByRole("button", { name: "Ouvrir la caisse" });
    if (await open.count()) {
      // Opening cash on the touch keypad: +1 000 twice.
      const plus1000 = page.locator("main").getByRole("button", { name: /^\+\s?1[\s\u202f ]?000/ }).first();
      await plus1000.click();
      await plus1000.click();
      await expect(page.locator("main")).toContainText("2 000 DA");
      await open.click();
      await page.waitForTimeout(800);
    }
    await page.getByPlaceholder("Code-barres, SKU ou nom…").fill(bag.sku);
    await page.getByRole("button", { name: /^noir\s+8\s000\s+DA/i }).first().click();
    await page.getByRole("button", { name: /^Encaisser/ }).last().click();
    const pay = page.locator("div.fixed.inset-0").last();
    await pay.getByRole("button", { name: "+5 000" }).first().click();
    await pay.getByRole("button", { name: "+5 000" }).first().click();
    await expect(pay).toContainText("2 000 DA"); // change on 10 000 for 8 000
    await pay.getByRole("button", { name: /Valider la vente/ }).click();
    await expect.poll(() => stockOf(bag.variantId)).toBe(s0 - 1);
    expect((await treasury()).cash - t0.cash).toBe(8000);

    const sales = (await api("/admin/pos/sales")).items as any[];
    const sale = sales.find((x) => x.sale_type === "sale");
    await api(`/admin/pos/sales/${sale.id}/refund`, { body: { refund_method: "cash" } });
    expect(await stockOf(bag.variantId)).toBe(s0);
    expect((await treasury()).cash - t0.cash).toBe(0);

    const cur = (await api("/admin/pos/register/current")).session;
    expect(cur.expected_cash_dzd).toBe(2000);
    await api("/admin/pos/register/close", { body: { counted_cash_dzd: 1500 } });
    expect((await treasury()).cash - t0.cash).toBe(-500); // till 500 DA short
    w.expectClean([/register\/current/]);
  });

  test("stock: a damaged item leaves the stock and counts as a loss", async ({ page }) => {
    const w = watch(page);
    const pnl0 = await api("/admin/accounting/pnl");
    const s0 = await stockOf(bag.variantId);
    await cmsLogin(page);
    await cmsOpen(page, "Stock");
    await api("/admin/inventory/write-off", { body: { variant_id: bag.variantId, quantity: 1, reason: "damaged" } });
    expect(await stockOf(bag.variantId)).toBe(s0 - 1);
    const pnl1 = await api("/admin/accounting/pnl");
    expect(pnl0.net_operating_profit_dzd - pnl1.net_operating_profit_dzd).toBe(3000);
    expect(pnl1.stock_losses_dzd - (pnl0.stock_losses_dzd || 0)).toBe(3000);
    w.expectClean();
  });

  test("expenses: an unpaid bill is a charge; paying it moves the cash", async ({ page }) => {
    const w = watch(page);
    const t0 = await treasury();
    const pnl0 = await api("/admin/accounting/pnl");
    const exp = await api("/admin/expenses", { body: { description: `Électricité ${uid()}`, category: "electricite_eau", amount_dzd: 4200, payment_method: "cash", payment_status: "pending" } });
    expect((await api("/admin/accounting/pnl")).operating_expenses_dzd - pnl0.operating_expenses_dzd).toBe(4200);
    expect((await treasury()).cash).toBe(t0.cash);
    await cmsLogin(page);
    await cmsOpen(page, "Dépenses");
    const row = page.locator("tr", { hasText: exp.description }).first();
    await row.getByRole("button", { name: "Payer" }).click();
    await page.waitForTimeout(400);
    if (await page.locator('[aria-labelledby="active-confirm-title"]').count()) await confirmDialog(page);
    await expect.poll(async () => (await treasury()).cash - t0.cash).toBe(-4200);
    w.expectClean();
  });
});
