const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export async function fetchStoreLayout() {
  const res = await fetch(`${API_BASE}/store/layout`);
  if (!res.ok) throw new Error("Failed to load store layout");
  return res.json();
}

export async function fetchCategories() {
  const res = await fetch(`${API_BASE}/categories`);
  if (!res.ok) throw new Error("Failed to load categories");
  return res.json();
}

export async function fetchCategoryBySlug(slug: string) {
  const res = await fetch(`${API_BASE}/categories/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error("Category not found");
  return res.json();
}

export async function fetchProducts(params: Record<string, string | number | boolean> = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/products?${qs.toString()}`);
  if (!res.ok) throw new Error("Failed to load products");
  return res.json();
}

export async function fetchProductBySlug(slug: string) {
  const res = await fetch(`${API_BASE}/products/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error("Product not found");
  return res.json();
}

export async function fetchDeliveryZones() {
  const res = await fetch(`${API_BASE}/delivery-zones`);
  if (!res.ok) throw new Error("Failed to load 69 Wilaya delivery zones");
  return res.json();
}

export async function validateCouponCode(code: string, subtotal_dzd: number) {
  const res = await fetch(`${API_BASE}/coupons/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, subtotal_dzd }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Invalid coupon code");
  return data;
}

export async function submitGuestOrder(payload: unknown) {
  const res = await fetch(`${API_BASE}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Order submission failed");
  return data;
}

export async function trackGuestOrder(reference: string, phone: string) {
  const qs = new URLSearchParams({ reference, phone });
  const res = await fetch(`${API_BASE}/orders/track?${qs.toString()}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Order not found");
  return data;
}
