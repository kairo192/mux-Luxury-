// Calls to the API, amounts, languages, escaping of text put into the page.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// HTTP helper — shared by every public endpoint call on this page.
//
// Why this exists: the storefront used to call `fetch()` directly in a
// dozen places, which meant (1) a blipping 502 at a flaky moment showed
// customers a raw backend detail, (2) a 422 validation payload (array of
// dicts) rendered as "[object Object]" in the toast, (3) a slow server
// hung the UI indefinitely. This helper gives every call a timeout,
// retries and a clear French message.
//
// Behaviour:
//   - Timeout per attempt (default 15s) via AbortController.
//   - Retries GETs and POSTs carrying an Idempotency-Key up to 3 attempts
//     on 502/503/504 and transient network errors. Exponential-ish backoff.
//   - Adds X-Request-ID so the backend's structured logs can tie a
//     customer complaint back to a specific request.
//   - Translates backend errors to French customer-facing text, never
//     leaking SQLite / Postgres / traceback keywords.
// Returns the parsed JSON body on success; throws an Error whose message
// is already safe to show in a toast on failure.
async function fetchPublicJson(path, options = {}, timeoutMs = 15000) {
  const method = ((options && options.method) || "GET").toUpperCase();
  const reqId = "sf_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 7);
  const headers = Object.assign(
    { "X-Request-ID": reqId },
    (options && options.headers) || {}
  );
  const canRetry = method === "GET" || Boolean(headers["Idempotency-Key"]);
  const maxAttempts = canRetry ? 3 : 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(path, Object.assign({}, options, {
        headers,
        signal: options.signal || controller.signal,
      }));
      if ([502, 503, 504].includes(res.status) && attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, attempt * 250));
        continue;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatStorefrontError(data, res.status));
      }
      return data;
    } catch (err) {
      const isAbort = err && (err.name === "AbortError" || /abort/i.test(String(err.message || "")));
      const isNet = err && /failed to fetch|networkerror|network request/i.test(String(err.message || ""));
      if ((isAbort || isNet) && attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, attempt * 250));
        continue;
      }
      if (isAbort || isNet) {
        throw new Error(
          "Connexion interrompue avec la boutique Mus Luxury. Vérifiez votre connexion Internet ou commandez sur WhatsApp au " + storePhoneDisplay() + "."
        );
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }
}

function formatStorefrontError(data, status) {
  // Turns a server answer into a message a customer understands.
  if (status === 422 || Array.isArray(data && data.detail)) {
    return L("Veuillez vérifier les informations saisies (nom, numéro de téléphone 05/06/07, Wilaya et adresse).", "يرجى التحقق من المعلومات المدخلة (الاسم، رقم الهاتف 05/06/07، الولاية والعنوان).", "Please check the details you entered (name, 05/06/07 phone number, wilaya and address).");
  }
  const raw = (data && typeof data.detail === "string") ? data.detail : "";
  if (status === 403 && raw && raw.indexOf("Anti-Retour") !== -1) return raw;
  if (status === 409) {
    if (raw && raw.toLowerCase().indexOf("stock") !== -1) {
      return L("La quantité demandée dépasse le stock actuellement disponible pour cet article.", "الكمية المطلوبة تتجاوز المخزون المتوفر حاليًا لهذا المنتج.", "The quantity requested is more than the stock available for this item.");
    }
    const ref = (raw.match(/(?:existing reference:|référence)\s*([A-Za-z0-9-]+)/) || [])[1];
    if (ref) return L(`Cette commande est déjà enregistrée (référence ${ltr(ref)}).`, `هذا الطلب مسجّل من قبل (المرجع ${ltr(ref)}).`, `This order is already recorded (reference ${ltr(ref)}).`);
    return L("Cette commande vient déjà d'être enregistrée. Vérifiez son statut dans le suivi de commande.", "تم تسجيل هذا الطلب للتو. تحقّق من حالته في تتبّع الطلب.", "This order has just been recorded. Check its status in order tracking.");
  }
  if (status === 429) return L("Trop de tentatives rapprochées. Veuillez patienter quelques secondes avant de réessayer.", "محاولات كثيرة متتالية. يرجى الانتظار بضع ثوانٍ ثم إعادة المحاولة.", "Too many attempts. Please wait a few seconds and try again.");
  if (status === 404) return L("Aucun résultat trouvé pour cette référence ou cet article.", "لا توجد نتيجة لهذا الرقم أو لهذا المنتج.", "Nothing found for this reference or item.");
  if (status >= 500 || !raw || /sqlite|postgres|traceback|internal|exception/i.test(raw)) {
    return L("Le service est momentanément indisponible. Veuillez réessayer dans un instant ou commander via WhatsApp au ", "الخدمة غير متاحة مؤقتًا. يرجى إعادة المحاولة بعد قليل أو الطلب عبر واتساب على الرقم ", "The service is briefly unavailable. Please try again in a moment or order on WhatsApp at ") + ltr(storePhoneDisplay()) + ".";
  }
  return raw;
}

