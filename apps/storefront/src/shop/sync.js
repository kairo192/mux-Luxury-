// Keeping the shop in step with the server, and start-up.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// whole catalog is visible (cap: 2 000 products).
async function fetchAllProducts() {
  const all = [];
  for (let page = 1; page <= 40; page++) {
    const res = await fetchPublicJson(`/api/v1/products?page_size=50&page=${page}`);
    const items = res && Array.isArray(res.items) ? res.items : [];
    all.push(...items);
    const total = Number(res && res.total) || 0;
    if (items.length < 50 || (total && all.length >= total)) break;
  }
  return { items: all };
}

let isSyncingBackend = false;
let lastCatJson = "";
let lastProdJson = "";
let lastWilJson = "";
let lastLayoutJson = "";
async function syncStorefrontWithBackend() {
  if (isSyncingBackend) return;
  isSyncingBackend = true;
  try {
    const [catRes, prodRes, wilRes, setRes] = await Promise.all([
      // GETs benefit from the retry/timeout wrapper; keep the per-call
      // fallback to null so one failing endpoint doesn't knock the
      // homepage down.
      fetchPublicJson("/api/v1/categories").catch(() => null),
      fetchAllProducts().catch(() => null),
      fetchPublicJson("/api/v1/delivery-zones").catch(() => null),
      fetchPublicJson("/api/v1/store/layout").catch(() => null),
    ]);
    let dataChanged = false;
    if (catRes && Array.isArray(catRes.items)) {
      const rawCat = JSON.stringify(catRes.items);
      if (rawCat !== lastCatJson) {
        lastCatJson = rawCat;
        dataChanged = true;
      }
      state.categories = escapeDeep(catRes.items).map((c) => ({
        id: c.id,
        slug: c.slug,
        name_fr: c.name_fr,
        name_ar: c.name_ar || c.name_fr,
        name_en: c.name_en || c.name_fr,
        description_fr: c.description_fr || "",
        description_ar: c.description_ar || "",
        description_en: c.description_en || "",
        image: c.image_url || PLACEHOLDER_IMG,
        attributes: (c.attributes || []).map((a) => {
          (a.options || []).forEach((opt) => {
            if (opt.value && safeHex(opt.color_hex)) {
              COLOR_SWATCH_HEX[opt.value] = safeHex(opt.color_hex);
            }
          });
          return {
            key: a.attr_key,
            label_fr: a.label_fr,
            label_ar: a.label_ar || a.label_fr,
            label_en: a.label_en || a.label_fr,
            type: a.input_type,
            variant: Boolean(a.is_variant_axis),
            filterable: Boolean(a.is_filterable),
            options: (a.options || []).map((o) => o.value),
            rawOptions: a.options || [],
          };
        }),
      }));
    }
    const productsArrived = Boolean(prodRes && Array.isArray(prodRes.items));
    if (productsArrived) {
      const rawProd = JSON.stringify(prodRes.items);
      if (rawProd !== lastProdJson) {
        lastProdJson = rawProd;
        dataChanged = true;
      }
      state.products = escapeDeep(prodRes.items).map((p) => {
        const catSlug = (p.category && p.category.slug) || p.category_slug || "";
        const brandName = (p.brand && p.brand.name) || p.brand_name || "MUS LUXURY";
        const mainImg = p.main_image_url || PLACEHOLDER_IMG;
        const gallery = (p.images && p.images.length)
          ? p.images.map((im) => (typeof im === "string" ? im : im.image_url || mainImg))
          : [mainImg];

        return {
          id: p.id,
          slug: p.slug,
          category_id: p.category_id,
          category_slug: catSlug,
          sku: p.sku,
          badge: p.is_new_arrival ? "Nouveau" : p.is_featured ? "Populaire" : (p.discount_percent > 0 ? "Promo" : null),
          name_fr: p.name_fr,
          name_ar: p.name_ar || p.name_fr,
          name_en: p.name_en || p.name_fr,
          brand: brandName,
          description_fr: p.description_fr || "",
          description_ar: p.description_ar || "",
          description_en: p.description_en || "",
          image: mainImg,
          gallery: gallery,
          selling_price_dzd: p.selling_price_dzd,
          previous_price_dzd: p.previous_price_dzd,
          discount_percent: p.discount_percent || 0,
          sales_count: p.sales_count || 0,
          attributes: p.attributes || {},
          variants: (p.variants || []).map((v) => ({
            id: v.id,
            sku: v.sku,
            title: v.title,
            stock: v.stock_qty,
            price: v.effective_price_dzd || p.selling_price_dzd,
            attrs: v.attributes || {},
            img: v.image_url || mainImg,
          })),
        };
      });
    }
    if (wilRes && Array.isArray(wilRes.items) && wilRes.items.length > 0) {
      const rawWil = JSON.stringify(wilRes.items);
      if (rawWil !== lastWilJson) {
        lastWilJson = rawWil;
        dataChanged = true;
      }
      WILAYAS.splice(
        0,
        WILAYAS.length,
        ...wilRes.items.map((w) => ({
          code: w.wilaya_code,
          name_fr: w.wilaya_name_fr,
          name_ar: w.wilaya_name_ar || "",
          communes: w.communes && w.communes.length ? w.communes : [w.wilaya_name_fr],
          // A method the shop switched off (CMS → Livraison & Wilayas) or
          // without a price is unavailable — never an invented price.
          home_ok: Boolean(w.rates?.home) && Number(w.rates.home.is_supported ?? 1) !== 0,
          desk_ok: Boolean(w.rates?.stop_desk) && Number(w.rates.stop_desk.is_supported ?? 1) !== 0,
          home_fee: Number(w.rates?.home?.fee_dzd ?? 0),
          desk_fee: Number(w.rates?.stop_desk?.fee_dzd ?? 0),
        }))
      );
    }
    if (setRes && typeof setRes === "object") {
      // /store/layout = shop settings + home banners + home blocks (CMS → Contenu & Bannières).
      const settings = setRes.settings || {};
      const rawLayout = JSON.stringify([settings, setRes.banners || [], setRes.homepage_sections || []]);
      if (rawLayout !== lastLayoutJson) {
        lastLayoutJson = rawLayout;
        dataChanged = true;
        state.storeSettings = escapeDeep(settings);
        state.homeLayout = {
          banners: escapeDeep(setRes.banners || []),
          sections: setRes.homepage_sections || [],
        };
        if (settings.store_phone) {
          const el = document.getElementById("maison-store-phone");
          if (el) el.textContent = settings.store_phone;
        }
        if (settings.store_location) {
          const el = document.getElementById("maison-store-address");
          if (el) el.textContent = settings.store_location;
        }
        applyStoreContacts();
        applyOpeningHours();
      }
    }
    // "Loaded" only once the products really arrived: after a failed first
    // request the shared product link waits for the next successful sync
    // instead of being sent to the shop page.
    if (productsArrived && (dataChanged || !state.isCatalogLoaded)) {
      state.isCatalogLoaded = true;
      renderStorefront();
    } else if (dataChanged) {
      renderStorefront();
    }
    // A shared product link opened before the catalog was loaded.
    if (state.pendingProductSlug && state.isCatalogLoaded) {
      const slug = state.pendingProductSlug;
      state.pendingProductSlug = null;
      openProductBySlug(slug);
    }
  } catch (_e) {
    renderStorefront();
  } finally {
    isSyncingBackend = false;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  try {
    const savedLang = localStorage.getItem("luxe_store_lang");
    if (savedLang && savedLang !== "fr") setLanguage(savedLang);
  } catch (_e) {}
  renderStorefront();
  handleRoute();
  syncStorefrontWithBackend();

  // Background refresh: every 60 s while the page is visible, and when
  // the customer comes back to the tab after 30 s away. (It used to be
  // every 4 s — about one request per second per visitor on a 1-vCPU VPS.)
  let lastSyncAt = Date.now();
  const syncIfStale = (minAgeMs) => {
    if (document.visibilityState !== "visible") return;
    if (Date.now() - lastSyncAt < minAgeMs) return;
    lastSyncAt = Date.now();
    syncStorefrontWithBackend();
  };
  setInterval(() => syncIfStale(55000), 60000);
  setInterval(() => {
    if (document.visibilityState === "visible" && activeBanners("hero").length > 1) {
      state.heroIndex = ((state.heroIndex || 0) + 1) % activeBanners("hero").length;
      renderHero();
    }
  }, 7000);
  document.addEventListener("visibilitychange", () => syncIfStale(30000));
  window.addEventListener("focus", () => syncIfStale(30000));

  // BroadcastChannel & Storage event for instant zero-lag inter-tab updates
  try {
    const syncBc = new BroadcastChannel("luxe_catalog_sync");
    syncBc.onmessage = () => syncStorefrontWithBackend();
  } catch (_e) {}
  window.addEventListener("storage", (e) => {
    if (e.key === "luxe_catalog_sync") syncStorefrontWithBackend();
  });
});

Object.assign(window, {
  fetchAllProducts,
  syncStorefrontWithBackend,
});
