import { test, expect, type Page } from "@playwright/test";
import { SHOP, api, publicApi, createProduct, ensureCategory, watch, uid, cmsLogin, cmsOpen, lastNotice } from "../support/helpers";

// The customer's side: browse, languages, cart, promo code, checkout,
// validation, order tracking, sold-out items.
let cat: Awaited<ReturnType<typeof ensureCategory>>;
let bag: Awaited<ReturnType<typeof createProduct>>;

test.beforeAll(async () => {
  cat = await ensureCategory();
  bag = await createProduct({ name: "Sac Boutique", price: 12000, cost: 5000, stock: 4, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
});

async function fillCheckout(page: Page, phone: string) {
  await page.evaluate(() => (window as any).openCartDrawer());
  await page.locator("#chk-name").fill("Amina Client");
  await page.locator("#chk-phone").fill(phone);
  await page.locator("#chk-wilaya").selectOption("16");
  const communes = page.locator("#chk-commune option");
  if ((await communes.count()) > 1) await page.locator("#chk-commune").selectOption({ index: 1 });
  await page.locator("#chk-address").fill("12 rue des Oliviers, Alger");
}

async function addBagToCart(page: Page) {
  await page.goto(`${SHOP}/produit/${bag.slug}`);
  const modal = page.locator("#product-detail-modal");
  await expect(modal).toContainText("Sac Boutique");
  await modal.getByRole("button", { name: /Ajouter au panier/ }).first().click();
}

test.describe("shop", () => {
  test("home page lists the category and the product, without errors", async ({ page }) => {
    const w = watch(page);
    await page.goto(SHOP);
    await expect(page.locator("body")).toContainText("Sac Boutique");
    await expect(page.locator("body")).toContainText("12 000 DA");
    w.expectClean();
  });

  test("Arabic and English versions", async ({ page }) => {
    await page.goto(SHOP);
    await page.evaluate(() => localStorage.setItem("luxe_store_lang", "ar"));
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.evaluate(() => localStorage.setItem("luxe_store_lang", "en"));
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  });

  test("product page: price, stock, add to cart", async ({ page }) => {
    const w = watch(page);
    await addBagToCart(page);
    await expect(page.locator("#product-detail-modal")).toContainText("En stock (4)");
    await expect(page.locator("#cart-count-badge")).toHaveText("1");
    w.expectClean();
  });

  test("delivery prices come from the server, never invented", async ({ page }) => {
    const zones = (await publicApi<any>("/delivery-zones")).body.items as any[];
    const alger = zones.find((z) => z.wilaya_code === "16");
    const homeFee = Number(alger.rates.home.fee_dzd);
    const fmt = (n: number) => new RegExp(String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\\s") + "\\sDA");
    await addBagToCart(page);
    await page.evaluate(() => (window as any).openCartDrawer());
    await page.locator("#chk-wilaya").selectOption("16");
    await expect(page.locator("#chk-card-home-fee")).toHaveText(fmt(homeFee));
    await expect(page.locator('#chk-wilaya option[value="16"]')).toContainText("Dom:");

    // Price list unreachable: names stay, prices say "loading", no made-up figure.
    const blocked = await page.context().newPage();
    await blocked.route("**/api/v1/delivery-zones*", (r) => r.abort());
    await blocked.goto(`${SHOP}/produit/${bag.slug}`);
    const modal = blocked.locator("#product-detail-modal");
    await expect(modal).toContainText("Tarif en cours…");
    await modal.getByRole("button", { name: /Ajouter au panier/ }).first().click();
    await blocked.evaluate(() => (window as any).openCartDrawer());
    await expect(blocked.locator('#chk-wilaya option[value="16"]')).not.toContainText("Dom:");
    await expect(blocked.locator("#chk-summary-fee")).toHaveText("Tarif en cours…");
    await expect(blocked.locator("#chk-summary-total")).toContainText("+ livraison");
    await blocked.close();
  });

  test("opening hours and the Maps link set in the CMS show on the shop", async ({ page }) => {
    const w = watch(page);
    await cmsLogin(page);
    await cmsOpen(page, "Contenu & Bannières");
    const main = page.locator("main");
    await main.locator("#store-opening-hours").fill("Samedi : 09h00 – 19h00\nVendredi : Fermé");
    await main.getByPlaceholder("https://www.google.com/maps/…").fill("https://maps.app.goo.gl/e2eBoutique");
    await main.getByRole("button", { name: "Enregistrer les coordonnées" }).click();
    await expect.poll(async () => (await lastNotice(page)).includes("enregistrés")).toBe(true);
    expect((await publicApi<any>("/store/settings")).body.opening_hours).toBe("Samedi : 09h00 – 19h00\nVendredi : Fermé");

    await page.goto(SHOP);
    const hours = page.locator("#store-hours-list");
    await expect(hours).toContainText("09h00 – 19h00");
    await expect(hours).toContainText("Fermé");
    await expect(hours).not.toContainText("Dimanche");
    await expect(page.locator("a[data-maps-link]").first()).toHaveAttribute("href", "https://maps.app.goo.gl/e2eBoutique");
    w.expectClean();
  });

  test("checkout refuses an invalid phone number (no order created)", async ({ page }) => {
    await addBagToCart(page);
    const before = (await api("/admin/orders")).items.length;
    await fillCheckout(page, "12345");
    await page.getByRole("button", { name: /Confirmer la commande/ }).click();
    await expect(page.locator("body")).toContainText(/téléphone|numéro/i);
    expect((await api("/admin/orders")).items.length).toBe(before);
  });

  test("checkout with a promo code: the server order matches what the customer saw", async ({ page }) => {
    const w = watch(page);
    const code = `BIENVENUE${uid().toUpperCase()}`;
    await api("/admin/coupons", { body: { code, discount_type: "percentage", discount_value: 10 } });
    await addBagToCart(page);
    const phone = "0661" + String(Date.now()).slice(-6);
    await fillCheckout(page, phone);
    await page.locator("#chk-coupon").fill(code.toLowerCase());
    await page.getByRole("button", { name: "Appliquer" }).click();
    const drawer = page.locator("#cart-checkout-modal");
    await expect(drawer).toContainText("- 1 200 DA");
    await expect(drawer).toContainText("11 200 DA");
    await page.getByRole("button", { name: /Confirmer la commande/ }).click();
    await expect(page.locator("body")).toContainText("Commande confirmée");
    const ref = (await page.locator("body").innerText()).match(/LUX-[0-9A-Z-]+/)![0];
    const order = (await api("/admin/orders")).items.find((o: any) => o.order_reference === ref);
    expect(order).toMatchObject({ status: "new", subtotal_dzd: 12000, discount_dzd: 1200, coupon_code: code, delivery_fee_dzd: 400, total_dzd: 11200, customer_phone: phone });
    // stock reserved at once on the shop
    await page.goto(`${SHOP}/produit/${bag.slug}`);
    await expect(page.locator("#product-detail-modal")).toContainText("En stock (3)");
    w.expectClean();
  });

  test("order tracking shows the status set in the CMS", async ({ page }) => {
    const phone = "0662" + String(Date.now()).slice(-6);
    const r = await fetch(`${process.env.E2E_API_URL}/api/v1/orders`, {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": `trk-${phone}` },
      body: JSON.stringify({ full_name: "Suivi Client", phone, wilaya_code: "16", commune: "Alger Centre",
        delivery_address: "5 rue du Suivi, Alger", delivery_method: "home", items: [{ variant_id: bag.variantId, quantity: 1 }] }),
    });
    const o = await r.json();
    await api(`/admin/orders/${o.order_id}`, { method: "PATCH", body: { status: "confirmed" } });
    await page.goto(SHOP);
    await page.evaluate(() => (window as any).openOrderTrackingModal());
    await page.locator("#track-order-ref").fill(o.order_reference);
    await page.locator("#track-order-phone").fill(phone);
    await page.evaluate(() => (window as any).lookupGuestOrderStatus());
    await expect(page.locator("#track-order-result")).toContainText("Confirmée");
    await api(`/admin/orders/${o.order_id}`, { method: "PATCH", body: { status: "cancelled" } });
    await page.evaluate(() => (window as any).lookupGuestOrderStatus());
    await expect(page.locator("#track-order-result")).toContainText("Annulée");
    expect((await publicApi(`/orders/track?reference=${o.order_reference}&phone=0550000000`)).status).toBe(404);
  });

  test("a sold-out product cannot be added to the cart", async ({ page }) => {
    const p = await createProduct({ name: "Minaudière Unique", price: 9000, stock: 1, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
    await api("/admin/pos/register/current").then(async (cur) => {
      if (!cur.session) await api("/admin/pos/register/open", { body: { register_name: "Caisse E2E", opening_float_dzd: 0 } });
    });
    await api("/admin/pos/sales", { body: { items: [{ variant_id: p.variantId, quantity: 1 }], payments: [{ method: "cash", amount_dzd: 9000 }] }, headers: { "Idempotency-Key": `so-${uid()}` } });
    await page.goto(`${SHOP}/produit/${p.slug}`);
    const modal = page.locator("#product-detail-modal");
    await expect(modal).toContainText("Rupture de stock");
    await expect(modal.getByRole("button", { name: /Ajouter au panier|Rupture|Épuisé/ }).first()).toBeDisabled();
  });
});

// An Arabic-speaking customer on a phone: right-to-left page, prices still read
// "9 500 DA" (not "DA 500 9"), the form and the confirmation in Arabic.
test.describe("shop in Arabic on a phone", () => {
  test.use({ viewport: { width: 390, height: 664 }, isMobile: true, hasTouch: true, locale: "ar-DZ" });

  test("order from start to finish, no sideways scrolling", async ({ page }) => {
    const w = watch(page);
    const p = await createProduct({ name: "Sac Arabe", price: 9500, stock: 2, categoryId: cat.id, attrKey: cat.attrKey, value: cat.value });
    await page.goto(SHOP);
    await page.evaluate(() => localStorage.setItem("luxe_store_lang", "ar"));
    await page.goto(`${SHOP}/produit/${p.slug}`);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    const modal = page.locator("#product-detail-modal");
    // the price is one left-to-right block (Unicode isolate marks around it)
    expect(await modal.innerText()).toContain("⁦9 500 DA⁩");
    const noSideScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
    expect(await noSideScroll()).toBe(true);

    await modal.locator("button", { hasText: /أضف|Ajouter/ }).first().click();
    await page.evaluate(() => (window as any).openCartDrawer());
    const drawer = page.locator("#cart-checkout-modal");
    await expect(drawer).toContainText("معلومات التوصيل");
    expect(await noSideScroll()).toBe(true);
    await page.locator("#chk-name").fill("أمينة بن علي");
    await page.locator("#chk-phone").fill("0771" + String(Date.now()).slice(-6));
    await page.locator("#chk-wilaya").selectOption("09");
    await page.locator("#chk-address").fill("حي 100 مسكن، أولاد يعيش");
    await drawer.locator("button", { hasText: "تأكيد الطلب" }).click();
    await expect(drawer).toContainText("تم تأكيد طلبك");
    await expect(drawer).toContainText("أمينة بن علي");
    await page.evaluate(() => (window as any).openOrderTrackingModal());
    await expect(page.locator("#trk-title")).toHaveText("تتبع الطلب");
    await expect(page.locator("#trk-submit")).toContainText("البحث عن طلبي");
    await expect(page.locator("footer")).toContainText("معلومات ومساعدة");
    await expect(page.locator("footer")).not.toContainText("Questions fréquentes");
    w.expectClean();
  });
});
