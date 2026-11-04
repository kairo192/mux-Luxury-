import re

sf_path = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\apps\storefront\index.html"

with open(sf_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add activePdpMultiVariantMode and activePdpAllocations to state
old_state = """      activePdpProductId: null,
      activePdpVariantId: null,
      activePdpQty: 1,
      activePdpTab: "desc"
    };"""

new_state = """      activePdpProductId: null,
      activePdpVariantId: null,
      activePdpQty: 1,
      activePdpTab: "desc",
      activePdpMultiVariantMode: "same",
      activePdpAllocations: {}
    };"""

assert old_state in code, "old_state not found"
code = code.replace(old_state, new_state, 1)
print("1. Added activePdpMultiVariantMode & activePdpAllocations to state.")

# 2. Update openProductDetailModal to reset multi-variant state
old_open_pdp = """      state.activePdpQty = 1;
      state.activePdpTab = "desc";

      const cat = state.categories.find((c) => c.id === prod.category_id);"""

new_open_pdp = """      state.activePdpQty = 1;
      state.activePdpMultiVariantMode = "same";
      state.activePdpAllocations = {};
      state.activePdpTab = "desc";

      const cat = state.categories.find((c) => c.id === prod.category_id);"""

assert old_open_pdp in code, "old_open_pdp not found"
code = code.replace(old_open_pdp, new_open_pdp, 1)
print("2. Updated openProductDetailModal.")

# 3. Add setPdpMultiVariantMode, changeVariantAllocation and update changePdpQty
old_change_qty = """    function changePdpQty(delta) {
      const prod = state.products.find((p) => p.id === state.activePdpProductId);
      const variant = prod ? prod.variants.find((v) => v.id === state.activePdpVariantId) : null;
      const maxStock = variant ? variant.stock : 1;
      const next = state.activePdpQty + delta;
      if (next >= 1 && next <= Math.max(1, maxStock)) {
        state.activePdpQty = next;
        renderPdpModalContent();
      }
    }"""

new_change_qty = """    function setPdpMultiVariantMode(mode) {
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
    }"""

assert old_change_qty in code, "old_change_qty not found"
code = code.replace(old_change_qty, new_change_qty, 1)
print("3. Added setPdpMultiVariantMode, changeVariantAllocation, updated changePdpQty.")

# 4. Update addPdpToCart and addToCartInternal
old_add_cart = """    function addPdpToCart(buyNow) {
      const prod = state.products.find((p) => p.id === state.activePdpProductId);
      if (!prod) return;
      addToCartInternal(prod.id, state.activePdpVariantId, state.activePdpQty);
      closeProductDetailModal();
      if (buyNow) {
        openCartDrawer();
      }
    }

    // ========================================================================
    // CART & GUEST CHECKOUT
    // ========================================================================
    function quickAddToCart(prodId, variantId) {
      addToCartInternal(prodId, variantId, 1);
    }

    function addToCartInternal(prodId, variantId, qty) {
      const prod = state.products.find((p) => p.id === prodId);
      if (!prod) return;
      const variant = prod.variants.find((v) => v.id === variantId);
      if (!variant || variant.stock <= 0) {
        showToast("Cette variante est momentanément indisponible", "error");
        return;
      }
      const existing = state.cart.find((item) => item.variantId === variantId);
      const currentQty = existing ? existing.quantity : 0;
      if (currentQty + qty > variant.stock) {
        showToast(`Quantité disponible pour ${variant.title} : ${variant.stock}`, "error");
        return;
      }
      if (existing) {
        existing.quantity += qty;
      } else {
        state.cart.push({ variantId, productId: prodId, quantity: qty });
      }
      state.lastConfirmedOrder = null;
      renderStorefront();
      showToast(`${prodName(prod)} (${variant.title}) ajouté au panier`);
    }"""

new_add_cart = """    function addPdpToCart(buyNow) {
      const prod = state.products.find((p) => p.id === state.activePdpProductId);
      if (!prod) return;

      if (state.activePdpQty > 1 && state.activePdpMultiVariantMode === "split") {
        const totalAllocated = Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0);
        if (totalAllocated !== state.activePdpQty) {
          showToast(`Veuillez répartir l'intégralité des ${state.activePdpQty} articles (actuellement ${totalAllocated})`, "error");
          return;
        }

        let totalAdded = 0;
        for (const [vIdStr, qty] of Object.entries(state.activePdpAllocations)) {
          if (qty > 0) {
            addToCartInternal(prod.id, Number(vIdStr), qty, false);
            totalAdded += qty;
          }
        }
        showToast(`${totalAdded} articles (${prodName(prod)}) répartis ajoutés au panier !`);
        closeProductDetailModal();
        if (buyNow) openCartDrawer();
      } else {
        const variant = prod.variants.find((v) => v.id === state.activePdpVariantId);
        if (!variant || variant.stock < state.activePdpQty) {
          showToast(`Stock insuffisant pour cette déclinaison (disponible : ${variant ? variant.stock : 0})`, "error");
          return;
        }
        addToCartInternal(prod.id, state.activePdpVariantId, state.activePdpQty, true);
        closeProductDetailModal();
        if (buyNow) openCartDrawer();
      }
    }

    // ========================================================================
    // CART & GUEST CHECKOUT
    // ========================================================================
    function quickAddToCart(prodId, variantId) {
      addToCartInternal(prodId, variantId, 1, true);
    }

    function addToCartInternal(prodId, variantId, qty, notify = true) {
      const prod = state.products.find((p) => p.id === prodId);
      if (!prod) return;
      const variant = prod.variants.find((v) => v.id === variantId);
      if (!variant || variant.stock <= 0) {
        if (notify) showToast("Cette variante est momentanément indisponible", "error");
        return;
      }
      const existing = state.cart.find((item) => item.variantId === variantId);
      const currentQty = existing ? existing.quantity : 0;
      if (currentQty + qty > variant.stock) {
        if (notify) showToast(`Quantité disponible pour ${variant.title} : ${variant.stock}`, "error");
        return;
      }
      if (existing) {
        existing.quantity += qty;
      } else {
        state.cart.push({ variantId, productId: prodId, quantity: qty });
      }
      state.lastConfirmedOrder = null;
      renderStorefront();
      if (notify) showToast(`${prodName(prod)} (${variant.title}) ajouté au panier`);
    }"""

assert old_add_cart in code, "old_add_cart not found"
code = code.replace(old_add_cart, new_add_cart, 1)
print("4. Updated addPdpToCart and addToCartInternal.")

# 5. Update renderPdpModalContent to render Scenario B prompt & allocation table
old_selectors_and_cta = """            <!-- Dynamic Variant Axes Selectors (Couleur, Taille, Pointure, Teinte, etc.) -->
            <div class="space-y-3.5 pt-3 border-t border-gray-100">
              ${axesSelectorsHtml}
            </div>

            <!-- Quantity & CTA Buttons -->
            <div class="space-y-3 pt-2">
              <div class="flex items-center gap-3">
                <span class="text-xs font-bold">Quantité :</span>
                <div class="inline-flex items-center rounded-xl border border-gray-300 bg-white">
                  <button type="button" onclick="changePdpQty(-1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">-</button>
                  <span class="px-4 py-1.5 text-xs font-extrabold">${state.activePdpQty}</span>
                  <button type="button" onclick="changePdpQty(1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">+</button>
                </div>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onclick="addPdpToCart(false)"
                  ${varStock <= 0 ? "disabled" : ""}
                  class="py-3 px-4 rounded-xl gold-cta text-emerald-forest font-extrabold text-xs uppercase tracking-wider shadow-md flex items-center justify-center gap-2 transition"
                >
                  <svg class="w-4 h-4 stroke-[2.2]" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>
                  <span>Ajouter au panier</span>
                </button>
                <button
                  type="button"
                  onclick="addPdpToCart(true)"
                  ${varStock <= 0 ? "disabled" : ""}
                  class="py-3 px-4 rounded-xl bg-emerald-deep hover:bg-emerald-forest text-gold-light border border-gold-reflective/40 font-bold text-xs uppercase tracking-wider transition"
                >
                  Acheter maintenant
                </button>
              </div>"""

new_selectors_and_cta = """            <!-- Quantity Selector & Multi-unit Options Prompt (Scenario A & B) -->
            <div class="space-y-3 pt-2 border-t border-gray-100">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <span class="text-xs font-bold">Quantité :</span>
                  <div class="inline-flex items-center rounded-xl border border-gray-300 bg-white">
                    <button type="button" onclick="changePdpQty(-1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">-</button>
                    <span class="px-4 py-1.5 text-xs font-extrabold">${state.activePdpQty}</span>
                    <button type="button" onclick="changePdpQty(1)" class="px-3 py-1.5 text-sm font-bold hover:bg-gray-100">+</button>
                  </div>
                </div>
                ${state.activePdpQty >= 2 && prod.variants.length > 1 ? `
                  <span class="text-[11px] font-bold text-emerald-deep">Choix multi-unités activé</span>
                ` : ""}
              </div>

              <!-- Scenario B Prompt: When selecting 2+ units on a product with multiple variants -->
              ${state.activePdpQty >= 2 && prod.variants.length > 1 ? `
                <div class="p-3 rounded-xl bg-amber-500/10 border border-gold-reflective/40 space-y-2">
                  <p class="text-xs font-bold text-emerald-deep">
                    Vous souhaitez ${state.activePdpQty} articles. Voulez-vous la même déclinaison ou des options différentes ?
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
                      ✓ Mêmes options
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
                      ⚡ Choisir séparément
                    </button>
                  </div>
                </div>
              ` : ""}

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
                        ✓ Répartition complète (${state.activePdpQty}/${state.activePdpQty})
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
                  <span>Ajouter au panier</span>
                </button>
                <button
                  type="button"
                  onclick="addPdpToCart(true)"
                  ${(state.activePdpMultiVariantMode === 'split' ? (Object.values(state.activePdpAllocations).reduce((a, b) => a + b, 0) !== state.activePdpQty) : varStock < state.activePdpQty) ? "disabled" : ""}
                  class="py-3 px-4 rounded-xl bg-emerald-deep hover:bg-emerald-forest text-gold-light border border-gold-reflective/40 font-bold text-xs uppercase tracking-wider transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Acheter maintenant
                </button>
              </div>"""

assert old_selectors_and_cta in code, "old_selectors_and_cta not found"
code = code.replace(old_selectors_and_cta, new_selectors_and_cta, 1)
print("5. Integrated Scenario B multi-unit options prompt & allocation table into PDP modal.")

# 6. Enhance Cart items display with variant swatches & title
old_cart_item = """                <p class="font-bold text-xs text-charcoal truncate">${prodName(prod)}</p>
                <p class="text-[11px] text-gray-500">${variant.title}</p>
                <p class="text-xs font-extrabold text-emerald-deep mt-0.5">${formatDZD(unitPrice)}</p>"""

new_cart_item = """                <p class="font-bold text-xs text-charcoal truncate">${prodName(prod)}</p>
                <div class="flex items-center gap-1.5 mt-0.5">
                  ${(() => {
                    const colorVal = variant.attrs ? (variant.attrs.color || variant.attrs.couleur || Object.values(variant.attrs).find(v => COLOR_SWATCH_HEX[v])) : null;
                    const hex = colorVal ? (COLOR_SWATCH_HEX[colorVal] || null) : null;
                    return hex ? `<span class="w-3 h-3 rounded-full border border-black/20 shrink-0" style="background-color:${hex}"></span>` : "";
                  })()}
                  <span class="text-[11px] text-gray-600 font-semibold truncate">${variant.title}</span>
                </div>
                <p class="text-xs font-extrabold text-emerald-deep mt-0.5">${formatDZD(unitPrice)}</p>"""

assert old_cart_item in code, "old_cart_item not found"
code = code.replace(old_cart_item, new_cart_item, 1)
print("6. Enhanced cart drawer with variant color swatches and clear labels.")

with open(sf_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(code)

print("Saved all storefront multi-variant selection features successfully!")
