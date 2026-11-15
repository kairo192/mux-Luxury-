// Product window: pictures, colour / size choices, quantity, delivery estimate.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// PRODUCT DETAILS MODAL — CMS-DRIVEN MULTI-AXIS SELECTORS (Couleur, Taille, Pointure, etc.)
// ========================================================================
state.activePdpAxes = {};
state.activePdpWilaya = "16";
state.activePdpDeliveryMethod = "home";
state.checkoutWilaya = "16";
state.checkoutMethod = "home";

function isProductModalOpen() {
  const m = document.getElementById("product-detail-modal");
  return Boolean(m && !m.classList.contains("hidden"));
}

function hideProductModal() {
  document.getElementById("product-detail-modal").classList.add("hidden");
}

// #/produit/<slug> — a shared link, or the back/forward buttons.
function openProductBySlug(slug) {
  if (!state.isCatalogLoaded) {
    state.pendingProductSlug = slug;
    return;
  }
  const prod = state.products.find((p) => p.slug === slug);
  if (!prod) {
    history.replaceState(null, "", "/#/boutique");
    handleRoute();
    showToast("Cet article n'est plus disponible.", "error");
    return;
  }
  openProductDetailModal(prod.id, { fromRoute: true });
}

function openProductDetailModal(prodId, opts = {}) {
  const prod = state.products.find((p) => p.id === prodId);
  if (!prod) return;
  // Give the product its own address (shareable link) without leaving the
  // current page; the browser/phone back button then closes the pop-up.
  if (!opts.fromRoute) {
    const target = "/produit/" + encodeURIComponent(decodeHtml(prod.slug));
    if (currentUrl() !== target) {
      if (!currentRouteHash().startsWith("#/produit/")) {
        state.pdpReturnUrl = currentUrl();
      }
      history.pushState({ pdp: prod.id }, "", target);
      setLastRoutedUrl(currentUrl());
      state.pdpPushed = true;
    }
  }
  setPageMeta(
    `${decodeHtml(prodName(prod))} — Mus Luxury`,
    decodeHtml(prod.description_fr || "").slice(0, 160) || DEFAULT_PAGE_DESC,
    "/produit/" + prod.slug
  );
  state.activePdpProductId = prod.id;
  const firstAvail = prod.variants.find((v) => v.stock > 0) || prod.variants[0];
  state.activePdpVariantId = firstAvail ? firstAvail.id : null;
  state.activePdpAxes = firstAvail && firstAvail.attrs ? { ...firstAvail.attrs } : {};
  state.activePdpQty = 1;
  state.activePdpMultiVariantMode = "same";
  state.activePdpAllocations = {};
  state.activePdpTab = "desc";

  const cat = state.categories.find((c) => c.id === prod.category_id);
  document.getElementById("pdp-breadcrumb").textContent = decodeHtml(`Accueil  ›  ${cat ? catName(cat) : "Boutique"}  ›  ${prodName(prod)}`);
  renderPdpModalContent();
  document.getElementById("product-detail-modal").classList.remove("hidden");
}

function closeProductDetailModal() {
  if (state.pdpPushed && currentRouteHash().startsWith("#/produit/")) {
    // Go back to where the customer was; handleRoute() hides the pop-up
    // and keeps the scroll position.
    state.pdpPushed = false;
    history.back();
    return;
  }
  hideProductModal();
  if (currentRouteHash().startsWith("#/produit/")) {
    // Opened from a shared link: there is no previous page in the shop.
    history.replaceState(null, "", "/#/boutique");
    handleRoute();
  }
}

function selectPdpAxisValue(axisKey, optionVal) {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;
  state.activePdpAxes[axisKey] = optionVal;

  // Find exact matching variant for all selected axes, or closest match that has this axisKey=optionVal
  let matched = prod.variants.find((v) => {
    if (!v.attrs) return false;
    return Object.entries(state.activePdpAxes).every(([k, val]) => v.attrs[k] === val);
  });

  if (!matched) {
    matched = prod.variants.find((v) => v.attrs && v.attrs[axisKey] === optionVal && v.stock > 0)
           || prod.variants.find((v) => v.attrs && v.attrs[axisKey] === optionVal)
           || prod.variants[0];
    if (matched && matched.attrs) {
      state.activePdpAxes = { ...matched.attrs };
    }
  }

  if (matched) {
    state.activePdpVariantId = matched.id;
  }
  state.activePdpQty = 1;
  renderPdpModalContent();
}

