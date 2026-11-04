import re

sf_path = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\apps\storefront\index.html"

with open(sf_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add skeleton cards to store-products-grid in initial HTML
old_grid = '<div id="store-products-grid" class="product-card-grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-3 gap-3 sm:gap-5">\n          </div>'
skeleton_card = """            <div class="bg-white rounded-xl sm:rounded-2xl overflow-hidden border border-gold-reflective/25 p-3 sm:p-4 space-y-3 animate-pulse">
              <div class="w-full aspect-[4/5] bg-gray-200/80 rounded-xl"></div>
              <div class="h-2.5 bg-gray-200/80 rounded w-1/3"></div>
              <div class="h-4 bg-gray-200/80 rounded w-3/4"></div>
              <div class="flex justify-between items-center pt-2">
                <div class="h-5 bg-gray-200/80 rounded w-2/5"></div>
                <div class="h-7 w-7 bg-gray-200/80 rounded-full"></div>
              </div>
            </div>"""
new_grid = f'<div id="store-products-grid" class="product-card-grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-3 gap-3 sm:gap-5">\n' + "\n".join([skeleton_card]*6) + '\n          </div>'

assert old_grid in code, "old_grid not found"
code = code.replace(old_grid, new_grid, 1)
print("1. Added skeleton cards to store-products-grid initial HTML.")

# 2. Add isCatalogLoaded flag to state
old_state = """      activeCategorySlug: "all",
      searchQuery: "",
      maxPriceFilter: 25000,"""

new_state = """      activeCategorySlug: "all",
      searchQuery: "",
      maxPriceFilter: 25000,
      isCatalogLoaded: false,"""

assert old_state in code, "old_state not found"
code = code.replace(old_state, new_state, 1)
print("2. Added isCatalogLoaded to state.")

# 3. Add debouncing to handleStoreSearch and handlePriceFilter
old_search_price = """    function handleStoreSearch(val) {
      state.searchQuery = val.trim().toLowerCase();
      renderCatalogProducts();
    }

    function triggerSearchBtn() {
      scrollToCatalog();
      renderCatalogProducts();
    }

    function handlePriceFilter(val) {
      state.maxPriceFilter = Number(val);
      document.getElementById("filter-price-display").textContent = formatDZD(val);
      renderCatalogProducts();
    }"""

new_search_price = """    let searchDebounceTimer = null;
    function handleStoreSearch(val) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        state.searchQuery = val.trim().toLowerCase();
        renderCatalogProducts();
      }, 200);
    }

    function triggerSearchBtn() {
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
    }"""

assert old_search_price in code, "old_search_price not found"
code = code.replace(old_search_price, new_search_price, 1)
print("3. Added debouncing to handleStoreSearch and handlePriceFilter.")

# 4. Update renderCatalogProducts to render skeletons if not loaded yet
old_grid_render = """      const grid = document.getElementById("store-products-grid");
      if (list.length === 0) {"""

new_grid_render = """      const grid = document.getElementById("store-products-grid");
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
      if (list.length === 0) {"""

assert old_grid_render in code, "old_grid_render not found"
code = code.replace(old_grid_render, new_grid_render, 1)
print("4. Added dynamic skeleton fallback to renderCatalogProducts.")

# 5. Optimize syncStorefrontWithBackend with signature caching
old_sync_start = """    let isSyncingBackend = false;
    async function syncStorefrontWithBackend() {
      if (isSyncingBackend) return;
      isSyncingBackend = true;
      try {
        const [catRes, prodRes, wilRes] = await Promise.all([
          fetch("/api/v1/categories").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/products?page_size=50").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/delivery-zones").then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]);"""

new_sync_start = """    let isSyncingBackend = false;
    let lastCatJson = "";
    let lastProdJson = "";
    let lastWilJson = "";
    async function syncStorefrontWithBackend() {
      if (isSyncingBackend) return;
      isSyncingBackend = true;
      try {
        const [catRes, prodRes, wilRes] = await Promise.all([
          fetch("/api/v1/categories").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/products?page_size=50").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/delivery-zones").then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]);
        let dataChanged = false;"""

assert old_sync_start in code, "old_sync_start not found"
code = code.replace(old_sync_start, new_sync_start, 1)

old_cat_block = """        if (catRes && Array.isArray(catRes.items)) {
          state.categories = catRes.items.map((c) => ({"""

new_cat_block = """        if (catRes && Array.isArray(catRes.items)) {
          const rawCat = JSON.stringify(catRes.items);
          if (rawCat !== lastCatJson) {
            lastCatJson = rawCat;
            dataChanged = true;
          }
          state.categories = catRes.items.map((c) => ({"""

assert old_cat_block in code, "old_cat_block not found"
code = code.replace(old_cat_block, new_cat_block, 1)

old_prod_block = """        if (prodRes && Array.isArray(prodRes.items)) {
          state.products = prodRes.items.map((p) => {"""

new_prod_block = """        if (prodRes && Array.isArray(prodRes.items)) {
          const rawProd = JSON.stringify(prodRes.items);
          if (rawProd !== lastProdJson) {
            lastProdJson = rawProd;
            dataChanged = true;
          }
          state.products = prodRes.items.map((p) => {"""

assert old_prod_block in code, "old_prod_block not found"
code = code.replace(old_prod_block, new_prod_block, 1)

old_wil_block = """        if (wilRes && Array.isArray(wilRes.items) && wilRes.items.length > 0) {
          WILAYAS.splice(
            0,
            WILAYAS.length,
            ...wilRes.items.map((w) => ({
              code: w.wilaya_code,
              name_fr: w.wilaya_name_fr,
              name_ar: w.wilaya_name_ar || "",
              communes: w.communes && w.communes.length ? w.communes : [w.wilaya_name_fr],
              home_fee: w.rates?.home?.fee_dzd ?? 600,
              desk_fee: w.rates?.stop_desk?.fee_dzd ?? 400,
            }))
          );
        }
        renderStorefront();"""

new_wil_block = """        if (wilRes && Array.isArray(wilRes.items) && wilRes.items.length > 0) {
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
              home_fee: w.rates?.home?.fee_dzd ?? 600,
              desk_fee: w.rates?.stop_desk?.fee_dzd ?? 400,
            }))
          );
        }
        if (dataChanged || !state.isCatalogLoaded) {
          state.isCatalogLoaded = true;
          renderStorefront();
        }"""

assert old_wil_block in code, "old_wil_block not found"
code = code.replace(old_wil_block, new_wil_block, 1)
print("5. Optimized syncStorefrontWithBackend with signature diffing.")

# 6. Gate polling interval with document.visibilityState
old_interval = """      // Realtime Background Sync: Re-sync every 3 seconds
      setInterval(syncStorefrontWithBackend, 3000);"""

new_interval = """      // Realtime Background Sync: Re-sync every 4 seconds only if tab is actively visible
      setInterval(() => {
        if (document.visibilityState === "visible") {
          syncStorefrontWithBackend();
        }
      }, 4000);

      // Re-sync immediately when customer returns or focuses the window
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          syncStorefrontWithBackend();
        }
      });"""

assert old_interval in code, "old_interval not found"
code = code.replace(old_interval, new_interval, 1)
print("6. Gated polling interval with document.visibilityState.")

# 7. Add loading="lazy" decoding="async" to promo images
code = code.replace(
    '<img src="/assets/prod_baskets_elegantes.jpg" alt="Chaussures" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />',
    '<img src="/assets/prod_baskets_elegantes.jpg" alt="Chaussures" loading="lazy" decoding="async" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />'
)
code = code.replace(
    '<img src="/assets/prod_lunettes_soleil.jpg" alt="Lunettes" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />',
    '<img src="/assets/prod_lunettes_soleil.jpg" alt="Lunettes" loading="lazy" decoding="async" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />'
)
code = code.replace(
    '<img src="/assets/prod_montre_or.jpg" alt="Montres" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />',
    '<img src="/assets/prod_montre_or.jpg" alt="Montres" loading="lazy" decoding="async" class="w-24 h-24 object-cover rounded-xl border border-gold-reflective/30 shadow-sm" />'
)
code = code.replace(
    '<img src="/assets/mus_luxury_sign.jpg" alt="Boutique Mus Luxury Ouled Yaïch" class="w-full h-20 object-cover rounded-xl border border-gold-reflective/30" />',
    '<img src="/assets/mus_luxury_sign.jpg" alt="Boutique Mus Luxury Ouled Yaïch" loading="lazy" decoding="async" class="w-full h-20 object-cover rounded-xl border border-gold-reflective/30" />'
)
print("7. Added loading='lazy' decoding='async' to promo images.")

with open(sf_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(code)

print("Saved all storefront optimizations successfully!")

