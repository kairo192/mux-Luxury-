// Address router (#/…, /produit/…, /categorie/…), catalogue, search and filters.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// CLIENT-SIDE HASH ROUTER & ACTIVE INDICATOR CONTROLLER
// =========================================================================
// Products and categories have real addresses that Google can index and
// customers can share: /produit/<slug> and /categorie/<slug>. The other
// screens keep their #/ routes. currentRouteHash() maps both forms to one
// internal route so the rest of the router is unchanged.
function currentRouteHash() {
  const h = window.location.hash;
  if (h && h !== "#" && h !== "#/") return h;
  const m = window.location.pathname.match(/^\/(produit|categorie)\/([a-z0-9-]+)\/?$/);
  if (m) return m[1] === "produit" ? `#/produit/${m[2]}` : `#/category/${m[2]}`;
  return "#/home";
}

function currentUrl() {
  return window.location.pathname + window.location.search + window.location.hash;
}

function navigateTo(hash, pushState = true) {
  if (pushState) {
    if (hash.startsWith("#/category/")) {
      const target = "/categorie/" + hash.slice("#/category/".length);
      if (currentUrl() !== target) history.pushState(null, "", target);
      handleRoute();
      return;
    }
    if (window.location.pathname !== "/") {
      history.pushState(null, "", "/" + hash);
      handleRoute();
      return;
    }
    if (window.location.hash !== hash) {
      window.location.hash = hash;
      return; // hashchange listener will fire handleRoute()
    }
  }
  handleRoute();
}

// Page title / description / canonical follow what the customer sees
// (the server already set them for a direct visit; this keeps them right
// while browsing inside the shop).
// Fixed home values: on a /produit or /categorie visit the server has
// already replaced the page's own title/description.
const DEFAULT_PAGE_TITLE = "Mus Luxury — Boutique Officielle Mode, Sacs & Accessoires en Algérie";
const DEFAULT_PAGE_DESC = "Mus Luxury — sacs, chaussures, accessoires et beauté. Livraison dans les 69 wilayas d'Algérie, paiement à la livraison.";
function setPageMeta(title, description, path) {
  document.title = title || DEFAULT_PAGE_TITLE;
  const d = document.querySelector('meta[name="description"]');
  if (d) d.setAttribute("content", description || DEFAULT_PAGE_DESC);
  const c = document.querySelector('link[rel="canonical"]');
  if (c) c.setAttribute("href", window.location.origin + (path || "/"));
}
function applyRouteMeta(hash) {
  if (hash.startsWith("#/category/")) {
    const cat = state.categories.find((c) => c.slug === hash.slice("#/category/".length));
    if (cat) {
      const name = decodeHtml(catName(cat));
      setPageMeta(`${name} — Mus Luxury`, decodeHtml(cat.description_fr || "") || DEFAULT_PAGE_DESC, `/categorie/${cat.slug}`);
      return;
    }
  }
  setPageMeta(null, null, "/");
}

function updateActiveNavIndicators(hash) {
  // 1. Desktop Nav Links
  const desktopLinks = [
    { id: "nav-link-home", match: hash === "#/home" || hash === "#" || hash === "" },
    { id: "nav-link-boutique", match: hash === "#/boutique" },
    { id: "nav-link-collections", match: hash.startsWith("#/category/") },
    { id: "nav-link-maison", match: hash === "#/maison" },
  ];

  desktopLinks.forEach((link) => {
    const el = document.getElementById(link.id);
    if (!el) return;
    if (link.match) {
      el.className = "nav-route-btn text-gold-reflective border-b-2 border-gold-reflective pb-1 font-bold transition-all duration-200 flex items-center gap-1.5";
    } else {
      el.className = "nav-route-btn text-gold-light/90 hover:text-gold-reflective pb-1 font-semibold transition-all duration-200 flex items-center gap-1.5";
    }
  });

  // 2. Mobile Bottom Nav Tabs
  const mobileTabs = [
    { id: "mobile-tab-home", match: hash === "#/home" || hash === "#" || hash === "" },
    { id: "mobile-tab-boutique", match: hash === "#/boutique" || hash.startsWith("#/category/") },
    { id: "mobile-tab-favoris", match: hash === "#/favoris" },
    { id: "mobile-tab-maison", match: hash === "#/maison" },
  ];

  mobileTabs.forEach((tab) => {
    const el = document.getElementById(tab.id);
    if (!el) return;
    if (tab.match) {
      el.classList.add("text-emerald-deep", "font-bold");
      el.classList.remove("text-charcoal/75", "font-semibold");
    } else {
      el.classList.remove("text-emerald-deep", "font-bold");
      el.classList.add("text-charcoal/75", "font-semibold");
    }
  });
}