function selectPdpVariant(varId) {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;
  const v = prod.variants.find((x) => x.id === varId);
  if (v) {
    state.activePdpVariantId = v.id;
    state.activePdpAxes = v.attrs ? { ...v.attrs } : {};
  }
  state.activePdpQty = 1;
  renderPdpModalContent();
}

function changePdpWilayaEstimate(wilayaCode) {
  state.activePdpWilaya = wilayaCode;
  state.checkoutWilaya = wilayaCode;
  renderPdpModalContent();
}

function changePdpDeliveryMethod(method) {
  state.activePdpDeliveryMethod = method === "stop_desk" ? "stop_desk" : "home";
  state.checkoutMethod = state.activePdpDeliveryMethod;
  renderPdpModalContent();
}

function setPdpMultiVariantMode(mode) {
  state.activePdpMultiVariantMode = mode;
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (mode === "split" && prod) {
    state.activePdpAllocations = {};
    const currentVar = prod.variants.find((v) => v.id === state.activePdpVariantId && v.stock > 0) || prod.variants.find((v) => v.stock > 0);
    if (currentVar) {
      state.activePdpAllocations[currentVar.id] = Math.min(state.activePdpQty, currentVar.stock);
    }
  }
  renderPdpModalContent();
}

function changeVariantAllocation(varId, delta) {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;
  const v = prod.variants.find((x) => x.id === varId);
  if (!v) return;

  const current = state.activePdpAllocations[varId] || 0;
  const currentTotal = Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0);

  if (delta > 0) {
    if (currentTotal >= state.activePdpQty) {
      showToast(`Total des ${state.activePdpQty} articles déjà alloué. Diminuez une autre déclinaison d'abord.`, "warning");
      return;
    }
    if (current + 1 > v.stock) {
      showToast(`Stock maximum disponible pour ${v.title} : ${v.stock}`, "error");
      return;
    }
    state.activePdpAllocations[varId] = current + 1;
  } else if (delta < 0) {
    if (current > 0) {
      state.activePdpAllocations[varId] = current - 1;
      if (state.activePdpAllocations[varId] === 0) {
        delete state.activePdpAllocations[varId];
      }
    }
  }
  renderPdpModalContent();
}

function changePdpQty(delta) {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;
  const isSplit = state.activePdpMultiVariantMode === "split";
  const totalStock = prod.variants.reduce((sum, v) => sum + (v.stock || 0), 0);
  const variant = prod.variants.find((v) => v.id === state.activePdpVariantId);
  const maxStock = isSplit ? totalStock : (variant ? variant.stock : 1);

  const next = state.activePdpQty + delta;
  if (!isSplit && delta > 0 && next > maxStock && next <= totalStock && prod.variants.length > 1) {
    // This colour / size has no more, but the others do: switch to
    // "several variants" so the customer can pick one of each.
    state.activePdpQty = next;
    setPdpMultiVariantMode("split");
    showToast(L("Répartissez les pièces entre les déclinaisons disponibles.", "وزّعوا القطع على الخيارات المتوفرة.", "Spread the pieces across the available options."));
    return;
  }
  if (next >= 1 && next <= Math.max(1, maxStock)) {
    state.activePdpQty = next;
    if (next === 1) {
      state.activePdpMultiVariantMode = "same";
      state.activePdpAllocations = {};
    }
    renderPdpModalContent();
  } else if (next > maxStock) {
    showToast(`Stock maximum disponible : ${maxStock}`, "error");
  }
}

function switchPdpImage(imgUrl) {
  const mainImg = document.getElementById("pdp-main-img");
  if (mainImg) mainImg.src = imgUrl;
}

function togglePdpZoom() {
  const wrap = document.getElementById("pdp-zoom-wrap");
  if (wrap) wrap.classList.toggle("zoomed");
}

function switchPdpTab(tabName) {
  state.activePdpTab = tabName;
  renderPdpModalContent();
}

