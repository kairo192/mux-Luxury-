const API_BASE =
  (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_BASE_URL) || "/api/v1";

function formatPublicStorefrontError(data: any, status: number): string {
  if (status === 422 || Array.isArray(data?.detail)) {
    return "Veuillez vérifier les informations saisies (nom complet, numéro de téléphone algérien 05/06/07, Wilaya et adresse).";
  }
  const raw = typeof data?.detail === "string" ? data.detail : "";
  if (status === 403 && raw.includes("Anti-Retour")) {
    return raw;
  }
  if (status === 409) {
    if (raw.toLowerCase().includes("stock")) {
      return "La quantité demandée dépasse le stock actuellement disponible pour cet article.";
    }
    return "Cette commande vient déjà d'être enregistrée. Vérifiez son statut dans le suivi de commande.";
  }
  if (status === 429) {
    return "Trop de tentatives rapprochées. Veuillez patienter quelques secondes avant de réessayer.";
  }
  if (status === 404) {
    return "Aucun résultat trouvé pour cette référence ou cet article.";
  }
  if (status >= 500 || !raw || /sqlite|postgres|traceback|internal|exception/i.test(raw)) {
    return "Le service est momentanément indisponible. Veuillez réessayer dans un instant ou commander via WhatsApp au 0655 53 41 54.";
  }
  return raw;
}

async function publicFetch(path: string, options: RequestInit = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options.signal || controller.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatPublicStorefrontError(data, res.status));
    }
    return data;
  } catch (err: any) {
    if (err?.name === "AbortError" || /failed to fetch|networkerror/i.test(String(err?.message))) {
      throw new Error("Connexion interrompue avec la boutique Mus Luxury. Vérifiez votre connexion Internet.");
    }
    throw err;
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
