import { test, expect } from "@playwright/test";
import { API, CMS, SHOP, OWNER, CASHIER, publicApi, watch, cmsLogin, cmsOpen, lastNotice } from "../support/helpers";

// A brand-new production installation: empty database, no demo data.
test.describe("first installation", () => {
  test("the owner account is created by the setup wizard", async ({ page }) => {
    const w = watch(page);
    await page.goto(CMS);
    await expect(page.locator("#owner-name")).toBeVisible();
    await page.locator("#owner-name").fill(OWNER.name);
    await page.locator("#owner-email").fill(OWNER.email);
    await page.locator("#owner-password").fill(OWNER.password);
    await page.locator("#owner-confirm").fill(OWNER.password);
    await page.locator("#owner-phone").fill(OWNER.phone);
    await page.locator('button[type="submit"]').click();
    await expect(page.locator("aside[aria-label]")).toBeVisible({ timeout: 20_000 });
    expect(await lastNotice(page)).toContain("Compte propriétaire créé");
    // the "status" call before setup answers 401/404 by design
    w.expectClean([/auth\/(me|status)/, /401 /]);
  });

  test("the setup wizard cannot be used a second time", async () => {
    const r = await fetch(`${API}/api/v1/admin/auth/initialize-owner`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: "Intrus", email: "intrus@example.com", password: "Intrus-2026-xx" }),
    });
    expect([403, 409]).toContain(r.status);
    expect((await r.json()).detail).toContain("compte propriétaire existe déjà");
  });

  test("a production shop starts empty: no demo products, banners or codes", async ({ page }) => {
    const w = watch(page);
    const products = await publicApi<any>("/products");
    expect(products.body.total ?? products.body.items.length).toBe(0);
    const layout = await publicApi<any>("/store/layout");
    expect(layout.body.banners ?? []).toEqual([]);
    await page.goto(SHOP);
    await expect(page.locator("body")).toContainText(/Mus Luxury/i);
    w.expectClean();
  });

  test("a wrong password is refused with a French message", async ({ page }) => {
    await page.goto(CMS);
    await page.locator("#login-email").fill(OWNER.email);
    await page.locator("#login-password").fill("mauvais-mot-de-passe");
    await page.locator('button[type="submit"]').click();
    await expect(page.locator("body")).toContainText(/incorrect|invalide|identifiants/i);
    await expect(page.locator("aside[aria-label]")).toHaveCount(0);
  });

  test("the owner creates a cashier account", async ({ page }) => {
    const w = watch(page);
    await cmsLogin(page);
    await cmsOpen(page, "Utilisateurs & rôles");
    await page.getByRole("button", { name: "Nouvel utilisateur" }).click();
    const form = page.locator("div.fixed.inset-0").last();
    await form.getByLabel("Nom complet").fill(CASHIER.name);
    await form.getByLabel("Email").fill(CASHIER.email);
    await form.getByLabel("Rôle").selectOption({ label: "Caissier" });
    await form.getByLabel("Mot de passe").fill(CASHIER.password);
    await form.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.locator("main")).toContainText(CASHIER.email);
    w.expectClean();
  });
});