function renderPdpModalContent() {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;
  const cat = state.categories.find((c) => c.id === prod.category_id);
  const variant = prod.variants.find((v) => v.id === state.activePdpVariantId) || prod.variants[0];
  const effectivePrice = variant && variant.price ? variant.price : prod.selling_price_dzd;
  // Items total: in split mode each allocated piece at ITS variant's price.
  const merchTotal = state.activePdpMultiVariantMode === "split" && state.activePdpQty > 1
    ? Object.entries(state.activePdpAllocations).reduce((sum, [vid, q]) => {
        const v = prod.variants.find((x) => x.id === Number(vid));
        return sum + (v && v.price ? v.price : prod.selling_price_dzd) * (Number(q) || 0);
      }, 0)
    : effectivePrice * state.activePdpQty;
  // What the WhatsApp message asks for: each chosen variant with its count.
  const waChoiceText = state.activePdpMultiVariantMode === "split" && state.activePdpQty > 1
    ? Object.entries(state.activePdpAllocations).filter(([, q]) => q > 0)
        .map(([vid, q]) => `${q}× ${(prod.variants.find((x) => x.id === Number(vid)) || {}).title || ""}`).join(", ")
    : (variant ? variant.title : "");
  const varStock = variant ? variant.stock : 0;
  const tr = I18N[state.lang] || I18N.fr;
  const activeImage = (variant && variant.img) ? variant.img : prod.image;
  const gallery = prod.gallery && prod.gallery.length ? prod.gallery : [prod.image];

  // 1. Dynamically build interactive selectors for EVERY variant axis defined on this category in the CMS
  //    (e.g., Couleur swatches, Taille / Pointure boxes, Teinte, Calibre, Cadran, etc.)
  const variantAxesAttrs = (cat && cat.attributes ? cat.attributes : []).filter((a) => a.variant);
  let axesSelectorsHtml = "";

  variantAxesAttrs.forEach((axisAttr) => {
    // Collect unique option values actually present across this product's variants for this axis
    const prodAxisValues = [];
    prod.variants.forEach((v) => {
      const val = v.attrs ? v.attrs[axisAttr.key] : null;
      if (val && !prodAxisValues.includes(val)) prodAxisValues.push(val);
    });
    if (prodAxisValues.length === 0) return;

    const currentSelectedVal = state.activePdpAxes[axisAttr.key] || prodAxisValues[0];
    const isColorAxis = axisAttr.type === "color";

    if (isColorAxis) {
      axesSelectorsHtml += `
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-charcoal/80">${attrLabel(axisAttr)} : <strong class="text-emerald-deep">${currentSelectedVal}</strong></span>
          </div>
          <div class="flex flex-wrap items-center gap-2.5">
            ${prodAxisValues
              .map((val) => {
                const isSel = currentSelectedVal === val;
                const hex = safeHex(COLOR_SWATCH_HEX[val] || (axisAttr.rawOptions && axisAttr.rawOptions.find(o => o.value === val)?.color_hex)) || "#063D2E";
                return `
                  <button
                    type="button"
                    onclick="selectPdpAxisValue(${jsArg(decodeHtml(axisAttr.key))}, ${jsArg(val)})"
                    class="group flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold transition ${
                      isSel
                        ? "border-gold-reflective bg-emerald-deep text-gold-light shadow-gold-ring"
                        : "border-gray-300 bg-white text-charcoal hover:border-emerald-deep"
                    }"
                  >
                    <span class="w-4 h-4 rounded-full border border-black/20 flex-shrink-0" style="background-color:${hex}"></span>
                    <span>${val}</span>
                  </button>
                `;
              })
              .join("")}
          </div>
        </div>
      `;
    } else {
      axesSelectorsHtml += `
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-charcoal/80">${attrLabel(axisAttr)} : <strong class="text-emerald-deep">${currentSelectedVal}</strong></span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            ${prodAxisValues
              .map((val) => {
                const isSel = currentSelectedVal === val;
                // Check if this option has stock with current other selections
                const candidateVar = prod.variants.find(
                  (v) => v.attrs && v.attrs[axisAttr.key] === val && Object.entries(state.activePdpAxes).every(([k, ov]) => k === axisAttr.key || v.attrs[k] === ov)
                ) || prod.variants.find((v) => v.attrs && v.attrs[axisAttr.key] === val);
                const hasStock = candidateVar ? candidateVar.stock > 0 : true;
                return `
                  <button
                    type="button"
                    onclick="selectPdpAxisValue(${jsArg(decodeHtml(axisAttr.key))}, ${jsArg(val)})"
                    class="min-w-[44px] px-3.5 py-2 rounded-xl text-xs font-bold border transition ${
                      isSel
                        ? "bg-emerald-deep text-gold-reflective border-gold-reflective shadow-sm"
                        : hasStock
                        ? "bg-white text-charcoal border-gray-300 hover:border-emerald-deep"
                        : "bg-gray-100 text-gray-400 border-gray-200 line-through"
                    }"
                  >
                    ${val}
                  </button>
                `;
              })
              .join("")}
          </div>
        </div>
      `;
    }
  });

  // 2. Dynamically build Custom Product Specifications from the Category's non-variant attributes + selected variant
  const customSpecEntries = [];
  if (cat && cat.attributes) {
    cat.attributes
      .filter((a) => !a.variant)
      .forEach((a) => {
        const val = prod.attributes ? prod.attributes[a.key] : null;
        if (val) {
          customSpecEntries.push([attrLabel(a), val]);
        }
      });
  }
  // Also include selected variant attributes in technical specs
  if (variant && variant.attrs && cat && cat.attributes) {
    Object.entries(variant.attrs).forEach(([k, val]) => {
      const attrDef = cat.attributes.find((a) => a.key === k);
      customSpecEntries.push([attrDef ? attrLabel(attrDef) : k, val]);
    });
  }

  const specRows = customSpecEntries
    .map(
      ([label, val]) =>
        `<tr class="border-b border-gray-100"><td class="py-2 font-semibold text-gray-500 text-xs">${label}</td><td class="py-2 font-bold text-charcoal text-xs">${val}</td></tr>`
    )
    .join("");

  const highlightPills = customSpecEntries
    .slice(0, 4)
    .map(
      ([label, val]) =>
        `<span class="px-2.5 py-1 rounded-lg bg-cream border border-gold-reflective/30 text-[11px] text-charcoal"><strong class="text-emerald-deep">${label} :</strong> ${val}</span>`
    )
    .join("");

  // 3. Live 69-Wilaya Delivery Estimator inside PDP
  const selWilaya = WILAYAS.find((w) => w.code === state.activePdpWilaya) || WILAYAS[15];

  const body = document.getElementById("pdp-modal-body");
  body.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-12 gap-6">
      <!-- Left Column: Gallery & Thumbnails -->
      <div class="md:col-span-6 space-y-3">
        <div id="pdp-zoom-wrap" onclick="togglePdpZoom()" class="zoom-stage relative h-72 sm:h-80 rounded-2xl bg-cream border border-gold-reflective/40 flex items-center justify-center">
          <img id="pdp-main-img" src="${activeImage}" alt="${prodName(prod)}" class="w-full h-full object-cover" />
          <span class="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-emerald-deep/90 text-gold-light text-[10px] font-mono">SKU: ${variant ? variant.sku : prod.sku}</span>
          <span class="absolute bottom-3 right-3 px-2.5 py-1 rounded-full bg-emerald-forest/85 text-gold-light text-[10px] pointer-events-none">${L("Cliquer pour zoomer", "انقر للتكبير", "Click to zoom")}</span>
        </div>
        <div class="flex items-center gap-2 overflow-x-auto">
          ${gallery
            .map(
              (g) => `
            <button type="button" onclick="switchPdpImage(${jsArg(decodeHtml(g))})" class="w-16 h-16 rounded-xl overflow-hidden border-2 border-gold-reflective/40 hover:border-emerald-deep flex-shrink-0">
              <img src="${g}" alt="Miniature" class="w-full h-full object-cover" />
            </button>
          `
            )
            .join("")}
        </div>
      </div>

      <!-- Right Column: Dynamic CMS Variant Selectors, Custom Attributes & Actions -->
      <div class="md:col-span-6 space-y-4">
        <div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold uppercase tracking-[0.2em] text-gold-dark">${prod.brand || "MUS LUXURY"}</span>
            <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
              varStock > 0 ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"
            }">
              ${varStock > 0 ? `● ${tr.inStock} (${varStock})` : `✕ ${tr.outOfStock}`}
            </span>
          </div>
          <h2 class="font-luxury text-2xl sm:text-3xl font-bold text-emerald-deep mt-1">${prodName(prod)}</h2>
          <div class="flex items-baseline gap-3 mt-2">
            <span class="text-2xl font-extrabold text-gold-dark">${formatDZD(effectivePrice)}</span>
            ${
              prod.previous_price_dzd
                ? `<span class="text-sm text-gray-400 line-through">${formatDZD(prod.previous_price_dzd)}</span>`
                : ""
            }
            ${
              prod.discount_percent > 0
                ? `<span class="px-2 py-0.5 rounded bg-red-600 text-white text-xs font-bold">-${prod.discount_percent}%</span>`
                : ""
            }
          </div>
        </div>

        <p class="text-xs sm:text-sm text-charcoal/80 leading-relaxed whitespace-pre-line">${prodDesc(prod)}</p>

        <!-- Quick Custom Attribute Highlights from CMS -->
        <div class="flex flex-wrap gap-1.5">
          ${highlightPills}
        </div>

        <!-- Quantity Selector & Multi-unit Options Prompt (Scenario A & B) -->
        <div class="space-y-3 pt-2 border-t border-gray-100">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="text-xs font-bold">${L("Quantité :", "الكمية:", "Quantity:")}</span>
              <div class="inline-flex items-center rounded-xl border border-gray-300 bg-white">
                <button type="button" onclick="changePdpQty(-1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">-</button>
                <span class="px-4 py-1.5 text-xs font-extrabold">${state.activePdpQty}</span>
                <button type="button" onclick="changePdpQty(1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">+</button>
              </div>
            </div>
            ${state.activePdpQty >= 2 && prod.variants.length > 1 ? `
              <span class="text-[11px] font-bold text-emerald-deep">${L("Choix multi-unités activé", "اختيار متعدد للقطع", "Multi-item choice on")}</span>
            ` : ""}
          </div>

          <!-- Scenario B Prompt: When selecting 2+ units on a product with multiple variants -->
          ${state.activePdpQty >= 2 && prod.variants.length > 1 ? (() => {
            const tr = I18N[state.lang] || I18N.fr;
            const promptText = (tr.scenarioBPrompt || I18N.fr.scenarioBPrompt).replace('{qty}', state.activePdpQty);
            return `
            <div class="p-3 rounded-xl bg-amber-500/10 border border-gold-reflective/40 space-y-2">
              <p class="text-xs font-bold text-emerald-deep">
                ${promptText}
              </p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onclick="setPdpMultiVariantMode('same')"
                  class="px-2.5 py-1.5 rounded-lg text-xs font-bold border transition ${
                    state.activePdpMultiVariantMode === 'same'
                      ? 'bg-emerald-deep text-gold-reflective border-emerald-deep shadow-sm'
                      : 'bg-white text-charcoal border-gray-300 hover:border-gold-reflective'
                  }"
                >
                  ${tr.scenarioBSame || "Oui, mêmes options"}
                </button>
                <button
                  type="button"
                  onclick="setPdpMultiVariantMode('split')"
                  class="px-2.5 py-1.5 rounded-lg text-xs font-bold border transition ${
                    state.activePdpMultiVariantMode === 'split'
                      ? 'bg-emerald-deep text-gold-reflective border-emerald-deep shadow-sm'
                      : 'bg-white text-charcoal border-gray-300 hover:border-gold-reflective'
                  }"
                >
                  ${tr.scenarioBSplit || "Personnaliser chaque article séparément"}
                </button>
              </div>
            </div>
          `; })() : ""}

          <!-- If Split Mode (Scenario B): Show Interactive Allocation Table -->
          ${state.activePdpQty >= 2 && state.activePdpMultiVariantMode === 'split' ? (() => {
            const totalAllocated = Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0);
            const isComplete = totalAllocated === state.activePdpQty;
            return `
              <div class="space-y-2 p-3 bg-white rounded-xl border border-gold-reflective/30">
                <div class="flex items-center justify-between text-xs pb-1.5 border-b border-gray-100">
                  <span class="font-bold text-emerald-deep">Répartition des ${state.activePdpQty} articles :</span>
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    isComplete ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                  }">
                    ${totalAllocated} / ${state.activePdpQty} alloué${totalAllocated > 1 ? 's' : ''}
                  </span>
                </div>
                <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  ${prod.variants.filter(v => v.stock > 0).map(v => {
                    const allocated = state.activePdpAllocations[v.id] || 0;
                    const colorVal = v.attrs?.color || v.attrs?.couleur;
                    const hex = colorVal ? (COLOR_SWATCH_HEX[colorVal] || '#063D2E') : null;
                    return `
                      <div class="flex items-center justify-between p-2 rounded-lg bg-gray-50 border ${
                        allocated > 0 ? 'border-emerald-600 bg-emerald-50/50' : 'border-gray-200'
                      }">
                        <div class="flex items-center gap-2 min-w-0">
                          ${hex ? `<span class="w-3.5 h-3.5 rounded-full border border-black/20 shrink-0" style="background-color:${hex}"></span>` : ''}
                          <div class="truncate">
                            <span class="font-bold text-xs text-charcoal">${v.title}</span>
                            <span class="text-[10px] text-gray-500 block">Stock : ${v.stock} • ${formatDZD(v.price || prod.selling_price_dzd)}</span>
                          </div>
                        </div>
                        <div class="flex items-center gap-1.5 shrink-0">
                          <button type="button" onclick="changeVariantAllocation(${v.id}, -1)" class="w-7 h-7 rounded bg-white hover:bg-gray-200 border border-gray-300 font-bold text-xs">-</button>
                          <span class="font-extrabold text-xs w-6 text-center">${allocated}</span>
                          <button type="button" onclick="changeVariantAllocation(${v.id}, 1)" class="w-7 h-7 rounded bg-white hover:bg-gray-200 border border-gray-300 font-bold text-xs">+</button>
                        </div>
                      </div>
                    `;
                  }).join('')}
                </div>
                ${!isComplete ? `
                  <p class="text-[11px] text-amber-800 font-semibold bg-amber-50 p-2 rounded-lg border border-amber-200 text-center">
                    Allouez encore ${state.activePdpQty - totalAllocated} article(s) pour valider l'ajout.
                  </p>
                ` : `
                  <p class="text-[11px] text-emerald-800 font-semibold bg-emerald-50 p-2 rounded-lg border border-emerald-200 text-center">
                    Répartition complète (${state.activePdpQty}/${state.activePdpQty})
                  </p>
                `}
              </div>
            `;
          })() : `
            <!-- Standard Single Variant Axes Selectors (Scenario A & Scenario B Same Options) -->
            <div class="space-y-3.5 pt-1">
              ${axesSelectorsHtml}
            </div>
          `}

          <!-- CTA Buttons -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
            <button
              type="button"
              onclick="addPdpToCart(false)"
              ${(state.activePdpMultiVariantMode === 'split' ? (Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0) !== state.activePdpQty) : varStock < state.activePdpQty) ? "disabled" : ""}
              class="py-3 px-4 rounded-xl gold-cta text-emerald-forest font-extrabold text-xs uppercase tracking-wider shadow-md flex items-center justify-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg class="w-4 h-4 stroke-[2.2]" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>
              <span>${tr.addToCart}</span>
            </button>
            <button
              type="button"
              onclick="addPdpToCart(true)"
              ${(state.activePdpMultiVariantMode === 'split' ? (Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0) !== state.activePdpQty) : varStock < state.activePdpQty) ? "disabled" : ""}
              class="py-3 px-4 rounded-xl bg-emerald-deep hover:bg-emerald-forest text-gold-light border border-gold-reflective/40 font-bold text-xs uppercase tracking-wider transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ${tr.buyNow}
            </button>
          </div>
          <a
            href="https://wa.me/${waNumber()}?text=${encodeURIComponent(decodeHtml(`Bonjour Mus Luxury, je souhaite commander : ${prodName(prod)} (${waChoiceText}) - Qté: ${state.activePdpQty} - Prix: ${formatDZD(merchTotal)}`) + "\n" + window.location.origin + "/produit/" + encodeURIComponent(decodeHtml(prod.slug)))}"
            target="_blank"
            rel="noopener noreferrer"
            class="w-full py-2.5 px-4 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold text-xs flex items-center justify-center gap-2 transition"
          >
            <svg class="w-4 h-4 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
            <span>Commander ou poser une question sur WhatsApp (${escapeHtml(storePhoneDisplay())})</span>
          </a>
        </div>

        <!-- Live 69-Wilaya Delivery Estimator & Automatic Total Calculator Box -->
        <div class="p-3.5 rounded-xl bg-emerald-deep/5 border border-emerald-deep/20 space-y-2.5 text-xs">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="font-bold text-emerald-deep flex items-center gap-1.5">
              <svg class="w-4 h-4 text-gold-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13" rx="1"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
              <span>${L("Livraison (69 Wilayas) :", "التوصيل (69 ولاية):", "Delivery (69 wilayas):")}</span>
            </span>
            <select onchange="changePdpWilayaEstimate(this.value)" class="px-2.5 py-1.5 rounded-lg border border-gray-300 bg-white font-semibold text-xs focus:outline-none focus:border-emerald-deep">
              ${WILAYAS.map((w) => `<option value="${w.code}" ${w.code === selWilaya.code ? "selected" : ""}>${w.code} - ${wilayaName(w)}</option>`).join("")}
            </select>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              onclick="changePdpDeliveryMethod('home')"
              class="p-2 rounded-xl border text-left transition flex items-center justify-between ${
                state.activePdpDeliveryMethod === "home"
                  ? "bg-emerald-deep text-white border-gold-reflective shadow-sm"
                  : "bg-white text-charcoal border-gray-200 hover:border-emerald-deep"
              }"
            >
              <div>
                <div class="font-bold text-[11px]">${L("À Domicile", "إلى المنزل", "Home")}</div>
                <div class="text-[10px] ${state.activePdpDeliveryMethod === "home" ? "text-gold-light/85" : "text-gray-500"}">${L("Livraison chez vous", "التوصيل إلى بيتكم", "Delivered to you")}</div>
              </div>
              <span class="font-extrabold text-xs ${state.activePdpDeliveryMethod === "home" ? "text-gold-reflective" : "text-emerald-deep"}">${deliveryFeeText(selWilaya, "home", merchTotal)}</span>
            </button>
            <button
              type="button"
              onclick="changePdpDeliveryMethod('stop_desk')"
              class="p-2 rounded-xl border text-left transition flex items-center justify-between ${
                state.activePdpDeliveryMethod === "stop_desk"
                  ? "bg-emerald-deep text-white border-gold-reflective shadow-sm"
                  : "bg-white text-charcoal border-gray-200 hover:border-emerald-deep"
              }"
            >
              <div>
                <div class="font-bold text-[11px]">Stop-Desk</div>
                <div class="text-[10px] ${state.activePdpDeliveryMethod === "stop_desk" ? "text-gold-light/85" : "text-gray-500"}">${L("Bureau relais", "مكتب الاستلام", "Pick-up office")}</div>
              </div>
              <span class="font-extrabold text-xs ${state.activePdpDeliveryMethod === "stop_desk" ? "text-gold-reflective" : "text-emerald-deep"}">${deliveryFeeText(selWilaya, "stop_desk", merchTotal)}</span>
            </button>
          </div>
          <div class="flex items-center justify-between pt-1.5 border-t border-emerald-deep/15 text-[11px]">
            <span class="text-charcoal/80">${L("Total estimé", "المجموع التقديري", "Estimated total")} (${state.activePdpQty} ${L("article" + (state.activePdpQty > 1 ? "s" : ""), "قطعة", "item" + (state.activePdpQty > 1 ? "s" : ""))} + ${state.activePdpDeliveryMethod === "stop_desk" ? "Stop-Desk" : L("Domicile", "المنزل", "Home")}) :</span>
            <strong class="text-sm font-extrabold text-emerald-deep">${formatDZD(merchTotal + deliveryFeeFor(selWilaya, state.activePdpDeliveryMethod, merchTotal))}${feesKnown(selWilaya) ? "" : " + livraison"}</strong>
          </div>
        </div>

        <!-- Specifications & Delivery Tabs -->
        <div class="pt-2 border-t border-gray-100 space-y-2.5">
          <div class="flex gap-2 text-xs font-bold">
            <button type="button" onclick="switchPdpTab('desc')" class="px-3 py-1.5 rounded-lg ${
              state.activePdpTab === "desc" ? "bg-cream text-emerald-deep border border-gold-reflective/40" : "text-gray-500"
            }">${L("Caractéristiques techniques", "المواصفات", "Specifications")}</button>
            <button type="button" onclick="switchPdpTab('ship')" class="px-3 py-1.5 rounded-lg ${
              state.activePdpTab === "ship" ? "bg-cream text-emerald-deep border border-gold-reflective/40" : "text-gray-500"
            }">${L("Livraison &amp; Retours", "التوصيل والإرجاع", "Delivery &amp; returns")}</button>
          </div>
          ${
            state.activePdpTab === "desc"
              ? `<table class="w-full">${specRows}</table>`
              : `<div class="text-xs text-charcoal/80 space-y-1 bg-cream p-3 rounded-xl border border-gold-reflective/25">
                  <p class="font-bold text-emerald-deep">${L("Expédition rapide dans les 69 Wilayas d'Algérie", "شحن سريع إلى 69 ولاية في الجزائر", "Fast shipping to all 69 wilayas of Algeria")}</p>
                  <p>${L("Paiement en espèces à la réception (Cash on Delivery) • Échange ou retour sous 7 jours.", "الدفع نقدًا عند الاستلام • الاستبدال أو الإرجاع خلال 7 أيام.", "Cash on delivery • Exchange or return within 7 days.")}</p>
                </div>`
          }
        </div>
      </div>
    </div>
  `;
}

function addPdpToCart(buyNow) {
  const prod = state.products.find((p) => p.id === state.activePdpProductId);
  if (!prod) return;

  if (state.activePdpQty > 1 && state.activePdpMultiVariantMode === "split") {
    const totalAllocated = Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0);
    if (totalAllocated !== state.activePdpQty) {
      showToast(`Veuillez répartir l'intégralité des ${state.activePdpQty} articles (actuellement ${totalAllocated})`, "error");
      return;
    }

    // Check every line first: either the whole selection goes into the
    // cart, or nothing does and the window stays open.
    const lines = Object.entries(state.activePdpAllocations).filter(([, q]) => q > 0);
    for (const [vIdStr, qty] of lines) {
      const v = prod.variants.find((x) => x.id === Number(vIdStr));
      const inCart = (state.cart.find((c) => c.variantId === Number(vIdStr)) || {}).quantity || 0;
      if (!v || v.stock <= 0 || inCart + qty > v.stock) {
        showToast(`${L("Quantité disponible pour", "الكمية المتوفرة لـ", "Available quantity for")} ${v ? v.title : ""} : ${v ? Math.max(0, v.stock - inCart) : 0}`, "error");
        return;
      }
    }
    let totalAdded = 0;
    for (const [vIdStr, qty] of lines) {
      if (addToCartInternal(prod.id, Number(vIdStr), qty, false)) totalAdded += qty;
    }
    showToast(L(`${totalAdded} articles (${prodName(prod)}) répartis ajoutés au panier !`, `تمت إضافة ${totalAdded} قطع (${prodName(prod)}) إلى السلة`, `${totalAdded} items (${prodName(prod)}) added to the cart`));
    closeProductDetailModal();
    if (buyNow) openCartDrawer();
  } else {
    const variant = prod.variants.find((v) => v.id === state.activePdpVariantId);
    if (!variant || variant.stock < state.activePdpQty) {
      showToast(`Stock insuffisant pour cette déclinaison (disponible : ${variant ? variant.stock : 0})`, "error");
      return;
    }
    // Kept open when it was refused (e.g. the cart already holds the rest of
    // the stock); the toast explains why.
    if (!addToCartInternal(prod.id, state.activePdpVariantId, state.activePdpQty, true)) return;
    closeProductDetailModal();
    if (buyNow) openCartDrawer();
  }
}

// ========================================================================

Object.assign(window, {
  isProductModalOpen,
  hideProductModal,
  openProductBySlug,
  openProductDetailModal,
  closeProductDetailModal,
  selectPdpAxisValue,
  selectPdpVariant,
  changePdpWilayaEstimate,
  changePdpDeliveryMethod,
  setPdpMultiVariantMode,
  changeVariantAllocation,
  changePdpQty,
  switchPdpImage,
  togglePdpZoom,
  switchPdpTab,
  renderPdpModalContent,
  addPdpToCart,
});
