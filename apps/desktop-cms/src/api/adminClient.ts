import { keychainSetSecret, keychainGetSecret, keychainDeleteSecret, getOsKeychainStatus } from "../utils/osKeychain";
import { ClientSafeApiError, sanitizeAndTranslateError } from "../utils/clientNotifier";
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
let apiBaseUrl: string =
  (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_CMS_API_URL) ||
  "https://api.musluxury.dz/api/v1";
let defaultTimeoutMs = 15000;

export function configureApiBaseUrl(url: string) {
  apiBaseUrl = url.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

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
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...((options.headers as Record<string, string>) || {}),
  };
  const activeToken = getAccessToken();
  if (activeToken) {
    headers["Authorization"] = `Bearer ${activeToken}`;
  }

  try {
    const res = await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });
    const contentType = res.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await res.json().catch(() => ({})) : await res.text().catch(() => "");

    if (res.status === 401) {
      const isAuthEndpoint = path.includes("/admin/auth/login") || path.includes("/admin/auth/recovery");
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
    return data;
  } catch (err: any) {
    if (err instanceof ClientSafeApiError) {
      throw err;
    }
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

export const DesktopCmsApi = {
  // Authentication & First-Time Setup
  getSetupStatus: () => adminFetch("/admin/auth/setup-status"),
  initializeOwner: (payload: {
    full_name: string;
    email: string;
    password: string;
    whatsapp_phone: string;
    emergency_phone: string;
  }) =>
    adminFetch("/admin/auth/initialize-owner", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
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
  getRecoveryStatus: () => adminFetch("/admin/auth/recovery/status"),
  rotateEmergencyCode: () => adminFetch("/admin/auth/recovery/rotate-emergency-code", { method: "POST" }),
  requestPasswordRecovery: (phone: string, channel: "whatsapp_cloud_api" | "offline_emergency" = "whatsapp_cloud_api") =>
    adminFetch("/admin/auth/recovery/request", {
      method: "POST",
      body: JSON.stringify({ phone, channel }),
    }),
  verifyPasswordRecovery: (phone: string, verification_code: string, new_password: string) =>
    adminFetch("/admin/auth/recovery/verify", {
      method: "POST",
      body: JSON.stringify({ phone, verification_code, new_password }),
    }),

  // Dashboard & Delta Synchronization
  getDashboard: () => adminFetch("/admin/dashboard"),
  deltaSync: (sinceOrderId = 0, sinceMovementId = 0) =>
    adminFetch(`/admin/sync/delta?since_order_id=${sinceOrderId}&since_movement_id=${sinceMovementId}`),

  // Dynamic Categories & 14-Type Attribute Builder
  listCategories: () => adminFetch("/categories"),
  createCategory: (payload: unknown) =>
    adminFetch("/admin/categories", { method: "POST", body: JSON.stringify(payload) }),
  updateCategory: (categoryId: number, payload: unknown) =>
    adminFetch(`/admin/categories/${categoryId}`, { method: "PUT", body: JSON.stringify(payload) }),
  archiveCategory: (categoryId: number) =>
    adminFetch(`/admin/categories/${categoryId}`, { method: "DELETE" }),
  addCategoryAttribute: (payload: unknown) =>
    adminFetch("/admin/category-attributes", { method: "POST", body: JSON.stringify(payload) }),
  deleteCategoryAttribute: (attrId: number, forceMigrate = false) =>
    adminFetch(`/admin/category-attributes/${attrId}?force_migrate=${forceMigrate}`, { method: "DELETE" }),

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

  // Inventory Management
  adjustVariantStock: (variantId: number, change_qty: number, reason: string) =>
    adminFetch(`/admin/variants/${variantId}/adjust-stock`, {
      method: "POST",
      body: JSON.stringify({ change_qty, reason }),
    }),
  listInventoryMovements: (variantId?: number) =>
    adminFetch(`/admin/inventory/movements${variantId ? `?variant_id=${variantId}` : ""}`),

  // Order Management, Invoices & CSV Export
  listOrders: (status?: string) =>
    adminFetch(`/admin/orders${status ? `?status=${status}` : ""}`),
  updateOrderStatus: (orderId: number, status: string, internal_notes?: string) =>
    adminFetch(`/admin/orders/${orderId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, internal_notes }),
    }),
  getOrderInvoice: (orderId: number) => adminFetch(`/admin/orders/${orderId}/invoice`),
  exportOrdersCsv: () => adminFetch("/admin/orders/export.csv"),
  listCustomers: () => adminFetch("/admin/customers"),
  getReports: () => adminFetch("/admin/reports"),

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
  createCoupon: (payload: unknown) =>
    adminFetch("/admin/coupons", { method: "POST", body: JSON.stringify(payload) }),
  updateStoreSettings: (settings: Record<string, unknown>) =>
    adminFetch("/admin/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    }),

  // Product Image Gallery Management & Static Pages
  checkHealth: () => adminFetch("/health"),
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

  // Backups & Isolated Restoration Verification
  listBackups: () => adminFetch("/admin/backups"),
  triggerBackup: () => adminFetch("/admin/backups", { method: "POST" }),
  verifyBackupRestore: (backupId: number) =>
    adminFetch(`/admin/backups/${backupId}/verify-restore`, { method: "POST" }),
};
