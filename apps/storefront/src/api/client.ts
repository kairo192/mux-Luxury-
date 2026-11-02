const API_BASE =
  (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_BASE_URL) || "/api/v1";

async function publicFetch(path: string, options: RequestInit = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options.signal || controller.signal,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `HTTP error ${res.status}`);
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export function fetchStoreLayout() {
  return publicFetch("/store/layout");
}

export function fetchCategories() {
  return publicFetch("/categories");
}

export function fetchCategoryBySlug(slug: string) {
  return publicFetch(`/categories/${encodeURIComponent(slug)}`);
}

export function fetchProducts(params: Record<string, string | number | boolean> = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  });
  return publicFetch(`/products?${qs.toString()}`);
}

export function fetchProductBySlug(slug: string) {
  return publicFetch(`/products/${encodeURIComponent(slug)}`);
}

export function fetchDeliveryZones() {
  return publicFetch("/delivery-zones");
}

export function calculateDeliveryTotal(
  wilaya_code: string,
  delivery_method: "home" | "stop_desk",
  subtotal_dzd: number,
  coupon_code?: string
) {
  const qs = new URLSearchParams({
    wilaya_code,
    delivery_method,
    subtotal_dzd: String(subtotal_dzd),
  });
  if (coupon_code) qs.set("coupon_code", coupon_code);
  return publicFetch(`/delivery-zones/calculate?${qs.toString()}`);
}

export function validateCouponCode(code: string, subtotal_dzd: number) {
  return publicFetch("/coupons/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, subtotal_dzd }),
  });
}

export function submitGuestOrder(payload: unknown, idempotencyKey?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  return publicFetch("/orders", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
}

export function trackGuestOrder(reference: string, phone: string) {
  const qs = new URLSearchParams({ reference, phone });
  return publicFetch(`/orders/track?${qs.toString()}`);
}

export function fetchStaticPage(slug: string) {
  return publicFetch(`/pages/${encodeURIComponent(slug)}`);
}