let lastRoutedUrl = null;
function setLastRoutedUrl(url) {
  lastRoutedUrl = url;
}
function onRouteEvent() {
  // popstate and hashchange can both fire for one navigation: route once.
  if (currentUrl() === lastRoutedUrl) return;
  handleRoute();
}

// Filters such as a shoe size belong to one category: opening another one
// starts with no filter, so nothing stays applied without its control.
function setActiveCategory(slug) {
  if (state.activeCategorySlug !== slug) state.dynamicFilterSelections = {};
  state.activeCategorySlug = slug;
}

function handleRoute() {
  lastRoutedUrl = currentUrl();
  const hash = currentRouteHash();

  if (hash.startsWith("#/produit/")) {
    openProductBySlug(decodeURIComponent(hash.slice("#/produit/".length)).trim());
    return;
  }
  // Leaving a product link that was waiting for the catalog: it must not
  // open later on top of the page chosen since.
  state.pendingProductSlug = null;
  applyRouteMeta(hash);
  if (isProductModalOpen()) {
    hideProductModal();
    state.pdpPushed = false;
    if (state.pdpReturnUrl && currentUrl() === state.pdpReturnUrl) {
      // Back button from a product: stay exactly where the customer was.
      state.pdpReturnUrl = null;
      return;
    }
  }
  const homeSec = document.getElementById("store-home-sections");
  const maisonSec = document.getElementById("store-maison-section");
  const catalogSec = document.getElementById("catalog-section");

  updateActiveNavIndicators(hash);

  if (hash === "#/maison") {
    if (homeSec) homeSec.classList.add("hidden");
    if (catalogSec) catalogSec.classList.add("hidden");
    if (maisonSec) maisonSec.classList.remove("hidden");
    renderLaMaisonPage();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  // Hide Maison if not on #/maison
  if (maisonSec) maisonSec.classList.add("hidden");

  if (hash.startsWith("#/category/")) {
    const slug = hash.replace("#/category/", "").trim();
    setActiveCategory(slug);
    state.onlyFavorites = false;
    if (homeSec) homeSec.classList.add("hidden");
    if (catalogSec) catalogSec.classList.remove("hidden");
    renderStorefront();
    if (catalogSec) catalogSec.scrollIntoView({ behavior: "smooth" });
    return;
  }

  if (hash === "#/favoris") {
    state.onlyFavorites = true;
    if (homeSec) homeSec.classList.add("hidden");
    if (catalogSec) catalogSec.classList.remove("hidden");
    renderStorefront();
    if (catalogSec) catalogSec.scrollIntoView({ behavior: "smooth" });
    return;
  }

  if (hash === "#/boutique") {
    setActiveCategory("all");
    state.onlyFavorites = false;
    if (homeSec) homeSec.classList.add("hidden");
    if (catalogSec) catalogSec.classList.remove("hidden");
    renderStorefront();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  if (hash === "#/suivi") {
    openOrderTrackingModal();
    return;
  }

  if (hash === "#/tarifs") {
    openWilayaTariffsModal();
    return;
  }

  // Default: #/home
  setActiveCategory("all");
  state.onlyFavorites = false;
  if (homeSec) homeSec.classList.remove("hidden");
  if (catalogSec) catalogSec.classList.remove("hidden");
  renderStorefront();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

window.addEventListener("hashchange", onRouteEvent);
window.addEventListener("popstate", onRouteEvent);

function navigateStore(target) {
  if (target === "home") {
    navigateTo("#/home");
  } else if (target === "boutique" || target === "shop") {
    navigateTo("#/boutique");
  } else if (target === "maison") {
    navigateTo("#/maison");
  } else {
    navigateTo("#/home");
  }
}

function filterByCategory(slug) {
  if (slug === "all") {
    navigateTo("#/boutique");
  } else {
    navigateTo("#/category/" + slug);
  }
}

function getAlgeriaCurrentTime() {
  // Algeria is UTC+1 all year (no DST)
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utc + 3600000);
}


function openSignLightbox() {
  const el = document.getElementById("maison-photo-lightbox");
  if (el) el.classList.remove("hidden");
}

function closeSignLightbox() {
  const el = document.getElementById("maison-photo-lightbox");
  if (el) el.classList.add("hidden");
}

function renderLaMaisonPage() {
  const algNow = getAlgeriaCurrentTime();
  const day = algNow.getDay(); // 0 = Sunday, 5 = Friday, 6 = Saturday
  const hour = algNow.getHours();
  const min = algNow.getMinutes();
  const timeNum = hour + min / 60;

  let isOpen = false;
  let closeTimeStr = "";
  let nextOpenStr = "";

  if (day === 5) {
    // Friday: 15h00 - 21h00
    if (timeNum >= 15 && timeNum < 21) {
      isOpen = true;
      closeTimeStr = "21h00";
    } else {
      nextOpenStr = timeNum < 15 ? "aujourd'hui à 15h00" : "demain (samedi) à 10h00";
    }
  } else {
    // Saturday to Thursday: 10h00 - 20h00
    if (timeNum >= 10 && timeNum < 20) {
      isOpen = true;
      closeTimeStr = "20h00";
    } else {
      nextOpenStr = timeNum < 10 ? "aujourd'hui à 10h00" : (day === 4 ? "demain (vendredi) à 15h00" : "demain à 10h00");
    }
  }

  const statusEl = document.getElementById("maison-live-status");
  if (statusEl) {
    if (isOpen) {
      statusEl.className = "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-300";
      statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span><span>Ouvert actuellement (Ferme à ${closeTimeStr})</span>`;
    } else {
      statusEl.className = "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300";
      statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-600"></span><span>Fermé actuellement (Ouvre ${nextOpenStr})</span>`;
    }
  }
}

function copyStoreAddress() {
  // The address set in CMS → Paramètres boutique, else the shop's own.
  const addr = decodeHtml(setting("store_location")) || "FVX6+GCJ Mus luxury, Ouled Yaïch, Blida (Wilaya 09), Algérie";
  navigator.clipboard?.writeText(addr).then(() => {
    showToast("✓ Adresse GPS copiée dans le presse-papier !");
  }).catch(() => {
    showToast("Adresse : " + addr);
  });
}

function renderHeaderCollections() {
  // 1. Header Dropdown List
  const dropdownEl = document.getElementById("header-collections-dropdown-list");
  if (dropdownEl) {
    dropdownEl.innerHTML = state.categories.map((c) => `
      <button type="button" onclick="navigateTo('#/category/${c.slug}')" class="w-full text-left px-3 py-2 rounded-xl hover:bg-emerald-forest transition flex items-center justify-between group">
        <div class="flex items-center gap-2.5">
          <img src="${c.image}" alt="${catName(c)}" class="w-7 h-7 rounded-lg object-cover border border-gold-reflective/30" onerror="this.onerror=null;this.src='${PLACEHOLDER_IMG}'" />
          <span class="text-xs text-white group-hover:text-gold-reflective font-medium transition">${catName(c)}</span>
        </div>
        <svg class="w-3.5 h-3.5 text-gold-reflective/60 group-hover:text-gold-reflective group-hover:translate-x-1 transition" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
      </button>
    `).join("");
  }

  // 2. Catalog Category Quick Filter Pills
  const pillsEl = document.getElementById("catalog-category-pills");
  if (pillsEl) {
    const isAll = state.activeCategorySlug === "all";
    let pillsHtml = `
      <button type="button" onclick="navigateTo('#/boutique')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
        isAll
          ? "bg-emerald-deep text-gold-reflective border border-gold-reflective shadow-sm font-bold"
          : "bg-white/80 hover:bg-white text-charcoal/80 border border-gold-reflective/25 hover:border-gold-reflective"
      }">Toutes les collections</button>
    `;

    state.categories.forEach((c) => {
      const isAct = state.activeCategorySlug === c.slug;
      pillsHtml += `
        <button type="button" onclick="navigateTo('#/category/${c.slug}')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
          isAct
            ? "bg-emerald-deep text-gold-reflective border border-gold-reflective shadow-sm font-bold"
            : "bg-white/80 hover:bg-white text-charcoal/80 border border-gold-reflective/25 hover:border-gold-reflective"
        }">${catName(c)}</button>
      `;
    });
    pillsEl.innerHTML = pillsHtml;
  }

  // 3. Mobile Drawer Categories
  const drawerCatsEl = document.getElementById("mobile-drawer-categories");
  if (drawerCatsEl) {
    drawerCatsEl.innerHTML = state.categories.map((c) => `
      <button type="button" onclick="closeMobileMenu(); navigateTo('#/category/${c.slug}');" class="p-2 rounded-xl bg-emerald-forest/80 hover:bg-emerald-forest border border-gold-reflective/25 text-left transition flex items-center gap-2 group">
        <img src="${c.image}" alt="${catName(c)}" class="w-6 h-6 rounded-md object-cover border border-gold-reflective/30" onerror="this.onerror=null;this.src='${PLACEHOLDER_IMG}'" />
        <span class="text-[11px] text-white group-hover:text-gold-reflective font-medium truncate">${catName(c)}</span>
      </button>
    `).join("");
  }
}

function openMobileMenu() {
  const drawer = document.getElementById("mobile-nav-drawer");
  if (drawer) drawer.classList.remove("hidden");
}

function closeMobileMenu() {
  const drawer = document.getElementById("mobile-nav-drawer");
  if (drawer) drawer.classList.add("hidden");
}

function scrollToCatalog() {
  const el = document.getElementById("catalog-section");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

let searchDebounceTimer = null;
function handleStoreSearch(val) {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    // Compared with pre-escaped catalog names, so escape the query too.
    state.searchQuery = escapeHtml(val.trim()).toLowerCase();
    showCatalogForSearch();
    renderCatalogProducts();
  }, 200);
}

// From a page without the product list (La Maison), a search opens the shop
// so its results are visible; the query is kept.
function showCatalogForSearch() {
  if (state.searchQuery && currentRouteHash() === "#/maison") navigateTo("#/boutique");
}

function triggerSearchBtn() {
  showCatalogForSearch();
  scrollToCatalog();
  renderCatalogProducts();
}

let priceDebounceTimer = null;
function handlePriceFilter(val) {
  document.getElementById("filter-price-display").textContent = formatDZD(val);
  clearTimeout(priceDebounceTimer);
  priceDebounceTimer = setTimeout(() => {
    state.maxPriceFilter = Number(val);
    renderCatalogProducts();
  }, 150);
}

function handleInStockToggle(checked) {
  state.inStockOnly = checked;
  renderCatalogProducts();
}

function handleSortChange(val) {
  state.sortBy = val;
  renderCatalogProducts();
}

function toggleFavoritesFilter() {
  state.onlyFavorites = !state.onlyFavorites;
  if (state.onlyFavorites) {
    showToast("Affichage de votre sélection de favoris");
    scrollToCatalog();
  }
  renderStorefront();
}

function toggleFavoriteProduct(prodId) {
  if (state.favorites.has(prodId)) {
    state.favorites.delete(prodId);
  } else {
    state.favorites.add(prodId);
    showToast("Article ajouté à vos favoris");
  }
  saveFavoritesToStorage();
  renderFavoriteCounters();
  renderCatalogProducts();
}

// Header, mobile bar and mobile menu all show the same favourites count.
function renderFavoriteCounters() {
  for (const id of ["fav-count-badge", "mobile-fav-count-badge", "mobile-drawer-fav-count"]) {
    const el = document.getElementById(id);
    if (el) el.textContent = state.favorites.size;
  }
}

function resetCatalogFilters() {
  state.activeCategorySlug = "all";
  state.searchQuery = "";
  state.maxPriceFilter = null;
  state.inStockOnly = false;
  state.onlyFavorites = false;
  state.dynamicFilterSelections = {};
  document.getElementById("store-search-input").value = "";
  document.getElementById("filter-max-price").value = String(catalogMaxPrice());
  document.getElementById("filter-price-display").textContent = formatDZD(catalogMaxPrice());
  document.getElementById("filter-instock-only").checked = false;
  // The address changes with the view (a reload or a shared link shows the
  // same thing); the router decides which sections are visible.
  if (currentRouteHash() === "#/boutique") renderStorefront();
  else navigateTo("#/boutique");
}

function toggleDynamicAttrFilter(attrKey, optionVal) {
  if (state.dynamicFilterSelections[attrKey] === optionVal) {
    delete state.dynamicFilterSelections[attrKey];
  } else {
    state.dynamicFilterSelections[attrKey] = optionVal;
  }
  renderDynamicSidebarFilters();
  renderCatalogProducts();
}

function renderStorefront() {
  const t = I18N[state.lang];
  renderFavoriteCounters();
  const totalCartCount = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  document.getElementById("cart-count-badge").textContent = totalCartCount;
  const mobCartBadge = document.getElementById("mobile-cart-count-badge");
  if (mobCartBadge) mobCartBadge.textContent = totalCartCount;

  // Render Dynamic Collections & Category Pills
  renderHeaderCollections();

  // 1. Category Navigation Bar (if legacy element present)
  const navEl = document.getElementById("dynamic-nav-categories");
  if (navEl) {
    let navHtml = `<button type="button" onclick="navigateStore('home')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
      state.activeCategorySlug === "all"
        ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
        : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
    }">${t.home}</button>`;

    state.categories.forEach((c) => {
      const isAct = state.activeCategorySlug === c.slug;
      navHtml += `<button type="button" onclick="filterByCategory('${c.slug}')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
        isAct
          ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
          : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
      }">${catName(c)}</button>`;
    });
    navEl.innerHTML = navHtml;
  }

  // 2. Homepage Categories Grid (Matches 1000589999.png Dark Emerald & Gold Cards)
  const homeGrid = document.getElementById("home-categories-grid");
  if (state.categories.length === 0) {
    homeGrid.innerHTML = `
      <div class="col-span-full py-8 px-4 text-center bg-white/70 backdrop-blur-sm rounded-2xl border border-gold-reflective/30 space-y-1.5">
        <p class="font-luxury text-emerald-deep font-bold text-sm sm:text-base">Maison Mus Luxury</p>
        <p class="text-[11px] sm:text-xs text-charcoal/70">Nouvelle collection en cours d'actualisation.</p>
      </div>
    `;
  } else {
    homeGrid.innerHTML = state.categories
      .map((c) => {
        return `
          <button type="button" onclick="filterByCategory('${c.slug}')" class="h-full group cat-card-bg rounded-xl sm:rounded-2xl overflow-hidden border border-gold-reflective/35 shadow-luxury hover:shadow-luxury-hover hover:border-gold-reflective transition text-center flex flex-col justify-between">
            <div class="aspect-[4/3] w-full overflow-hidden bg-emerald-forest relative">
              <img src="${c.image}" alt="${catName(c)}" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='${PLACEHOLDER_IMG}'" class="w-full h-full object-cover group-hover:scale-105 transition duration-500" />
              <div class="absolute inset-0 bg-gradient-to-t from-emerald-forest/75 via-transparent to-transparent"></div>
            </div>
            <div class="w-full px-1.5 sm:px-2 py-2 sm:py-2.5 flex items-center justify-center gap-1.5 bg-emerald-forest/95 border-t border-gold-reflective/20">
              <span class="w-1.5 h-1.5 rounded-full bg-gold-reflective flex-shrink-0"></span>
              <span class="font-semibold text-[11px] sm:text-xs text-white group-hover:text-gold-reflective truncate transition">${catName(c)}</span>
            </div>
          </button>
        `;
      })
      .join("");
  }

  renderDynamicSidebarFilters();
  renderCatalogProducts();
  renderHomeContent();
}

function renderDynamicSidebarFilters() {
  const container = document.getElementById("dynamic-category-filters");
  const activeCat = state.categories.find((c) => c.slug === state.activeCategorySlug);

  let html = `
    <div class="space-y-2.5">
      <p class="text-[11px] font-bold text-charcoal/70 uppercase tracking-wider">Catégories</p>
      <div class="flex flex-wrap gap-1.5">
        <button type="button" onclick="filterByCategory('all')" class="px-3 py-1 rounded-full text-xs font-semibold border transition ${
          state.activeCategorySlug === "all"
            ? "bg-emerald-deep text-gold-reflective border-emerald-deep"
            : "bg-cream text-charcoal border-gray-200 hover:border-gold-reflective"
        }">Tout voir</button>
        ${state.categories
          .map(
            (c) => `
          <button type="button" onclick="filterByCategory('${c.slug}')" class="px-3 py-1 rounded-full text-xs font-semibold border transition ${
              state.activeCategorySlug === c.slug
                ? "bg-emerald-deep text-gold-reflective border-emerald-deep"
                : "bg-cream text-charcoal border-gray-200 hover:border-gold-reflective"
            }">${catName(c)}</button>
        `
          )
          .join("")}
      </div>
    </div>
  `;

  if (activeCat && activeCat.attributes) {
    activeCat.attributes.forEach((attr) => {
      const selectedVal = state.dynamicFilterSelections[attr.key] || "";
      html += `
        <div class="space-y-2 pt-3 border-t border-gray-100">
          <p class="text-[11px] font-bold text-charcoal/70 uppercase tracking-wider">${attrLabel(attr)}</p>
          <div class="flex flex-wrap gap-1.5">
            ${attr.options
              .map((opt) => {
                const isSel = selectedVal === opt;
                const hex = COLOR_SWATCH_HEX[opt];
                return `<button type="button" onclick="toggleDynamicAttrFilter('${attr.key}', ${jsArg(opt)})" class="px-2.5 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 transition ${
                  isSel
                    ? "bg-gold-reflective text-emerald-forest border-gold-dark font-bold"
                    : "bg-white text-charcoal border-gray-200 hover:border-gold-reflective"
                }">
                  ${hex ? `<span class="w-3 h-3 rounded-full border border-black/20" style="background-color:${hex}"></span>` : ""}
                  <span>${opt}</span>
                </button>`;
              })
              .join("")}
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
}

function renderCatalogProducts() {
  const t = I18N[state.lang];
  const activeCat = state.categories.find((c) => c.slug === state.activeCategorySlug);

  document.getElementById("catalog-breadcrumb").textContent = activeCat ? decodeHtml(catName(activeCat)) : t.allCollections;
  document.getElementById("catalog-heading").textContent = activeCat ? decodeHtml(catName(activeCat)) : "Produits en vedette";
  document.getElementById("catalog-description").textContent = activeCat
    ? decodeHtml(catDesc(activeCat))
    : L("Sélection Mus Luxury • Livraison 69 Wilayas avec paiement à la livraison.", "تشكيلة موس لوكسوري • التوصيل إلى 69 ولاية والدفع عند الاستلام.", "Mus Luxury selection • Delivery to 69 wilayas, cash on delivery.");

  let list = [...state.products];

  if (activeCat) {
    list = list.filter((p) => p.category_id === activeCat.id);
  }
  if (state.onlyFavorites) {
    list = list.filter((p) => state.favorites.has(p.id));
  }
  if (state.searchQuery) {
    list = list.filter(
      (p) =>
        p.name_fr.toLowerCase().includes(state.searchQuery) ||
        (p.name_ar && p.name_ar.includes(state.searchQuery)) ||
        (p.name_en && p.name_en.toLowerCase().includes(state.searchQuery)) ||
        (p.brand && p.brand.toLowerCase().includes(state.searchQuery))
    );
  }
  if (state.maxPriceFilter !== null) list = list.filter((p) => p.selling_price_dzd <= state.maxPriceFilter);

  if (state.inStockOnly) {
    list = list.filter((p) => p.variants.reduce((s, v) => s + v.stock, 0) > 0);
  }

  Object.entries(state.dynamicFilterSelections).forEach(([key, val]) => {
    list = list.filter((p) => {
      if (p.attributes && p.attributes[key] === val) return true;
      return p.variants.some((v) => v.attrs && v.attrs[key] === val);
    });
  });

  if (state.sortBy === "price_asc") {
    list.sort((a, b) => a.selling_price_dzd - b.selling_price_dzd);
  } else if (state.sortBy === "price_desc") {
    list.sort((a, b) => b.selling_price_dzd - a.selling_price_dzd);
  } else if (state.sortBy === "popularity") {
    list.sort((a, b) => (b.sales_count || 0) - (a.sales_count || 0));
  } else {
    // "Plus récents": newest product first.
    list.sort((a, b) => b.id - a.id);
  }

  document.getElementById("catalog-count-pill").textContent = `${list.length} article${list.length > 1 ? "s" : ""}`;

  const grid = document.getElementById("store-products-grid");
  if (!state.isCatalogLoaded && state.products.length === 0) {
    grid.innerHTML = Array(6).fill(`
      <div class="bg-white rounded-xl sm:rounded-2xl overflow-hidden border border-gold-reflective/25 p-3 sm:p-4 space-y-3 animate-pulse">
        <div class="w-full aspect-[4/5] bg-gray-200/80 rounded-xl"></div>
        <div class="h-2.5 bg-gray-200/80 rounded w-1/3"></div>
        <div class="h-4 bg-gray-200/80 rounded w-3/4"></div>
        <div class="flex justify-between items-center pt-2">
          <div class="h-5 bg-gray-200/80 rounded w-2/5"></div>
          <div class="h-7 w-7 bg-gray-200/80 rounded-full"></div>
        </div>
      </div>
    `).join("");
    return;
  }
  if (list.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full bg-white rounded-2xl p-10 text-center border border-gold-reflective/25 space-y-3">
        <p class="font-luxury text-xl font-bold text-emerald-deep">Aucun article ne correspond à votre sélection</p>
        <p class="text-xs text-gray-500">Essayez de modifier vos filtres ou de parcourir toutes nos collections.</p>
        <button type="button" onclick="resetCatalogFilters()" class="px-5 py-2.5 rounded-full bg-emerald-deep text-gold-reflective text-xs font-bold">Afficher toute la boutique</button>
      </div>
    `;
    return;
  }

  grid.innerHTML = list
    .map((p) => {
      const totalStock = p.variants.reduce((s, v) => s + v.stock, 0);
      const firstAvailableVar = p.variants.find((v) => v.stock > 0) || p.variants[0];
      const isFav = state.favorites.has(p.id);
      const swatches = productSwatches(p);

      return `
        <article class="product-card bg-white rounded-xl sm:rounded-2xl overflow-hidden border border-gold-reflective/25 shadow-luxury hover:shadow-luxury-hover transition duration-300">
          <!-- Image Container with Strict Aspect Ratio -->
          <div class="product-card-media relative bg-cream-warm overflow-hidden group">
            <img src="${p.image}" alt="${prodName(p)}" loading="lazy" decoding="async" onclick="openProductDetailModal(${p.id})" class="w-full h-full object-cover cursor-pointer group-hover:scale-105 transition duration-500" />
            ${
              p.badge
                ? `<span class="absolute top-2.5 left-2.5 px-2.5 py-0.5 sm:px-3 sm:py-1 rounded-full ${
                    p.badge === "Promo" ? "bg-red-600 text-white" : "bg-emerald-deep text-gold-light border border-gold-reflective/40"
                  } text-[9px] sm:text-[10px] font-bold uppercase tracking-wider shadow-sm">${p.badge}</span>`
                : ""
            }
            <button type="button" onclick="toggleFavoriteProduct(${p.id})" class="absolute top-2.5 right-2.5 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-white/95 hover:bg-white flex items-center justify-center shadow-md transition" aria-label="Favori">
              <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4 ${isFav ? "text-red-600 fill-red-600" : "text-charcoal/70"}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
          </div>

          <!-- Card Body with Uniform Baselines -->
          <div class="p-3 sm:p-4 flex-1 flex flex-col justify-between space-y-2.5 sm:space-y-3">
            <div>
              <p class="text-[9px] sm:text-[10px] font-bold uppercase tracking-widest text-gold-dark truncate">${p.brand || "MUS LUXURY"}</p>
              <h3 onclick="openProductDetailModal(${p.id})" class="font-bold text-charcoal text-xs sm:text-base hover:text-emerald-deep cursor-pointer line-clamp-1 mt-0.5">${prodName(p)}</h3>

              <!-- Price & Discount Badge Row -->
              <div class="flex flex-wrap items-center justify-between gap-1 mt-1.5">
                <div class="flex items-baseline gap-1.5">
                  <span class="text-sm sm:text-lg font-extrabold text-emerald-deep">${formatDZD(p.selling_price_dzd)}</span>
                  ${
                    p.previous_price_dzd
                      ? `<span class="text-[10px] sm:text-xs text-gray-400 line-through">${formatDZD(p.previous_price_dzd)}</span>`
                      : ""
                  }
                </div>
                ${
                  p.discount_percent > 0
                    ? `<span class="px-1.5 py-0.5 rounded bg-red-600 text-white text-[9px] sm:text-[10px] font-bold">-${p.discount_percent}%</span>`
                    : ""
                }
              </div>

              <!-- Real colour dots (hidden when the product has no colour options) -->
              <div class="flex items-center gap-1.5 mt-2.5 ${swatches.length ? "" : "hidden"}">
                ${swatches
                  .map(
                    (hex) =>
                      `<span onclick="openProductDetailModal(${p.id})" class="w-4 h-4 rounded-full border border-gray-300 cursor-pointer hover:scale-110 transition" style="background-color:${hex}"></span>`
                  )
                  .join("")}
              </div>
            </div>

            <!-- Full-Width Deep Emerald Add to Cart Button (Matches 1000589999.png) -->
            <div class="pt-1">
              <button
                type="button"
                onclick="quickAddToCart(${p.id}, ${firstAvailableVar ? firstAvailableVar.id : 0})"
                ${totalStock <= 0 ? "disabled" : ""}
                class="w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition ${
                  totalStock > 0
                    ? "bg-emerald-deep text-white hover:bg-emerald-forest shadow-sm"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed"
                }"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="9" cy="21" r="1"></circle>
                  <circle cx="20" cy="21" r="1"></circle>
                  <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                </svg>
                <span>${totalStock > 0 ? t.addToCart : t.outOfStock}</span>
              </button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

// ========================================================================

Object.assign(window, {
  setActiveCategory,
  renderFavoriteCounters,
  currentRouteHash,
  currentUrl,
  navigateTo,
  DEFAULT_PAGE_TITLE,
  DEFAULT_PAGE_DESC,
  setPageMeta,
  applyRouteMeta,
  updateActiveNavIndicators,
  onRouteEvent,
  handleRoute,
  navigateStore,
  filterByCategory,
  getAlgeriaCurrentTime,
  openSignLightbox,
  closeSignLightbox,
  renderLaMaisonPage,
  copyStoreAddress,
  renderHeaderCollections,
  openMobileMenu,
  closeMobileMenu,
  scrollToCatalog,
  handleStoreSearch,
  triggerSearchBtn,
  handlePriceFilter,
  handleInStockToggle,
  handleSortChange,
  toggleFavoritesFilter,
  toggleFavoriteProduct,
  resetCatalogFilters,
  toggleDynamicAttrFilter,
  renderStorefront,
  renderDynamicSidebarFilters,
  renderCatalogProducts,
  setLastRoutedUrl,
});
