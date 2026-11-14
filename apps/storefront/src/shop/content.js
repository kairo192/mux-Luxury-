// Shop content from the CMS (contacts, opening hours, banners, home blocks), page meta tags.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// SHOP CONTENT FROM THE CMS (CMS → Contenu & Bannières)
// Defaults below are the shop's real details, used until the CMS values
// load (or if they are left empty).
// =========================================================================
const DEFAULT_CONTACT = {
  phone: "0655 53 41 54",
  wa: "213655534154",
  instagram: "https://www.instagram.com/musluxury09",
  tiktok: "https://www.tiktok.com/@musluxury.092",
};

function setting(key) {
  const v = state.storeSettings ? state.storeSettings[key] : "";
  return v === null || v === undefined ? "" : decodeHtml(String(v)).trim();
}

function storePhoneDisplay() {
  return setting("store_phone") || DEFAULT_CONTACT.phone;
}

function waNumber() {
  const digits = (setting("whatsapp_contact_number") || setting("store_phone")).replace(/\D/g, "");
  if (!digits) return DEFAULT_CONTACT.wa;
  return digits.startsWith("0") ? "213" + digits.slice(1) : digits;
}

function safeHttpUrl(url) {
  return /^https:\/\/[^\s"'<>]+$/i.test(url || "") ? url : "";
}

// Free delivery from this cart subtotal (0 = no free delivery). The SAME
// rule is enforced by the server when the order is created.
function freeDeliveryThreshold() {
  const n = parseInt(setting("free_delivery_threshold_dzd").replace(/\s/g, ""), 10);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function methodAvailable(wObj, method) {
  if (!wObj) return false;
  const ok = method === "stop_desk" ? wObj.desk_ok : wObj.home_ok;
  return ok !== false; // undefined until the server's list has loaded
}

// True once the server's prices for this wilaya are known.
function feesKnown(wObj) {
  return Boolean(wObj) && wObj.home_ok !== undefined;
}

// 0 while the prices are unknown: the server computes the real fee when
// the order is created and the confirmation shows the server's totals.
function deliveryFeeFor(wObj, method, subtotal) {
  if (!feesKnown(wObj)) return 0;
  const base = Number(method === "stop_desk" ? wObj.desk_fee : wObj.home_fee) || 0;
  const threshold = freeDeliveryThreshold();
  return threshold && subtotal >= threshold ? 0 : base;
}

// Price label for one delivery method: the price, "Indisponible", or
// "Tarif en cours…" while the server's list has not loaded yet.
function deliveryFeeText(wObj, method, subtotal = 0, prefix = "") {
  if (!feesKnown(wObj)) return L("Tarif en cours…", "جارٍ تحميل السعر…", "Loading price…");
  if (!methodAvailable(wObj, method)) return L("Indisponible", "غير متوفر", "Unavailable");
  const fee = deliveryFeeFor(wObj, method, subtotal);
  return fee === 0 ? L("Offerte", "مجاني", "Free") : ltr(prefix + formatDZD(fee));
}

// "Jour (note) : horaires", one line per day (CMS → Paramètres boutique).
// Without the setting the hours written in the page stay.
function applyOpeningHours() {
  const box = document.getElementById("store-hours-list");
  const lines = setting("opening_hours").split("\n").map((l) => l.trim()).filter((l) => l.includes(":"));
  if (!box || !lines.length) return;
  box.innerHTML = lines.map((line) => {
    const cut = line.indexOf(":");
    const head = line.slice(0, cut).trim();
    const hours = line.slice(cut + 1).trim();
    const m = head.match(/^([^(]*)\((.*)\)\s*$/);
    const day = m ? m[1].trim() : head;
    const note = m ? m[2].trim() : "";
    const special = Boolean(note) || /ferm/i.test(hours);
    return special
      ? `<div class="flex items-center justify-between py-1.5 bg-amber-50/60 px-2 rounded-lg border border-amber-200/60">
          <div class="flex items-center gap-1.5"><span class="font-bold text-amber-900">${escapeHtml(day)}</span>${note ? `<span class="text-[10px] text-amber-700 font-medium">(${escapeHtml(note)})</span>` : ""}</div>
          <span class="font-mono font-bold text-amber-900 bg-amber-100 px-2.5 py-0.5 rounded-lg border border-amber-300">${escapeHtml(hours)}</span>
        </div>`
      : `<div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
          <span class="font-semibold text-charcoal">${escapeHtml(day)}</span>
          <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">${escapeHtml(hours)}</span>
        </div>`;
  }).join("");
}

let shownPhone = DEFAULT_CONTACT.phone;
function applyStoreContacts() {
  const phone = storePhoneDisplay();
  const wa = waNumber();
  const ig = safeHttpUrl(setting("instagram_url"));
  const tk = safeHttpUrl(setting("tiktok_url"));
  document.querySelectorAll('a[href*="wa.me/"]').forEach((a) => {
    a.setAttribute("href", a.getAttribute("href").replace(/wa\.me\/\d+/, "wa.me/" + wa));
  });
  document.querySelectorAll('a[href^="tel:"]').forEach((a) => a.setAttribute("href", "tel:" + phone.replace(/\s/g, "")));
  if (ig) document.querySelectorAll('a[href*="instagram.com/"]').forEach((a) => a.setAttribute("href", ig));
  if (tk) document.querySelectorAll('a[href*="tiktok.com/"]').forEach((a) => a.setAttribute("href", tk));
  const maps = safeHttpUrl(setting("store_maps_url"));
  // Marked on first pass: a short link (maps.app.goo.gl) no longer contains "google.com/maps".
  document.querySelectorAll('a[href*="google.com/maps"]').forEach((a) => a.setAttribute("data-maps-link", ""));
  if (maps) document.querySelectorAll("a[data-maps-link]").forEach((a) => a.setAttribute("href", maps));
  if (phone !== shownPhone) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const n = walker.currentNode;
      if (n.nodeValue && n.nodeValue.includes(shownPhone) && !/SCRIPT|STYLE|TEXTAREA/.test(n.parentNode.nodeName)) nodes.push(n);
    }
    nodes.forEach((n) => { n.nodeValue = n.nodeValue.split(shownPhone).join(phone); });
    shownPhone = phone;
  }
}

function bannerText(b, field) {
  const l = state.lang;
  return (l !== "fr" && b[`${field}_${l}`]) || b[`${field}_fr`] || "";
}

function activeBanners(position) {
  return ((state.homeLayout && state.homeLayout.banners) || []).filter((b) => b.position === position && Number(b.is_active) !== 0);
}

// Home blocks the owner can switch off (CMS → Contenu → Blocs de la page d'accueil).
function sectionVisible(key) {
  const secs = (state.homeLayout && state.homeLayout.sections) || [];
  const sec = secs.find((x) => x.section_key === key);
  return sec ? Number(sec.is_active) !== 0 : true;
}

// Where a banner button leads: /categorie/x, /produit/x, #/…, or https://…
function openBannerLink(rawLink) {
  const link = decodeHtml(rawLink || "").trim();
  if (!link) return navigateTo("#/boutique");
  if (/^https:\/\//i.test(link)) return window.open(link, "_blank", "noopener,noreferrer");
  const cat = link.match(/^\/categorie\/([a-z0-9-]+)\/?$/);
  if (cat) return navigateTo("#/category/" + cat[1]);
  const prod = link.match(/^\/produit\/([a-z0-9-]+)\/?$/);
  if (prod) {
    history.pushState(null, "", "/produit/" + prod[1]);
    return handleRoute();
  }
  if (link.startsWith("#/")) return navigateTo(link);
  return navigateTo("#/boutique");
}

function openHeroSecondary() {
  const first = state.categories[0];
  navigateTo(first ? "#/category/" + first.slug : "#/boutique");
}

function renderHero() {
  const hero = document.getElementById("home-hero");
  if (!hero) return;
  hero.classList.toggle("hidden", !sectionVisible("hero_banner"));
  const t = I18N[state.lang] || I18N.fr;
  const list = activeBanners("hero");
  const img = document.getElementById("hero-image");
  const title1 = document.getElementById("hero-title-1");
  const title2 = document.getElementById("hero-title-2");
  const desc = document.getElementById("hero-desc");
  const cta1 = document.getElementById("hero-cta-primary");
  const cta2 = document.getElementById("hero-cta-secondary");
  const caption = document.getElementById("hero-caption-collection");
  const dots = document.getElementById("hero-dots");
  const ctaBtn = cta1 ? cta1.closest("button") : null;
  if (!list.length) {
    // Brand text (translated) and photo when no CMS banner exists.
    title1.textContent = t.heroTitle1; title2.textContent = t.heroTitle2; title2.classList.remove("hidden");
    desc.textContent = t.heroDesc; cta1.textContent = t.heroCta1;
    if (caption) caption.textContent = t.heroCaptionCollection;
    if (img && img.getAttribute("src") !== img.dataset.defaultSrc) img.setAttribute("src", img.dataset.defaultSrc);
    if (ctaBtn) ctaBtn.onclick = () => navigateTo("#/boutique");
    const first = state.categories[0];
    if (cta2) {
      cta2.classList.toggle("hidden", !first);
      if (first) cta2.textContent = decodeHtml(catName(first));
    }
    if (dots) dots.classList.add("hidden");
    return;
  }
  const idx = (state.heroIndex || 0) % list.length;
  const b = list[idx];
  title1.textContent = decodeHtml(bannerText(b, "title"));
  title2.textContent = ""; title2.classList.add("hidden");
  desc.textContent = decodeHtml(bannerText(b, "subtitle"));
  cta1.textContent = state.lang === "fr" && b.cta_text_fr ? decodeHtml(b.cta_text_fr) : t.heroCta1;
  if (ctaBtn) ctaBtn.onclick = () => openBannerLink(b.cta_link);
  if (caption) caption.textContent = decodeHtml(bannerText(b, "title"));
  if (img) img.setAttribute("src", decodeHtml(b.image_url) || PLACEHOLDER_IMG);
  if (cta2) cta2.classList.add("hidden");
  if (dots) {
    dots.classList.toggle("hidden", list.length < 2);
    dots.innerHTML = list.map((_, i) => `<button type="button" onclick="state.heroIndex=${i};renderHero()" aria-label="Bannière ${i + 1}" class="w-2.5 h-2.5 rounded-full ${i === idx ? "bg-gold-reflective" : "bg-white/50"}"></button>`).join("");
  }
}

function renderPromos() {
  const box = document.getElementById("home-promos");
  if (!box) return;
  const list = activeBanners("promo_grid");
  const show = list.length > 0 && sectionVisible("promo_banners");
  box.classList.toggle("hidden", !show);
  if (!show) { box.innerHTML = ""; return; }
  const t = I18N[state.lang] || I18N.fr;
  box.innerHTML = list.map((b, i) => `
    <div onclick="openBannerLink(activeBanners('promo_grid')[${i}].cta_link)" class="group cursor-pointer rounded-2xl overflow-hidden hero-luxury-bg p-5 text-white border border-gold-reflective/35 flex items-center justify-between gap-4 shadow-luxury hover:shadow-luxury-hover transition">
      <div class="space-y-1.5 min-w-0">
        <h3 class="font-luxury text-2xl font-bold text-gold-light">${bannerText(b, "title")}</h3>
        ${bannerText(b, "subtitle") ? `<p class="text-xs text-white/75">${bannerText(b, "subtitle")}</p>` : ""}
        <span class="inline-flex items-center gap-1.5 pt-2 text-xs font-bold text-gold-reflective group-hover:translate-x-1 transition">
          <span>${state.lang === "fr" && b.cta_text_fr ? b.cta_text_fr : (t.viewCollection || "Voir la collection")}</span>
        </span>
      </div>
      ${b.image_url ? `<img src="${b.image_url}" alt="" loading="lazy" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/40 group-hover:scale-105 transition duration-300" />` : ""}
    </div>`).join("");
}

function renderFooterCollections() {
  const ul = document.getElementById("footer-collections");
  if (!ul) return;
  ul.innerHTML = state.categories.slice(0, 6).map((c) =>
    `<li><button type="button" onclick="navigateTo('#/category/${c.slug}')" class="hover:text-white transition">${catName(c)}</button></li>`
  ).join("");
}

// Home blocks + banners; called at the end of every renderStorefront().
function renderHomeContent() {
  renderFooterCollections();
  renderHero();
  renderPromos();
  const trust = document.getElementById("home-trust");
  if (trust) trust.classList.toggle("hidden", !sectionVisible("trust_bar"));
  const cats = document.getElementById("home-categories");
  if (cats) cats.classList.toggle("hidden", !sectionVisible("categories_grid") || !state.categories.length);
  const catalog = document.getElementById("catalog-section");
  // On the home page the product list follows the CMS switch both ways.
  if (catalog && currentRouteHash() === "#/home") catalog.classList.toggle("hidden", !sectionVisible("featured_products"));
  updatePriceFilterRange();
}

// Price filter covers the real price range of the catalog (it used to stop
// at 25 000 DA, which hid every more expensive product).
function catalogMaxPrice() {
  const max = state.products.reduce((m, p) => Math.max(m, Number(p.selling_price_dzd) || 0), 0);
  return Math.max(1000, Math.ceil(max / 500) * 500);
}
function updatePriceFilterRange() {
  const max = catalogMaxPrice();
  const input = document.getElementById("filter-max-price");
  if (!input) return;
  const wasAtMax = state.maxPriceFilter === null || state.maxPriceFilter >= Number(input.max || 0);
  input.max = String(max);
  input.min = "0";
  if (wasAtMax) {
    state.maxPriceFilter = null; // null = no price limit
    input.value = String(max);
    const disp = document.getElementById("filter-price-display");
    if (disp) disp.textContent = formatDZD(max);
  }
  const maxLabel = document.getElementById("filter-price-max-label");
  if (maxLabel) maxLabel.textContent = formatDZD(max);
}

// Shown when a product or category has no photo yet (never a photo of
// another product).
const PLACEHOLDER_IMG = "/assets/placeholder_product.svg";

// Real colour dots for a product card: the colours its variants exist in.
function productSwatches(p) {
  const seen = [];
  (p.variants || []).forEach((v) => {
    Object.values(v.attrs || {}).forEach((val) => {
      const hex = safeHex(COLOR_SWATCH_HEX[val]);
      if (hex && !seen.includes(hex)) seen.push(hex);
    });
  });
  return seen.slice(0, 6);
}

function openStoreMessageBox(title, message, type = "info") {
  const modal = document.getElementById("store-message-box-modal");
  const header = document.getElementById("store-msgbox-header");
  const badge = document.getElementById("store-msgbox-badge");
  const titleEl = document.getElementById("store-msgbox-title");
  const bodyEl = document.getElementById("store-msgbox-body");
  if (!modal || !titleEl || !bodyEl) return;
  if (header && badge) {
    if (type === "error") {
      header.className = "bg-red-900 text-white px-5 py-3.5 flex items-center justify-between border-b border-red-400/40";
      badge.textContent = "Vérification requise — Maison Mus Luxury";
    } else {
      header.className = "bg-emerald-deep text-white px-5 py-3.5 flex items-center justify-between border-b border-gold-reflective/30";
      badge.textContent = "Maison Mus Luxury — Conciergerie Officielle";
    }
  }
  titleEl.textContent = title;
  bodyEl.textContent = message;
  modal.classList.remove("hidden");
}

function closeStoreMessageBox() {
  const modal = document.getElementById("store-message-box-modal");
  if (modal) modal.classList.add("hidden");
}

function openWhatsAppCartConcierge() {
  if (!state.cart || state.cart.length === 0) {
    showToast("Votre panier est vide", "error");
    return;
  }
  const wObj = WILAYAS.find((w) => w.code === state.checkoutWilaya) || WILAYAS[15] || WILAYAS[0];
  const subtotal = computeCartSubtotal();
  const fee = deliveryFeeFor(wObj, state.checkoutMethod, subtotal);
  const discount = computeCouponDiscount(subtotal);
  const total = subtotal - discount + fee;
  const lines = state.cart.map((item) => {
    const prod = state.products.find((p) => p.id === item.productId);
    const variant = prod ? prod.variants.find((v) => v.id === item.variantId) : null;
    return `• ${item.quantity}x ${prod ? prodName(prod) : "Article"} (${variant ? variant.title : "Standard"})`;
  });
  const text = [
    "Bonjour Mus Luxury (Ouled Yaïch), je souhaite commander :",
    ...lines,
    `Wilaya : ${wObj.code} - ${wObj.name_fr} (${state.checkoutMethod === "stop_desk" ? "Stop-Desk" : "Livraison à Domicile"})`,
    feesKnown(wObj)
      ? `Total avec livraison : ${formatDZD(total)} (Paiement à la livraison)`
      : `Total articles : ${formatDZD(total)} + livraison (Paiement à la livraison)`,
  ].join("\n");
  window.open(`https://wa.me/${waNumber()}?text=${encodeURIComponent(decodeHtml(text))}`, "_blank", "noopener,noreferrer");
}

function showToast(msg, type = "success", showModalOnErr = false) {
  // Catalog names arrive pre-escaped: decode once, escape once below.
  msg = decodeHtml(msg);
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  const bg = type === "error" ? "bg-red-800 border-red-400" : "bg-emerald-deep border-gold-reflective";
  el.className = `pointer-events-auto px-4 py-3 rounded-xl text-white text-xs font-semibold shadow-luxury-hover border ${bg} flex items-center gap-2.5 transition-all`;
  const iconSvg = type === "error"
    ? `<svg class="w-4 h-4 text-red-200 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`
    : `<svg class="w-4 h-4 text-gold-reflective flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
  el.innerHTML = `${iconSvg}<span>${escapeHtml(msg)}</span>`;
  container.appendChild(el);
  if (type === "error" && showModalOnErr) {
    openStoreMessageBox("Information sur votre commande", String(msg), "error");
  }
  setTimeout(() => {
    el.remove();
  }, 3600);
}

function toggleMobileSearch() {
  const bar = document.getElementById("mobile-search-bar");
  if (bar) {
    bar.classList.toggle("hidden");
    if (!bar.classList.contains("hidden")) {
      document.getElementById("mobile-search-input")?.focus();
    }
  }
}

function toggleMobileFilters() {
  const sb = document.getElementById("catalog-filters-sidebar");
  if (sb) {
    sb.classList.toggle("mobile-drawer-open");
    sb.classList.toggle("hidden");
  }
}

function setLanguage(lang) {
  if (!["fr", "ar", "en"].includes(lang)) lang = "fr";
  state.lang = lang;
  // Remember the customer's language for the next visit / shared links.
  try { localStorage.setItem("luxe_store_lang", lang); } catch (_e) {}
  const root = document.getElementById("html-root");
  root.setAttribute("lang", lang);
  root.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");

  ["fr", "ar", "en"].forEach((l) => {
    const b = document.getElementById(`lang-${l}`);
    if (l === lang) {
      b.className = "px-2 py-0.5 rounded-full font-semibold bg-gold-reflective text-emerald-forest transition";
    } else {
      b.className = "px-2 py-0.5 rounded-full font-semibold text-gold-light hover:text-white transition";
    }
  });

  const t = I18N[lang];
  document.getElementById("lbl-top-promo").textContent = t.topPromo;
  document.getElementById("lbl-track-top").textContent = t.trackTop;
  document.getElementById("store-search-input").placeholder = t.searchPlaceholder;
  document.getElementById("lbl-header-cart").textContent = t.cart;
  document.getElementById("hero-badge").textContent = t.heroBadge;
  document.getElementById("hero-title-1").textContent = t.heroTitle1;
  document.getElementById("hero-title-2").textContent = t.heroTitle2;
  document.getElementById("hero-desc").textContent = t.heroDesc;
  document.getElementById("hero-cta-primary").textContent = t.heroCta1;
  document.getElementById("hero-cta-secondary").textContent = t.heroCta2;
  document.querySelectorAll(".lbl-tariffs").forEach((el) => { el.textContent = t.tariffs; });
  document.getElementById("hero-caption-collection").textContent = t.heroCaptionCollection;
  document.getElementById("hero-caption-cod").textContent = t.heroCaptionCod;
  document.getElementById("sec-categories-title").textContent = t.categoriesTitle;
  document.getElementById("lbl-filters-heading").textContent = t.filtersHeading;
  document.getElementById("lbl-reset-filters").textContent = t.resetFilters;
  document.getElementById("lbl-price-max").textContent = t.priceMax;
  document.getElementById("lbl-instock-only").textContent = t.inStockOnly;
  // Fixed texts of the page marked data-t-ar / data-t-en (footer…); the
  // French original is kept in data-t-fr to switch back.
  document.querySelectorAll("[data-t-ar]").forEach((el) => {
    if (el.dataset.tFr === undefined) el.dataset.tFr = el.innerHTML;
    el.innerHTML = lang === "ar" ? el.dataset.tAr : lang === "en" ? (el.dataset.tEn || el.dataset.tFr) : el.dataset.tFr;
  });

  renderStorefront();
  if (typeof isProductModalOpen === "function" && isProductModalOpen()) renderPdpModalContent();
}

// =========================================================================

Object.assign(window, {
  DEFAULT_CONTACT,
  setting,
  storePhoneDisplay,
  waNumber,
  safeHttpUrl,
  freeDeliveryThreshold,
  methodAvailable,
  feesKnown,
  deliveryFeeFor,
  deliveryFeeText,
  applyOpeningHours,
  applyStoreContacts,
  bannerText,
  activeBanners,
  sectionVisible,
  openBannerLink,
  openHeroSecondary,
  renderHero,
  renderPromos,
  renderFooterCollections,
  renderHomeContent,
  catalogMaxPrice,
  updatePriceFilterRange,
  PLACEHOLDER_IMG,
  productSwatches,
  openStoreMessageBox,
  closeStoreMessageBox,
  openWhatsAppCartConcierge,
  showToast,
  toggleMobileSearch,
  toggleMobileFilters,
  setLanguage,
});