function saveCartToStorage() {
  try {
    localStorage.setItem("luxe_store_cart", JSON.stringify(state.cart));
  } catch (_e) {}
}

function saveFavoritesToStorage() {
  try {
    localStorage.setItem("luxe_store_favorites", JSON.stringify([...state.favorites]));
  } catch (_e) {}
}

function formatDZD(amount) {
  const n = Number(amount) || 0;
  if (state.lang !== "ar") return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " DA";
  // Right-to-left (Arabic) reorders "9 500 DA" into "DA 500 9": no-break
  // spaces keep it on one line and ltr() keeps it in reading order.
  return ltr(n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u00A0") + "\u00A0DA");
}

// A left-to-right piece (price, "+ 500 DA", "#LUX-…", phone) inside Arabic
// text: invisible Unicode isolate marks, valid in HTML, plain text and
// WhatsApp messages. Unchanged in French and English.
function ltr(text) {
  return state.lang === "ar" ? "\u2066" + text + "\u2069" : text;
}

// Text in the customer's language (French when no translation is given).
function L(fr, ar, en) {
  return state.lang === "ar" ? (ar || fr) : state.lang === "en" ? (en || fr) : fr;
}
function wilayaName(w) {
  return state.lang === "ar" && w.name_ar ? w.name_ar : w.name_fr;
}

function catName(cat) {
  if (state.lang === "ar") return cat.name_ar || cat.name_fr;
  if (state.lang === "en") return cat.name_en || cat.name_fr;
  return cat.name_fr;
}

function prodName(prod) {
  if (state.lang === "ar") return prod.name_ar || prod.name_fr;
  if (state.lang === "en") return prod.name_en || prod.name_fr;
  return prod.name_fr;
}

// Descriptions in the customer's language (falls back to French).
function prodDesc(prod) {
  if (state.lang === "ar" && prod.description_ar) return prod.description_ar;
  if (state.lang === "en" && prod.description_en) return prod.description_en;
  return prod.description_fr || "";
}

function catDesc(cat) {
  if (state.lang === "ar" && cat.description_ar) return cat.description_ar;
  if (state.lang === "en" && cat.description_en) return cat.description_en;
  return cat.description_fr || "";
}

function attrLabel(attr) {
  if (state.lang === "ar") return attr.label_ar || attr.label_fr;
  if (state.lang === "en") return attr.label_en || attr.label_fr;
  return attr.label_fr;
}

function escapeHtml(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// SECURITY: every string that comes from the server (catalog, settings)
// is HTML-escaped ONCE, when it arrives (syncStorefrontWithBackend). All
// templates can then interpolate catalog data safely, including future
// ones. Use decodeHtml() before textContent / input.value.
function escapeDeep(val) {
  if (typeof val === "string") return escapeHtml(val);
  if (Array.isArray(val)) return val.map(escapeDeep);
  if (val && typeof val === "object") {
    const out = {};
    for (const k of Object.keys(val)) out[k] = escapeDeep(val[k]);
    return out;
  }
  return val;
}

function decodeHtml(val) {
  const t = document.createElement("textarea");
  t.innerHTML = String(val ?? "");
  return t.value;
}

// A value placed inside an inline handler: onclick="fn(${jsArg(v)})".
// JSON-quoted then HTML-escaped, so quotes/apostrophes can never break out.
function jsArg(val) {
  return escapeHtml(JSON.stringify(String(val ?? "")));
}

function safeHex(val) {
  const s = String(val || "").trim();
  return /^#[0-9a-fA-F]{3,8}$/.test(s) ? s : null;
}

// =========================================================================

Object.assign(window, {
  fetchPublicJson,
  formatStorefrontError,
  saveCartToStorage,
  saveFavoritesToStorage,
  formatDZD,
  ltr,
  L,
  wilayaName,
  catName,
  prodName,
  prodDesc,
  catDesc,
  attrLabel,
  escapeHtml,
  escapeDeep,
  decodeHtml,
  jsArg,
  safeHex,
});
