import { keychainSetSecret, keychainGetSecret, keychainDeleteSecret, getOsKeychainStatus } from "../utils/osKeychain";
import { ClientSafeApiError, sanitizeAndTranslateError } from "../utils/clientNotifier";
import { recordNetworkSample } from "../utils/networkQueue";
// ============================================================================
// TAURI 2 DESKTOP CMS — SHARED AUTHENTICATED HTTPS API CLIENT
// Features:
// - Configurable API base URL
// - Request timeout via AbortController (15s default)
// - Consistent JSON response parsing & structured error handling
// - Bearer token authentication & automatic 401 session expiration handling
// - HMAC-SHA256 cryptographic request signing & anti-replay nonces
// - Idempotency-Key support for non-idempotent mutations
// ============================================================================

let accessToken: string | null = null;
function resolveDefaultApiBaseUrl(): string {
  if (typeof sessionStorage !== "undefined") {
    try {
      const saved = sessionStorage.getItem("luxe_api_base_url");
      if (saved && saved.trim()) return saved.trim().replace(/\/+$/, "");
    } catch { /* ignore */ }
  }
  if (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_CMS_API_URL) {
    return String((import.meta as any).env.VITE_CMS_API_URL).replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.location) {
    const h = window.location.hostname;
    if (h === "localhost" || h === "127.0.0.1" || h === "tauri.localhost") {
      return "http://127.0.0.1:8000/api/v1";
    }
  }
  return "https://api.mus-luxury.com/api/v1";
}

let apiBaseUrl: string = resolveDefaultApiBaseUrl();
let defaultTimeoutMs = 15000;

export function configureApiBaseUrl(url: string) {
  apiBaseUrl = url.replace(/\/+$/, "");
  if (typeof sessionStorage !== "undefined") {
    try {
      sessionStorage.setItem("luxe_api_base_url", apiBaseUrl);
    } catch { /* ignore */ }
  }
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

/**
 * Address of the online shop that goes with the configured API:
 *   https://api.mus-luxury.com/api/v1 → https://mus-luxury.com
 *   http://localhost:8000/api/v1      → http://localhost:5173 (dev)
 */
export function storefrontBaseUrl(): string {
  try {
    const u = new URL(apiBaseUrl);
    if (u.hostname === "localhost" || u.hostname === "127.0.0.1") return `${u.protocol}//localhost:5173`;
    return `${u.protocol}//${u.hostname.replace(/^api\./, "")}`;
  } catch {
    return "https://mus-luxury.com";
  }
}

/**
 * Turns a stored image path into an address the CMS can display.
 * Uploaded photos (/uploads/…) live on the API server; built-in images
 * (/assets/…) live on the shop. Without this the CMS looked for them on
 * itself and every uploaded photo appeared broken.
 */
export function mediaUrl(url?: string | null): string {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^(https?:|data:|blob:)/i.test(raw)) return raw;
  const path = raw.startsWith("/") ? raw : `/${raw}`;
  if (path.startsWith("/uploads/")) {
    try {
      return new URL(apiBaseUrl).origin + path;
    } catch {
      return path;
    }
  }
  return storefrontBaseUrl() + path;
}

