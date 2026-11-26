import { test, expect, type Page } from "@playwright/test";
import { OWNER, CASHIER, CMS, ensureAccount, watch, cmsLogin, closeMessageBoxes } from "../support/helpers";

// Every screen of the menu, in the 3 languages, for the owner and a cashier:
// no crash, no console error, no refused / failed call, and nothing broken on
// screen (NaN, undefined, [object Object], raw translation keys).
const BROKEN = [/\bNaN\b/, /\bundefined\b/, /\[object Object\]/, /Invalid Date/, /\b[a-z_]+\.(?:btn|lbl|th|title|opt|empty|tab|desc)_[a-z_]+\b/];

async function menuEntries(page: Page): Promise<number> {
  return page.locator("aside[aria-label] button").evaluateAll((bs) =>
    bs.filter((b) => b.querySelector("svg") && (b as HTMLElement).innerText.trim()).length);
}

// Common French words of the CMS itself (not shop data — e.g. no "Commande": a test customer is "Karim Commande"):
// none may show in English or Arabic.
const FRENCH_UI = /\b(Enregistrer|Annuler|Supprimer|Modifier|Ajouter|Rechercher|Chargement|Fermer|Aucune?|Nouvelle?|Valider|Imprimer|Actualiser|Exporter|Fournisseurs?|Dépenses?|Trésorerie|Caisse|Tableau de bord)\b/;

async function sweep(page: Page, lang: "fr" | "en" | "ar" = "fr"): Promise<string[]> {
  const problems: string[] = [];
  const buttons = page.locator("aside[aria-label] button");
  const n = await buttons.count();
  for (let i = 0; i < n; i++) {
    const b = buttons.nth(i);
    if (!(await b.locator("svg").count())) continue; // section headers
    const label = (await b.innerText()).trim().split("\n")[0];
    if (!label || /Réduire|Collapse|طي/.test(label)) continue;
    await b.click();
    await page.waitForTimeout(600);
    await closeMessageBoxes(page);
    const text = await page.locator("main").innerText();
    for (const re of BROKEN) {
      const m = text.match(re);
      if (m) problems.push(`${label}: "${m[0]}"`);
    }
    if (lang !== "fr") {
      const all = await page.locator("body").innerText();
      const line = all.split("\n").find((l) => FRENCH_UI.test(l));
      if (line) problems.push(`${label}: French text in ${lang}: "${line.trim().slice(0, 120)}"`);
    }
  }
  return problems;
}

for (const who of [{ role: "owner", ...OWNER }, { role: "cashier", ...CASHIER }]) {
  for (const lang of ["fr", "en", "ar"] as const) {
    test(`${who.role} / ${lang}: every screen opens cleanly`, async ({ page }) => {
      test.setTimeout(120_000);
      const w = watch(page);
      await cmsLogin(page, who, lang);
      if (lang === "ar") await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      const entries = await menuEntries(page);
      if (who.role === "owner") expect(entries).toBeGreaterThan(25);
      else expect(entries).toBeLessThan(12); // a cashier sees the till, not the accounts
      expect(await sweep(page, lang)).toEqual([]);
      w.expectClean();
    });
  }
}

test("server messages follow the CMS language", async ({ page }) => {
  await ensureAccount(OWNER.email);
  await page.goto(CMS);
  await page.evaluate(() => localStorage.setItem("luxe_cms_lang", "ar"));
  await page.reload();
  await page.locator("#login-email").fill(OWNER.email);
  await page.locator("#login-password").fill("not-the-password-123");
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText(/البريد الإلكتروني أو كلمة المرور غير صحيحة/).first()).toBeVisible();
});
