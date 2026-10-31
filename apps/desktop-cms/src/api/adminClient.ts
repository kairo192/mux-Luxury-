// ============================================================================
// TAURI 2 DESKTOP CMS — AUTHENTICATED HTTPS API CLIENT
// The Desktop CMS NEVER connects directly to PostgreSQL.
// It authenticates via /api/v1/admin/auth/login and controls the entire website
// through /api/v1/admin/* endpoints.
// ============================================================================

let accessToken: string | null = null;
let apiBaseUrl: string = import.meta.env.VITE_CMS_API_URL || "https://api.musluxury.dz/api/v1";

export function configureApiBaseUrl(url: string) {
  apiBaseUrl = url.replace(/\/+$/, "");
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

async function adminFetch(path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  const res = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  if (res.status === 401) {
    accessToken = null;
    throw new Error("SESSION_EXPIRED");
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Erreur API CMS");
  }
  return data;
}

export const DesktopCmsApi = {
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
  getDashboard: () => adminFetch("/admin/dashboard"),
  getStoreLayout: () => adminFetch("/store/layout"),
  createCategory: (payload: unknown) =>
    adminFetch("/admin/categories", { method: "POST", body: JSON.stringify(payload) }),
  addCategoryAttribute: (payload: unknown) =>
    adminFetch("/admin/category-attributes", { method: "POST", body: JSON.stringify(payload) }),
  deleteCategoryAttribute: (attrId: number, forceMigrate = false) =>
    adminFetch(`/admin/category-attributes/${attrId}?force_migrate=${forceMigrate}`, { method: "DELETE" }),
  createProduct: (payload: unknown) =>
    adminFetch("/admin/products", { method: "POST", body: JSON.stringify(payload) }),
  generateVariants: (productId: number, payload: unknown) =>
    adminFetch(`/admin/products/${productId}/generate-variants`, { method: "POST", body: JSON.stringify(payload) }),
  listOrders: (status?: string) =>
    adminFetch(`/admin/orders${status ? `?status=${status}` : ""}`),
  updateOrderStatus: (orderId: number, status: string, internal_notes?: string) =>
    adminFetch(`/admin/orders/${orderId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, internal_notes }),
    }),
  updateHomepageSection: (sectionKey: string, payload: unknown) =>
    adminFetch(`/admin/homepage-sections/${sectionKey}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  createBanner: (payload: unknown) =>
    adminFetch("/admin/banners", { method: "POST", body: JSON.stringify(payload) }),
  updateStoreSettings: (settings: Record<string, unknown>) =>
    adminFetch("/admin/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    }),
  triggerBackup: () => adminFetch("/admin/backups", { method: "POST" }),
};