/** Neutral image for products/categories without a photo (works offline). */
export const PLACEHOLDER_IMG =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><rect width="600" height="600" fill="#063D2E"/>' +
      '<rect x="24" y="24" width="552" height="552" rx="28" fill="none" stroke="#D4AF62" stroke-opacity=".35" stroke-width="2"/>' +
      '<circle cx="300" cy="270" r="92" fill="none" stroke="#D4AF62" stroke-width="3"/>' +
      '<text x="300" y="300" text-anchor="middle" font-family="Georgia,serif" font-size="84" font-weight="700" fill="#D4AF62">ML</text>' +
      '<text x="300" y="430" text-anchor="middle" font-family="Georgia,serif" font-size="30" fill="#E8D4A5" letter-spacing="6">PHOTO À VENIR</text></svg>'
  );

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    void keychainSetSecret("luxe_cms_access_token", token);
  } else {
    void keychainDeleteSecret("luxe_cms_access_token");
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

export async function restoreSessionFromOsKeychain(): Promise<string | null> {
  const token = await keychainGetSecret("luxe_cms_access_token");
  if (token) {
    accessToken = token;
  }
  return token;
}

export async function computeSha256Hex(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function computeHmacSha256Hex(keyString: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(keyString),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function adminFetch(path: string, options: RequestInit = {}, timeoutMs = defaultTimeoutMs) {
  const method = (options.method || "GET").toUpperCase();
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const reqId = `cms_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    "X-Request-ID": reqId,
    ...((options.headers as Record<string, string>) || {}),
  };
  const activeToken = getAccessToken();
  if (activeToken) {
    headers["Authorization"] = `Bearer ${activeToken}`;
  }

  const canRetry = method === "GET" || Boolean(headers["Idempotency-Key"]);
  const maxAttempts = canRetry ? 3 : 1;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const startMs = Date.now();

    try {
      const res = await fetch(`${apiBaseUrl}${path}`, {
        // The CMS must always see live data: never answer from the WebView's
        // HTTP cache (public endpoints are cacheable for the storefront, which
        // made deleted categories "come back" after a reload).
        cache: "no-store",
        ...options,
        headers,
        signal: options.signal || controller.signal,
      });
      const rttMs = Date.now() - startMs;
      const serverReqId = res.headers.get("x-request-id") || reqId;
      recordNetworkSample({ online: true, latencyMs: rttMs, requestId: serverReqId, retried: attempt > 1 });

      if ([502, 503, 504].includes(res.status) && attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, attempt * 250));
        continue;
      }

      const contentType = res.headers.get("content-type") || "";
      const data = contentType.includes("application/json") ? await res.json().catch(() => ({})) : await res.text().catch(() => "");

      if (res.status === 401) {
        const isAuthEndpoint = path.includes("/admin/auth/login");
        if (!isAuthEndpoint) {
          setAccessToken(null);
        }
        const tr401 = sanitizeAndTranslateError(data, 401, path, "Authentification requise");
        throw new ClientSafeApiError({
          status: 401,
          title: tr401.title,
          userMessage: tr401.message,
          code: isAuthEndpoint ? tr401.code : "SESSION_EXPIRED",
        });
      }

      if (!res.ok) {
        const tr = sanitizeAndTranslateError(data, res.status, path, "Opération refusée");
        throw new ClientSafeApiError({
          status: res.status,
          title: tr.title,
          userMessage: tr.message,
          code: tr.code,
        });
      }

      // Realtime synchronization: Notify public storefront of changes immediately
      if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        try {
          if (typeof window !== "undefined") {
            const bc = new BroadcastChannel("mus_luxury_realtime");
            bc.postMessage({ type: "CATALOG_UPDATED", path, timestamp: Date.now() });
            window.dispatchEvent(new CustomEvent("mus_luxury_catalog_updated", { detail: { path } }));
          }
        } catch (_) {}
      }

      return data;
    } catch (err: any) {
      if (err instanceof ClientSafeApiError) {
        throw err;
      }
      if (attempt < maxAttempts) {
        recordNetworkSample({ online: true, retried: true });
        await new Promise((r) => setTimeout(r, attempt * 250));
        continue;
      }
      recordNetworkSample({ online: false, requestId: reqId });
      const trNet = sanitizeAndTranslateError(err, 0, path, "Erreur de communication");
      throw new ClientSafeApiError({
        status: trNet.status,
        title: trNet.title,
        userMessage: trNet.message,
        code: trNet.code,
      });
    } finally {
      clearTimeout(timer);
    }
  }
}

export const DesktopCmsApi = {
  // Authentication & First-Time Setup
  getSetupStatus: () => adminFetch("/admin/auth/setup-status"),
  initializeOwner: async (payload: {
    full_name: string;
    email: string;
    password: string;
    // whatsapp_phone is accepted by the backend but no longer collected in
    // the CMS owner-setup form (password recovery over WhatsApp removed).
    whatsapp_phone?: string;
    emergency_phone?: string;
  }) => {
    const data = await adminFetch("/admin/auth/initialize-owner", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (data?.access_token) {
      setAccessToken(data.access_token);
    }
    return data;
  },
  login: async (email: string, password: string) => {
    const data = await adminFetch("/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    return data;
  },
  logout: async () => {
    try {
      await adminFetch("/admin/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
    }
  },
  // Password-recovery endpoints removed. Owner-side password reset is now a
  // server-side CLI operation only (backend/scripts/emergency_reset_owner.py).

  // Dashboard & Delta Synchronization
  getDashboard: () => adminFetch("/admin/dashboard"),
  getBusinessDashboard: () => adminFetch("/admin/dashboard/business"),
  deltaSync: (sinceOrderId = 0, sinceMovementId = 0) =>
    adminFetch(`/admin/sync/delta?since_order_id=${sinceOrderId}&since_movement_id=${sinceMovementId}`),

  // Dynamic Categories & 14-Type Attribute Builder
  // Admin list (never the cached public one). includeArchived=true also
  // returns archived categories (deleted_at set) for the Categories page.
  listCategories: (includeArchived = false) =>
    adminFetch(`/admin/categories?include_archived=${includeArchived}`),
  // Database administration (owner only) — see backend/app/backup_engine.py
  getDatabaseStatus: () => adminFetch("/admin/system/database", {}, 30000),
  createDatabaseBackup: (includeMedia = false) =>
    adminFetch("/admin/system/backups", { method: "POST", body: JSON.stringify({ include_media: includeMedia }) }, 180000),
  restoreDatabaseBackup: (name: string, password: string, confirm: string) =>
    adminFetch(`/admin/system/backups/${encodeURIComponent(name)}/restore`, {
      method: "POST",
      body: JSON.stringify({ password, confirm }),
    }, 300000),
  /** Encrypted backup file, for the copy kept on the owner's PC. */
  downloadBackupForPc: async (name: string): Promise<Uint8Array> => {
    const token = getAccessToken();
    const res = await fetch(`${apiBaseUrl}/admin/system/backups/${encodeURIComponent(name)}/download`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const tr = sanitizeAndTranslateError(data, res.status, "/admin/system/backups/download", "Copie impossible");
      throw new ClientSafeApiError({ status: res.status, title: tr.title, userMessage: tr.message, code: tr.code });
    }
    return new Uint8Array(await res.arrayBuffer());
  },
  /** Sends a copy kept on the PC back to the server so it can be restored. */
  importBackupFromPc: (fileName: string, bytes: Uint8Array) => {
    const fd = new FormData();
    fd.append("file", new Blob([bytes as Uint8Array<ArrayBuffer>], { type: "application/octet-stream" }), fileName);
    return adminFetch("/admin/system/backups/import", { method: "POST", body: fd }, 180000);
  },
  resetDatabase: (password: string, confirm: string, keepSettings: boolean) =>
    adminFetch("/admin/system/reset", {
      method: "POST",
      body: JSON.stringify({ password, confirm, keep_settings: keepSettings }),
    }, 300000),
  listAdminCategories: (includeArchived = true) =>
    adminFetch(`/admin/categories?include_archived=${includeArchived}`),
  createCategory: (payload: unknown) =>
    adminFetch("/admin/categories", { method: "POST", body: JSON.stringify(payload) }),
  updateCategory: (categoryId: number, payload: unknown) =>
    adminFetch(`/admin/categories/${categoryId}`, { method: "PUT", body: JSON.stringify(payload) }),
  restoreCategory: (categoryId: number) =>
    adminFetch(`/admin/categories/${categoryId}/restore`, { method: "POST" }),
  archiveCategory: (categoryId: number) =>
    adminFetch(`/admin/categories/${categoryId}`, { method: "DELETE" }),
  deleteCategory: (categoryId: number, hard = false) =>
    adminFetch(`/admin/categories/${categoryId}?hard_delete=${hard}`, { method: "DELETE" }),
  reorderCategories: (items: Array<{ id: number; display_order: number }>) =>
    adminFetch("/admin/categories-reorder", {
      method: "PUT",
      body: JSON.stringify({ items }),
    }),
  addCategoryAttribute: (payload: unknown) =>
    adminFetch("/admin/category-attributes", { method: "POST", body: JSON.stringify(payload) }),
  updateCategoryAttribute: (attrId: number, payload: unknown) =>
    adminFetch(`/admin/category-attributes/${attrId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCategoryAttribute: (attrId: number, forceMigrate = false) =>
    adminFetch(`/admin/category-attributes/${attrId}?force_migrate=${forceMigrate}`, { method: "DELETE" }),
  createAttributeOption: (attrId: number, payload: unknown) =>
    adminFetch(`/admin/category-attributes/${attrId}/options`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAttributeOption: (optionId: number, payload: unknown) =>
    adminFetch(`/admin/attribute-options/${optionId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteAttributeOption: (optionId: number) =>
    adminFetch(`/admin/attribute-options/${optionId}`, { method: "DELETE" }),

  // Brands & Products & Variant Matrix
  listBrands: () => adminFetch("/brands"),
  createBrand: (payload: { name: string; slug: string; logo_url?: string }) =>
    adminFetch("/admin/brands", { method: "POST", body: JSON.stringify(payload) }),
  listAdminProducts: (params?: { q?: string; category_id?: number; status?: string; include_archived?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.category_id) qs.set("category_id", String(params.category_id));
    if (params?.status) qs.set("status", params.status);
    if (params?.include_archived) qs.set("include_archived", "true");
    const queryStr = qs.toString();
    return adminFetch(`/admin/products${queryStr ? `?${queryStr}` : ""}`);
  },
  createProduct: (payload: unknown) =>
    adminFetch("/admin/products", { method: "POST", body: JSON.stringify(payload) }),
  updateProduct: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}`, { method: "PUT", body: JSON.stringify(payload) }),
  archiveProduct: (productId: number) =>
    adminFetch(`/admin/products/${productId}`, { method: "DELETE" }),
  deleteProduct: (productId: number, hard = false, force = false) =>
    adminFetch(`/admin/products/${productId}?hard_delete=${hard}&force=${force}`, { method: "DELETE" }),
  bulkUpdateProductStatus: (productIds: number[], status: "draft" | "published" | "archived") =>
    adminFetch("/admin/products/bulk-status", {
      method: "POST",
      body: JSON.stringify({ product_ids: productIds, status }),
    }),
  generateVariants: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}/generate-variants`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Variant CRUD (real color/size combination management)
  createVariant: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}/variants`, {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": `variant-create-${productId}-${Date.now()}` },
    }),
  updateVariant: (variantId: number, payload: unknown) =>
    adminFetch(`/admin/variants/${variantId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteVariant: (variantId: number) =>
    adminFetch(`/admin/variants/${variantId}`, { method: "DELETE" }),
  bulkUpdateVariants: (payload: {
    variant_ids: number[];
    set_stock_qty?: number;
    adjust_stock_qty?: number;
    set_price_override_dzd?: number;
    clear_price_override?: boolean;
    is_active?: boolean;
    reason?: string;
  }) =>
    adminFetch("/admin/variants/bulk-update", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": `variant-bulk-${Date.now()}` },
    }),

  // Inventory Management
  adjustVariantStock: (variantId: number, change_qty: number, reason: string) =>
    adminFetch(`/admin/variants/${variantId}/adjust-stock`, {
      method: "POST",
      body: JSON.stringify({ change_qty, reason }),
    }),
  listInventoryMovements: (variantId?: number) =>
    adminFetch(`/admin/inventory/movements${variantId ? `?variant_id=${variantId}` : ""}`),
  getLowStockReport: (includeOutOfStock = true) =>
    adminFetch(`/admin/inventory/low-stock?include_out_of_stock=${includeOutOfStock ? "true" : "false"}&limit=200`),

  // Physical inventory counts & reconciliation
  listInventoryCounts: (limit = 30) =>
    adminFetch(`/admin/inventory/counts?limit=${limit}`),
  openInventoryCount: (payload: { name?: string; notes?: string } = {}) =>
    adminFetch("/admin/inventory/counts", { method: "POST", body: JSON.stringify(payload) }),
  getInventoryCount: (countId: number) =>
    adminFetch(`/admin/inventory/counts/${countId}`),
  upsertInventoryCountLine: (countId: number, variant_id: number, counted_qty: number) =>
    adminFetch(`/admin/inventory/counts/${countId}/lines`, {
      method: "PUT",
      body: JSON.stringify({ variant_id, counted_qty }),
    }),
  deleteInventoryCountLine: (countId: number, lineId: number) =>
    adminFetch(`/admin/inventory/counts/${countId}/lines/${lineId}`, { method: "DELETE" }),
  applyInventoryCount: (countId: number) =>
    adminFetch(`/admin/inventory/counts/${countId}/apply`, { method: "POST" }),
  cancelInventoryCount: (countId: number) =>
    adminFetch(`/admin/inventory/counts/${countId}/cancel`, { method: "POST" }),

  // Fiscal settings (tax rate, legal identity, receipt text)
  getFiscalSettings: () => adminFetch("/admin/fiscal/settings"),
  updateFiscalSettings: (payload: { pos_tax_rate_percent?: number; settings?: Record<string, string> }) =>
    adminFetch("/admin/fiscal/settings", { method: "PUT", body: JSON.stringify(payload) }),

  // Typed stock write-offs (damage, loss, supplier return, etc.)
  listWriteOffReasons: () => adminFetch("/admin/inventory/write-off-reasons"),
  stockWriteOff: (variant_id: number, quantity: number, reason: string, notes?: string) =>
    adminFetch("/admin/inventory/write-off", {
      method: "POST",
      body: JSON.stringify({ variant_id, quantity, reason, notes }),
    }),

  // Order Management, Invoices & CSV Export
  listOrders: (status?: string) =>
    adminFetch(`/admin/orders${status ? `?status=${status}` : ""}`),
  updateOrderStatus: (orderId: number, status: string, internal_notes?: string) =>
    adminFetch(`/admin/orders/${orderId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, internal_notes }),
    }),
  getOrderInvoice: (orderId: number) => adminFetch(`/admin/orders/${orderId}/invoice`),
  getOrderDeliveryNote: (orderId: number) => adminFetch(`/admin/orders/${orderId}/delivery-note`),
  exportOrdersCsv: () => adminFetch("/admin/orders/export.csv"),
  listCustomers: () => adminFetch("/admin/customers"),
  searchCustomers: (q: string) => adminFetch(`/admin/customers/search?q=${encodeURIComponent(q)}`),
  getCustomer: (customerId: number) => adminFetch(`/admin/customers/${customerId}`),
  createCustomer: (payload: { full_name: string; phone: string; email?: string | null; wilaya_code?: string | null; commune?: string | null; address?: string | null; notes?: string | null }) =>
    adminFetch("/admin/customers", { method: "POST", body: JSON.stringify(payload) }),
  updateCustomer: (customerId: number, payload: unknown) =>
    adminFetch(`/admin/customers/${customerId}`, { method: "PUT", body: JSON.stringify(payload) }),
  accountingCsvUrl: (part: "pnl" | "products" | "ledger") =>
    `${getApiBaseUrl()}/admin/accounting/export.csv?part=${part}`,
  getSalesReport: (from: string, to: string) =>
    adminFetch(`/admin/reports/sales?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  salesReportCsvUrl: (from: string, to: string) =>
    `${getApiBaseUrl()}/admin/reports/sales.csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  getExpenseReport: (from: string, to: string) =>
    adminFetch(`/admin/reports/expenses?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  expenseReportCsvUrl: (from: string, to: string) =>
    `${getApiBaseUrl()}/admin/reports/expenses.csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  getInventoryMovementsReport: (from: string, to: string, variantId?: number) =>
    adminFetch(`/admin/reports/inventory-movements?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${variantId ? `&variant_id=${variantId}` : ""}`),
  inventoryMovementsCsvUrl: (from: string, to: string, variantId?: number) =>
    `${getApiBaseUrl()}/admin/reports/inventory-movements.csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${variantId ? `&variant_id=${variantId}` : ""}`,
  getTreasuryReport: (from: string, to: string) =>
    adminFetch(`/admin/reports/treasury?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  treasuryReportCsvUrl: (from: string, to: string) =>
    `${getApiBaseUrl()}/admin/reports/treasury.csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,

  // Anti-Retour COD (Customer Phone Return-Rate Scoring & Blacklist)
  checkPhoneCodRisk: (phone: string) =>
    adminFetch(`/admin/cod-risk/check?phone=${encodeURIComponent(phone)}`),
  listCodBlacklist: () => adminFetch("/admin/cod-risk/blacklist"),
  addPhoneToCodBlacklist: (phone: string, reason: string, is_blocked = true) =>
    adminFetch("/admin/cod-risk/blacklist", {
      method: "POST",
      body: JSON.stringify({ phone, reason, is_blocked }),
    }),
  removePhoneFromCodBlacklist: (phone: string) =>
    adminFetch(`/admin/cod-risk/blacklist/${encodeURIComponent(phone)}`, {
      method: "DELETE",
    }),
  notifyOrderCustomerWhatsapp: (
    orderId: number,
    template_type: "confirmation_call" | "shipped_notice" | "no_answer_followup" | "delivery_arrived" = "confirmation_call",
    custom_message?: string
  ) =>
    adminFetch(`/admin/orders/${orderId}/notify-whatsapp`, {
      method: "POST",
      body: JSON.stringify({ template_type, custom_message }),
    }),
  listCommunicationsOutbox: (limit = 30) =>
    adminFetch(`/admin/communications/outbox?limit=${limit}`),
  getKeychainStatus: () => getOsKeychainStatus(),

  // 69-Wilaya Delivery Tariffs (Home & Stop-Desk)
  getDeliveryZones: () => adminFetch("/delivery-zones"),
  updateDeliveryZone: (wilayaCode: string, payload: unknown) =>
    adminFetch(`/admin/delivery-zones/${wilayaCode}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  bulkUpdateDeliveryZones: (zones: unknown[]) =>
    adminFetch("/admin/delivery-zones-bulk", {
      method: "PUT",
      body: JSON.stringify({ zones }),
    }),

  // Website Layout, Banners, Coupons & Store Settings
  getStoreLayout: () => adminFetch("/store/layout"),
  updateHomepageSection: (sectionKey: string, payload: unknown) =>
    adminFetch(`/admin/homepage-sections/${sectionKey}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  listBanners: () => adminFetch("/admin/banners"),
  createBanner: (payload: unknown) =>
    adminFetch("/admin/banners", { method: "POST", body: JSON.stringify(payload) }),
  deleteBanner: (bannerId: number) =>
    adminFetch(`/admin/banners/${bannerId}`, { method: "DELETE" }),
  updateBanner: (bannerId: number, payload: unknown) =>
    adminFetch(`/admin/banners/${bannerId}`, { method: "PUT", body: JSON.stringify(payload) }),
  listHomepageSections: () => adminFetch("/admin/homepage-sections"),
  listCoupons: () => adminFetch("/admin/coupons"),
  createCoupon: (payload: unknown) =>
    adminFetch("/admin/coupons", { method: "POST", body: JSON.stringify(payload) }),
  deactivateCoupon: (couponId: number) =>
    adminFetch(`/admin/coupons/${couponId}`, { method: "DELETE" }),
  updateStoreSettings: (settings: Record<string, unknown>) =>
    adminFetch("/admin/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    }),

  // Product Image Gallery Management & Static Pages
  uploadMediaFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return adminFetch("/admin/upload", { method: "POST", body: fd });
  },
  addProductImage: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}/images`, { method: "POST", body: JSON.stringify(payload) }),
  reorderProductImages: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}/images/reorder`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteProductImage: (imageId: number) =>
    adminFetch(`/admin/product-images/${imageId}`, { method: "DELETE" }),
  listStaticPages: () => adminFetch("/pages"),
  upsertStaticPage: (slug: string, payload: unknown) =>
    adminFetch(`/admin/pages/${slug}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Backups, Audit History & Isolated Restoration Verification
  listAuditLogs: (
    opts: { limit?: number; action?: string; entity_type?: string; admin_user_id?: number; q?: string } = {}
  ) => {
    const qs = new URLSearchParams();
    if (opts.limit) qs.set("limit", String(opts.limit));
    if (opts.action) qs.set("action", opts.action);
    if (opts.entity_type) qs.set("entity_type", opts.entity_type);
    if (opts.admin_user_id !== undefined) qs.set("admin_user_id", String(opts.admin_user_id));
    if (opts.q) qs.set("q", opts.q);
    const q = qs.toString();
    return adminFetch(`/admin/audit-logs${q ? `?${q}` : ""}`);
  },
  getAuditLogFacets: () => adminFetch("/admin/audit-logs/facets"),
  checkReadiness: () => adminFetch("/ready"),
  // Admin-facing backup endpoints removed. Backups run as infrastructure
  // (cron + release-deploy pre-migration dump).

  // ERP: Suppliers & Purchasing
  listSuppliers: () => adminFetch("/admin/suppliers"),
  getSupplier: (supplierId: number) => adminFetch(`/admin/suppliers/${supplierId}`),
  createSupplier: (payload: unknown) =>
    adminFetch("/admin/suppliers", { method: "POST", body: JSON.stringify(payload) }),
  updateSupplier: (supplierId: number, payload: unknown) =>
    adminFetch(`/admin/suppliers/${supplierId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteSupplier: (supplierId: number) =>
    adminFetch(`/admin/suppliers/${supplierId}`, { method: "DELETE" }),

  listPurchases: () => adminFetch("/admin/purchases"),
  createPurchaseOrder: (payload: unknown) =>
    adminFetch("/admin/purchases", { method: "POST", body: JSON.stringify(payload) }),
  receivePurchaseOrder: (poId: number) =>
    adminFetch(`/admin/purchases/${poId}/receive`, { method: "POST" }),
  payPurchaseOrder: (poId: number, paymentMethod = "cash") =>
    adminFetch(`/admin/purchases/${poId}/pay?payment_method=${paymentMethod}`, { method: "POST" }),
  getPurchaseOrderLabels: (poId: number) =>
    adminFetch(`/admin/purchases/${poId}/labels`),

  // POS version compatibility probe
  checkPosCompat: (clientVersion = "1.0.0") =>
    adminFetch(`/pos/compat?client_version=${encodeURIComponent(clientVersion)}`),

  // Catalog mirror (offline POS)
  catalogSnapshot: () => adminFetch(`/admin/pos/catalog/snapshot`),
  catalogDeltas: (sinceIso: string) =>
    adminFetch(`/admin/pos/catalog/deltas?since=${encodeURIComponent(sinceIso)}`),

  // ERP: Operating Expenses
  listExpenses: (category?: string) =>
    adminFetch(`/admin/expenses${category ? `?category=${category}` : ""}`),
  createExpense: (payload: unknown) =>
    adminFetch("/admin/expenses", { method: "POST", body: JSON.stringify(payload) }),
  payExpense: (expenseId: number, method: string) =>
    adminFetch(`/admin/expenses/${expenseId}/pay?payment_method=${encodeURIComponent(method)}`, { method: "POST" }),
  deleteExpense: (expenseId: number) =>
    adminFetch(`/admin/expenses/${expenseId}`, { method: "DELETE" }),

  // ERP: Treasury & Cash Register
  getTreasurySummary: () => adminFetch("/admin/treasury/summary"),
  listCashMovements: (limit = 50) =>
    adminFetch(`/admin/treasury/movements?limit=${limit}`),
  recordCashMovement: (payload: unknown) =>
    adminFetch("/admin/treasury/movements", { method: "POST", body: JSON.stringify(payload) }),

  // ERP: Accounting Ledger & Financial Profit Analytics
  getPnlStatement: () => adminFetch("/admin/accounting/pnl"),
  getProductsProfitability: () => adminFetch("/admin/accounting/products-profitability"),
  getAccountingLedger: (limit = 100) =>
    adminFetch(`/admin/accounting/ledger?limit=${limit}`),

  // POS: Cash register sessions
  posRegisterCurrent: () => adminFetch("/admin/pos/register/current"),
  posRegisterOpen: (opening_float_dzd: number, register_name?: string, notes?: string) =>
    adminFetch("/admin/pos/register/open", {
      method: "POST",
      body: JSON.stringify({ opening_float_dzd, register_name, notes }),
    }),
  posRegisterClose: (counted_cash_dzd: number, notes?: string) =>
    adminFetch("/admin/pos/register/close", {
      method: "POST",
      body: JSON.stringify({ counted_cash_dzd, notes }),
    }),
  posListSessions: (limit = 50) => adminFetch(`/admin/pos/register/sessions?limit=${limit}`),

  // POS: Barcode / SKU lookup and in-store sales
  posLookup: (code: string) => adminFetch(`/admin/pos/lookup?code=${encodeURIComponent(code)}`),
  posCreateSale: (
    payload: {
      items: Array<{ variant_id: number; quantity: number; line_discount_dzd?: number }>;
      payments: Array<{ method: string; amount_dzd: number; tendered_dzd?: number }>;
      customer_id?: number | null;
      order_discount_dzd?: number;
      notes?: string;
    },
    idempotencyKey: string
  ) =>
    adminFetch("/admin/pos/sales", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  posListSales: (limit = 50, sessionId?: number) =>
    adminFetch(`/admin/pos/sales?limit=${limit}${sessionId ? `&session_id=${sessionId}` : ""}`),
  posSync: (
    operations: Array<{
      client_txn_id: string;
      type: "sale";
      register_session_id?: number | null;
      created_at_client?: string;
      payload: unknown;
    }>
  ) =>
    adminFetch("/admin/pos/sync", {
      method: "POST",
      body: JSON.stringify({ operations }),
      headers: { "Idempotency-Key": `pos-sync-${Date.now()}` },
    }),
  posGetSale: (saleId: number) => adminFetch(`/admin/pos/sales/${saleId}`),
  posGetSaleInvoice: (saleId: number) => adminFetch(`/admin/pos/sales/${saleId}/invoice`),
  posRefundSale: (
    saleId: number,
    payload: { items?: Array<{ variant_id: number; quantity: number }>; refund_method?: string; notes?: string }
  ) =>
    adminFetch(`/admin/pos/sales/${saleId}/refund`, {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": `pos-refund-${saleId}-${Date.now()}` },
    }),

  // Barcode & product identification
  validateBarcode: (code: string) => adminFetch(`/admin/barcodes/validate?code=${encodeURIComponent(code)}`),
  assignVariantBarcode: (variantId: number, barcode?: string) =>
    adminFetch(`/admin/variants/${variantId}/assign-barcode`, {
      method: "POST",
      body: JSON.stringify({ barcode: barcode ?? null }),
    }),
  clearVariantBarcode: (variantId: number) =>
    adminFetch(`/admin/variants/${variantId}/barcode`, { method: "DELETE" }),
  getVariantLabel: (variantId: number) => adminFetch(`/admin/variants/${variantId}/label`),

  // Users, roles & permissions
  listRoles: () => adminFetch("/admin/roles"),
  listUsers: () => adminFetch("/admin/users"),
  createUser: (payload: { email: string; full_name: string; phone?: string | null; role_id: number; password: string }) =>
    adminFetch("/admin/users", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (userId: number, payload: { full_name?: string; phone?: string | null; role_id?: number; is_active?: boolean }) =>
    adminFetch(`/admin/users/${userId}`, { method: "PUT", body: JSON.stringify(payload) }),
  resetUserPassword: (userId: number, new_password: string) =>
    adminFetch(`/admin/users/${userId}/reset-password`, { method: "POST", body: JSON.stringify({ new_password }) }),

  // Devices & hardware management
  listDevices: () => adminFetch("/admin/devices"),
  createDevice: (payload: unknown) =>
    adminFetch("/admin/devices", { method: "POST", body: JSON.stringify(payload) }),
  updateDevice: (deviceId: number, payload: unknown) =>
    adminFetch(`/admin/devices/${deviceId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDevice: (deviceId: number) =>
    adminFetch(`/admin/devices/${deviceId}`, { method: "DELETE" }),
  setDefaultDevice: (deviceId: number) =>
    adminFetch(`/admin/devices/${deviceId}/set-default`, { method: "POST" }),
  testDevice: (deviceId: number, payload?: { success?: boolean; error?: string; capabilities?: string[] }) =>
    adminFetch(`/admin/devices/${deviceId}/test`, { method: "POST", body: JSON.stringify(payload || {}) }),
};
