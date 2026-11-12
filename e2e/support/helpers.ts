import { expect, type Page } from "@playwright/test";

export const API = process.env.E2E_API_URL!;
export const CMS = process.env.E2E_CMS_URL!;
export const SHOP = process.env.E2E_SHOP_URL!;

// Accounts created by the tests themselves on the fresh database.
export const OWNER = { name: "Propriétaire E2E", email: "owner.e2e@musluxury.dz", password: "Proprio-E2E-2026!", phone: "0550123456" };
export const CASHIER = { name: "Caissière E2E", email: "caisse.e2e@musluxury.dz", password: "Caisse-E2E-2026!" };

// ---------------------------------------------------------------- server API
const tokens = new Map<string, string>();

export async function token(email = OWNER.email, password = OWNER.password): Promise<string> {
  const cached = tokens.get(email);
  if (cached) return cached;
  const r = await fetch(`${API}/api/v1/admin/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`login ${email}: ${r.status} ${await r.text()}`);
  const t = (await r.json()).access_token as string;
  tokens.set(email, t);
  return t;
}

/** Calls the admin API as the owner (or `as`); throws on an unexpected status. */
export async function api<T = any>(path: string, init: { method?: string; body?: unknown; headers?: Record<string, string>; as?: string; expect?: number[] } = {}): Promise<T> {
  const tok = await token(init.as ?? OWNER.email, init.as === CASHIER.email ? CASHIER.password : OWNER.password);
  const r = await fetch(`${API}/api/v1${path}`, {
    method: init.method ?? (init.body === undefined ? "GET" : "POST"),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}`, ...(init.headers || {}) },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const ok = init.expect ?? [200, 201];
  const text = await r.text();
  if (!ok.includes(r.status)) throw new Error(`${init.method ?? "GET"} ${path}: ${r.status} ${text.slice(0, 300)}`);
  return (text ? JSON.parse(text) : {}) as T;
}

export async function publicApi<T = any>(path: string): Promise<{ status: number; body: T }> {
  const r = await fetch(`${API}/api/v1${path}`);
  return { status: r.status, body: (await r.json().catch(() => ({}))) as T };
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 7);
}

/** A published product with one variant, created through the API. */
export async function createProduct(opts: { name: string; price: number; cost?: number; stock: number; categoryId: number; attrKey: string; value: string }) {
  const s = uid();
  const slug = `${opts.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${s}`;
  const sku = `E2E-${s.toUpperCase()}`;
  await api("/admin/products", { body: {
    category_id: opts.categoryId, slug, sku, name_fr: opts.name, selling_price_dzd: opts.price,
    purchase_cost_dzd: opts.cost ?? Math.round(opts.price / 2), status: "published",
    variants: [{ sku: `${sku}-1`, title: opts.value, stock_qty: opts.stock, attributes: { [opts.attrKey]: opts.value } }],
  } });
  const pub = await publicApi<any>(`/products/${slug}`);
  return { slug, sku, productId: pub.body.id as number, variantId: pub.body.variants[0].id as number };
}

export async function ensureCategory(): Promise<{ id: number; attrKey: string; value: string }> {
  const slug = `e2e-sacs-${uid()}`;
  const cat = await api("/admin/categories", { body: {
    slug, name_fr: "Sacs E2E", name_ar: "حقائب", name_en: "Bags", display_order: 1, is_active: true, show_on_homepage: true,
  } });
  await api("/admin/category-attributes", { body: {
    category_id: cat.id, attr_key: "couleur", label_fr: "Couleur", input_type: "single_select", is_variant_axis: true,
    options: [{ value: "noir", label_fr: "Noir" }, { value: "rouge", label_fr: "Rouge" }],
  } });
  return { id: cat.id, attrKey: "couleur", value: "noir" };
}

// ------------------------------------------------------------ page watchers
/** Fails the test on page crashes, console errors and server errors (5xx);
 *  4xx are listed so a test can assert none happened. */
export function watch(page: Page) {
  const errors: string[] = [];
  const failed: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text());
  });
  page.on("response", (r) => {
    if (r.url().includes("/api/v1/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^.*\/api\/v1/, "")}`);
  });
  return {
    errors, failed,
    expectClean(allow: RegExp[] = []) {
      expect(errors, "no page or console errors").toEqual([]);
      expect(failed.filter((f) => !allow.some((a) => a.test(f))), "no failed API calls").toEqual([]);
    },
  };
}

// ---------------------------------------------------------------------- CMS
export async function closeMessageBoxes(page: Page) {
  for (let i = 0; i < 5; i++) {
    if (!(await page.locator('[aria-labelledby="active-message-box-title"]').count())) return;
    await page.keyboard.press("Escape");
    await page.waitForTimeout(150);
  }
}

export async function cmsLogin(page: Page, who: { email: string; password: string } = OWNER, lang: "fr" | "en" | "ar" = "fr") {
  await page.goto(CMS);
  await page.evaluate((l) => localStorage.setItem("luxe_cms_lang", l), lang);
  await page.reload();
  await page.locator("#login-email").fill(who.email);
  await page.locator("#login-password").fill(who.password);
  await page.locator('button[type="submit"]').click();
  await expect(page.locator("aside[aria-label]")).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(800);
  await closeMessageBoxes(page);
}

/** Opens a CMS screen from the side menu (French label, badges ignored). */
export async function cmsOpen(page: Page, label: string) {
  const re = new RegExp("^" + label.replace(/[.*+?^${}()|[\]\\&]/g, "\\$&") + "(\\s*\\d+)?$");
  await page.locator("aside[aria-label] button").filter({ hasText: re }).first().click();
  await page.waitForTimeout(700);
  await closeMessageBoxes(page);
}

/** The text of the toast / message shown last (success or error). */
export async function lastNotice(page: Page): Promise<string> {
  const box = page.locator('[aria-labelledby="active-message-box-title"]');
  if (await box.count()) return (await box.first().innerText()).replace(/\s+/g, " ");
  const t = page.locator('[role="status"], [role="alert"]');
  const n = await t.count();
  return n ? (await t.nth(n - 1).innerText()).replace(/\s+/g, " ") : "";
}

export async function confirmDialog(page: Page) {
  const d = page.locator('[aria-labelledby="active-confirm-title"]');
  await expect(d).toBeVisible();
  await d.locator("button").last().click();
}

export function visibleMain(page: Page) {
  return page.locator("main");
}

/** The input / select / textarea that follows a visible label (forms whose
 *  labels are not linked to their field). */
export function fieldAfter(scope: import("@playwright/test").Locator, labelText: string) {
  return scope.locator(`xpath=.//label[contains(normalize-space(.), ${JSON.stringify(labelText)})]/following::*[self::input or self::select or self::textarea][1]`);
}
