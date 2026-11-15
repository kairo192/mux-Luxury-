// Cart and guest checkout (cash on delivery).
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// CART & GUEST CHECKOUT
// ========================================================================
function quickAddToCart(prodId, variantId) {
  addToCartInternal(prodId, variantId, 1, true);
}

function addToCartInternal(prodId, variantId, qty, notify = true) {
  const prod = state.products.find((p) => p.id === prodId);
  if (!prod) return false;
  const variant = prod.variants.find((v) => v.id === variantId);
  if (!variant || variant.stock <= 0) {
    if (notify) showToast("Cette variante est momentanément indisponible", "error");
    return false;
  }
  const existing = state.cart.find((item) => item.variantId === variantId);
  const currentQty = existing ? existing.quantity : 0;
  if (currentQty + qty > variant.stock) {
    if (notify) showToast(`Quantité disponible pour ${variant.title} : ${variant.stock}`, "error");
    return false;
  }
  if (existing) {
    existing.quantity += qty;
    noteCartChangeWhileOrdering(existing, qty);
  } else {
    state.cart.push({ variantId, productId: prodId, quantity: qty });
  }
  saveCartToStorage();
  state.lastConfirmedOrder = null;
  renderStorefront();
  if (notify) showToast(`${prodName(prod)} (${variant.title}) ${L("ajouté au panier", "أُضيف إلى السلة", "added to the cart")}`);
  return true;
}

// While an order is being sent, its lines count what the customer adds on top
// (`addedWhileOrdering`): removing pieces takes from those additions first.
// When the order is confirmed, the line keeps the additions and whatever is
// left of the ordered part beyond what the shop recorded.
function noteCartChangeWhileOrdering(line, delta) {
  if (line.addedWhileOrdering === undefined) return;
  line.addedWhileOrdering = Math.max(0, line.addedWhileOrdering + delta);
}

function updateCartItemQty(variantId, delta) {
  const idx = state.cart.findIndex((i) => i.variantId === variantId);
  if (idx === -1) return;
  const item = state.cart[idx];
  const prod = state.products.find((p) => p.id === item.productId);
  const variant = prod ? prod.variants.find((v) => v.id === variantId) : null;
  const next = item.quantity + delta;
  if (next <= 0) {
    state.cart.splice(idx, 1);
  } else if (variant && next <= variant.stock) {
    item.quantity = next;
    noteCartChangeWhileOrdering(item, delta);
  } else {
    showToast("Quantité maximale en stock atteinte", "error");
  }
  saveCartToStorage();
  renderStorefront();
  renderCartDrawerContent();
}

function openCartDrawer() {
  renderCartDrawerContent();
  document.getElementById("cart-checkout-modal").classList.remove("hidden");
}

function closeCartDrawer() {
  document.getElementById("cart-checkout-modal").classList.add("hidden");
}

function computeCartSubtotal() {
  return state.cart.reduce((sum, item) => {
    const prod = state.products.find((p) => p.id === item.productId);
    const variant = prod ? prod.variants.find((v) => v.id === item.variantId) : null;
    const unitPrice = variant && variant.price ? variant.price : prod ? prod.selling_price_dzd : 0;
    return sum + unitPrice * item.quantity;
  }, 0);
}

function computeCouponDiscount(subtotal) {
  if (!state.appliedCoupon) return 0;
  const c = state.appliedCoupon;
  if (subtotal < c.minOrder) return 0;
  if (c.type === "percentage") {
    return Math.min(Math.floor((subtotal * c.value) / 100), c.maxDiscount || 999999);
  }
  return Math.min(c.value, subtotal);
}

async function applyGuestCheckoutCoupon() {
  const raw = (document.getElementById("chk-coupon")?.value || "").trim().toUpperCase();
  if (!raw) {
    state.appliedCoupon = null;
    updateCheckoutCalculation();
    return;
  }
  const subtotal = computeCartSubtotal();
  try {
    const cpnData = await fetchPublicJson("/api/v1/coupons/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: raw, subtotal_dzd: subtotal }),
    });
    state.appliedCoupon = {
      code: cpnData.code,
      type: cpnData.discount_type,
      value: cpnData.discount_value,
      minOrder: 0,
      maxDiscount: cpnData.discount_dzd,
    };
    updateCheckoutCalculation();
    showToast(`Code promo ${cpnData.code} appliqué (-${formatDZD(cpnData.discount_dzd)})`);
    return;
  } catch (_e) { /* fall through to the local COUPONS fixture below */ }
  const found = COUPONS.find((c) => c.code === raw);
  if (!found) {
    showToast("Code promo invalide", "error");
    return;
  }
  if (subtotal < found.minOrder) {
    showToast(`Minimum de commande requis : ${formatDZD(found.minOrder)}`, "error");
    return;
  }
  state.appliedCoupon = found;
  updateCheckoutCalculation();
  showToast(`Code promo ${found.code} appliqué`);
}

function selectCheckoutDeliveryMethod(method) {
  const wObj = WILAYAS.find((w) => w.code === state.checkoutWilaya);
  if (wObj && !methodAvailable(wObj, method)) return;
  state.checkoutMethod = method === "stop_desk" ? "stop_desk" : "home";
  const methodInput = document.getElementById("chk-method");
  if (methodInput) methodInput.value = state.checkoutMethod;
  updateCheckoutCalculation();
}

function updateCheckoutCalculation() {
  const wilayaSel = document.getElementById("chk-wilaya");
  const methodInput = document.getElementById("chk-method");
  const communeSel = document.getElementById("chk-commune");
  if (!wilayaSel || !methodInput) return;

  state.checkoutWilaya = wilayaSel.value;
  state.checkoutMethod = methodInput.value === "stop_desk" ? "stop_desk" : "home";

  const wObj = WILAYAS.find((w) => w.code === state.checkoutWilaya) || WILAYAS[15] || WILAYAS[0];
  if (communeSel && communeSel.dataset.wilaya !== wObj.code) {
    communeSel.dataset.wilaya = wObj.code;
    communeSel.innerHTML = wObj.communes.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  }

  // Update live prices and Wilaya labels inside the Home vs Stop-Desk selector cards
  const homeFeeBadge = document.getElementById("chk-card-home-fee");
  const deskFeeBadge = document.getElementById("chk-card-desk-fee");
  const homeWilayaSub = document.getElementById("chk-card-home-sub");
  const deskWilayaSub = document.getElementById("chk-card-desk-sub");
  const homeCardBtn = document.getElementById("chk-card-home-btn");
  const deskCardBtn = document.getElementById("chk-card-desk-btn");

  // Switch to the method this wilaya offers when the chosen one is off.
  if (!methodAvailable(wObj, state.checkoutMethod)) {
    const other = state.checkoutMethod === "home" ? "stop_desk" : "home";
    if (methodAvailable(wObj, other)) {
      state.checkoutMethod = other;
      methodInput.value = other;
    }
  }
  const homeOk = methodAvailable(wObj, "home");
  const deskOk = methodAvailable(wObj, "stop_desk");
  const cartSubtotal = computeCartSubtotal();
  if (homeFeeBadge) homeFeeBadge.textContent = deliveryFeeText(wObj, "home", cartSubtotal, "+ ");
  if (deskFeeBadge) deskFeeBadge.textContent = deliveryFeeText(wObj, "stop_desk", cartSubtotal, "+ ");
  if (homeWilayaSub) homeWilayaSub.textContent = `${L("À votre adresse", "إلى عنوانكم", "To your address")} (${wObj.code} - ${wilayaName(wObj)})`;
  if (deskWilayaSub) deskWilayaSub.textContent = `${L("Bureau relais", "مكتب الاستلام", "Pick-up office")} (${wObj.code} - ${wilayaName(wObj)})`;

  if (homeCardBtn && deskCardBtn) {
    if (state.checkoutMethod === "home") {
      homeCardBtn.className = "p-3 rounded-xl border-2 border-gold-reflective bg-emerald-deep text-white text-left transition shadow-sm flex items-center justify-between gap-2";
      deskCardBtn.className = "p-3 rounded-xl border border-gray-300 bg-white text-charcoal hover:border-emerald-deep text-left transition flex items-center justify-between gap-2";
      if (homeFeeBadge) homeFeeBadge.className = "font-extrabold text-xs text-gold-reflective whitespace-nowrap";
      if (deskFeeBadge) deskFeeBadge.className = "font-extrabold text-xs text-emerald-deep whitespace-nowrap";
      if (homeWilayaSub) homeWilayaSub.className = "text-[10px] text-gold-light/85 truncate";
      if (deskWilayaSub) deskWilayaSub.className = "text-[10px] text-gray-500 truncate";
    } else {
      deskCardBtn.className = "p-3 rounded-xl border-2 border-gold-reflective bg-emerald-deep text-white text-left transition shadow-sm flex items-center justify-between gap-2";
      homeCardBtn.className = "p-3 rounded-xl border border-gray-300 bg-white text-charcoal hover:border-emerald-deep text-left transition flex items-center justify-between gap-2";
      if (deskFeeBadge) deskFeeBadge.className = "font-extrabold text-xs text-gold-reflective whitespace-nowrap";
      if (homeFeeBadge) homeFeeBadge.className = "font-extrabold text-xs text-emerald-deep whitespace-nowrap";
      if (deskWilayaSub) deskWilayaSub.className = "text-[10px] text-gold-light/85 truncate";
      if (homeWilayaSub) homeWilayaSub.className = "text-[10px] text-gray-500 truncate";
    }
    homeCardBtn.disabled = !homeOk;
    deskCardBtn.disabled = !deskOk;
    homeCardBtn.classList.toggle("opacity-40", !homeOk);
    deskCardBtn.classList.toggle("opacity-40", !deskOk);
  }

  const subtotal = computeCartSubtotal();
  const fee = deliveryFeeFor(wObj, state.checkoutMethod, subtotal);
  const discount = computeCouponDiscount(subtotal);
  const total = subtotal - discount + fee;

  const feeLabelEl = document.getElementById("chk-summary-fee-label");
  const feeEl = document.getElementById("chk-summary-fee");
  const discEl = document.getElementById("chk-summary-discount");
  const totEl = document.getElementById("chk-summary-total");
  if (feeLabelEl) {
    feeLabelEl.textContent = `${L("Livraison", "التوصيل", "Delivery")} (${wObj.code} - ${wilayaName(wObj)} • ${state.checkoutMethod === "stop_desk" ? "Stop-Desk" : L("À domicile", "إلى المنزل", "Home")}) :`;
  }
  if (feeEl) feeEl.textContent = feesKnown(wObj) ? ltr(`+ ${formatDZD(fee)}`) : deliveryFeeText(wObj, state.checkoutMethod);
  if (discEl) discEl.textContent = discount > 0 ? ltr(`- ${formatDZD(discount)}`) : formatDZD(0);
  if (totEl) totEl.textContent = formatDZD(total) + (feesKnown(wObj) ? "" : L(" + livraison", " + التوصيل", " + delivery"));
}

async function submitGuestCheckoutOrder() {
  const name = (document.getElementById("chk-name")?.value || "").trim();
  const phone = (document.getElementById("chk-phone")?.value || "").trim().replace(/[\s\-\.]/g, "");
  const wilayaCode = document.getElementById("chk-wilaya")?.value || "16";
  const commune = document.getElementById("chk-commune")?.value || "Alger Centre";
  const address = (document.getElementById("chk-address")?.value || "").trim();
  const method = document.getElementById("chk-method")?.value || "home";

  if (name.length < 3) {
    showToast(L("Veuillez indiquer votre nom et prénom", "يرجى إدخال الاسم واللقب", "Please enter your full name"), "error");
    return;
  }
  if (!/^(\+213|0)(5|6|7)[0-9]{8}$/.test(phone)) {
    showToast(L("Numéro de téléphone mobile algérien invalide (ex: 0555 12 34 56)", "رقم الهاتف غير صحيح (مثال: 0555 12 34 56)", "Invalid Algerian mobile number (e.g. 0555 12 34 56)"), "error");
    return;
  }
  if (address.length < 5) {
    showToast(L("Veuillez préciser votre adresse de livraison", "يرجى إدخال عنوان التوصيل", "Please enter your delivery address"), "error");
    return;
  }

  const wObj = WILAYAS.find((w) => w.code === wilayaCode) || WILAYAS[0];
  let serverTotals = null; // totals computed by the server (the truth)
  let subtotal = 0;
  const orderItems = [];

  for (const item of state.cart) {
    const prod = state.products.find((p) => p.id === item.productId);
    const variant = prod ? prod.variants.find((v) => v.id === item.variantId) : null;
    if (!prod || !variant || variant.stock < item.quantity) {
      showToast(`${L("Stock insuffisant pour", "الكمية غير متوفرة لـ", "Not enough stock for")} ${prod ? prodName(prod) : L("cet article", "هذا المنتج", "this item")}`, "error");
      return;
    }
    const unitPrice = variant.price || prod.selling_price_dzd;
    subtotal += unitPrice * item.quantity;
    orderItems.push({
      product_id: prod.id,
      variant_id: variant.id,
      product_name: prod.name_fr,
      variant_title: variant.title,
      unit_price_dzd: unitPrice,
      quantity: item.quantity
    });
  }

  const discount = computeCouponDiscount(subtotal);
  let orderRef = null;
  let recordedItems = orderItems; // what the shop recorded for this order
  // The cart lines as they were when sending: after success, only these exact
  // lines are reduced. A line removed and added again meanwhile is a new line
  // and is left alone; extra pieces added to a line stay in it.
  const sentLines = new Map(state.cart.map((c) => [c.variantId, c]));
  for (const line of sentLines.values()) line.addedWhileOrdering = 0;
  const stopTracking = () => { for (const line of sentLines.values()) delete line.addedWhileOrdering; };

  // One anti-duplicate key per order: a double click or an automatic
  // retry re-sends the SAME key, and the server refuses a second order.
  if (state.placingOrder) return;
  state.placingOrder = true;
  // The key is kept until an order is confirmed: re-using a key that created
  // nothing is harmless, while dropping one too early could let a retry
  // create a second order. `checkoutIdemItems` holds what was sent by the
  // first attempt that got no clear answer (lost connection, server error,
  // too many requests): if the shop later says the key's order exists, that
  // is the order it recorded.
  if (!state.checkoutIdemKey) {
    const rnd = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    state.checkoutIdemKey = `storefront-${rnd}`;
    state.checkoutIdemItems = null;
  }

  try {
    const createdOrd = await fetchPublicJson("/api/v1/orders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": state.checkoutIdemKey,
      },
      body: JSON.stringify({
        full_name: name,
        phone: phone,
        wilaya_code: wilayaCode,
        commune: commune,
        delivery_address: address,
        delivery_method: method,
        coupon_code: state.appliedCoupon ? state.appliedCoupon.code : undefined,
        items: orderItems.map((it) => ({ variant_id: it.variant_id, quantity: it.quantity })),
      }),
    });
    if (createdOrd && createdOrd.order_reference) {
      serverTotals = createdOrd;
      orderRef = createdOrd.order_reference;
    }
  } catch (err) {
    // The first attempt actually reached the shop (e.g. the answer was
    // lost): the server reports the existing order — show it as placed.
    const dupRef = err && err.existingOrderRef;
    if (dupRef) {
      orderRef = dupRef;
      recordedItems = state.checkoutIdemItems || orderItems;
      // The shop's own figures for that order (the reply only carries its
      // number): read them back from order tracking.
      try {
        const rec = await fetchPublicJson(
          `/api/v1/orders/track?reference=${encodeURIComponent(dupRef)}&phone=${encodeURIComponent(phone)}`,
          { method: "GET" }
        );
        if (rec && rec.total_dzd != null) serverTotals = rec;
      } catch (_e) { /* the estimate below is shown instead */ }
    } else {
      // No clear answer: this attempt may have been recorded. Remember what
      // it sent (only the first such attempt; a refusal proves nothing).
      const answered = err && err.status >= 400 && err.status < 500 && err.status !== 429;
      if (!answered && !state.checkoutIdemItems) {
        state.checkoutIdemItems = orderItems.map((it) => ({ ...it }));
      }
      state.placingOrder = false;
      stopTracking();
      showToast(String((err && err.message) || "Erreur lors de l'enregistrement de votre commande."), "error");
      return;
    }
  }
  state.placingOrder = false;
  if (!orderRef) {
    stopTracking();
    // Never show an invented order number.
    showToast(L("La commande n'a pas pu être confirmée. Réessayez ou contactez-nous sur WhatsApp.", "تعذّر تأكيد الطلب. حاولوا مجددًا أو راسلونا عبر واتساب.", "The order could not be confirmed. Please try again or contact us on WhatsApp."), "error");
    return;
  }
  state.checkoutIdemKey = null;
  state.checkoutIdemItems = null;
  const sameAsRecorded = JSON.stringify(recordedItems.map((i) => [i.variant_id, i.quantity]))
    === JSON.stringify(orderItems.map((i) => [i.variant_id, i.quantity]));
  // Stock: re-read from the shop (never subtract from a list that may
  // already include this order); a product removed meanwhile is fine.
  syncStorefrontWithBackend();
  const recSubtotal = recordedItems.reduce((sum, i) => sum + i.unit_price_dzd * i.quantity, 0);
  const recDiscount = sameAsRecorded ? discount : computeCouponDiscount(recSubtotal);

  // What the shop recorded wins over the form: after a lost answer the
  // customer may have changed the wilaya or the delivery method since.
  const rec = serverTotals || {};
  const newOrder = {
    id: state.orders.length + 502,
    reference: orderRef,
    customer_name: rec.customer_name || name,
    customer_phone: phone,
    wilaya_code: rec.wilaya_code || wObj.code,
    wilaya_name: rec.wilaya_name || wObj.name_fr,
    commune: rec.commune || commune,
    address: rec.delivery_address || address,
    delivery_method: rec.delivery_method || method,
    // No figures from the shop (its answer was lost and tracking could not
    // be read): the amounts below are an estimate, and are shown as one.
    estimated: !serverTotals,
    subtotal_dzd: serverTotals ? serverTotals.subtotal_dzd : recSubtotal,
    discount_dzd: serverTotals ? serverTotals.discount_dzd : recDiscount,
    // Show what the server recorded (free delivery, coupon, prices) —
    // the amount the courier will collect.
    delivery_fee_dzd: serverTotals ? serverTotals.delivery_fee_dzd : deliveryFeeFor(wObj, method, recSubtotal),
    total_dzd: serverTotals ? serverTotals.total_dzd : recSubtotal - recDiscount + deliveryFeeFor(wObj, method, recSubtotal),
    status: "Nouvelle — En attente de confirmation téléphonique",
    items: recordedItems
  };

  state.orders.unshift(newOrder);
  // Take out only what this order contained: an article added while the
  // order was being sent stays in the cart.
  for (const it of recordedItems) {
    const line = sentLines.get(it.variant_id);
    if (!line || !state.cart.includes(line)) continue;
    const added = line.addedWhileOrdering || 0;
    const orderedPartLeft = line.quantity - added;
    line.quantity = added + Math.max(0, orderedPartLeft - it.quantity);
  }
  stopTracking();
  state.cart = state.cart.filter((c) => c.quantity > 0);
  saveCartToStorage();
  state.appliedCoupon = null;
  state.lastConfirmedOrder = newOrder;
  renderStorefront();
  renderCartDrawerContent();
  showToast(`${L("Commande", "الطلب", "Order")} ${ltr("#" + orderRef)} ${L("enregistrée", "مسجّل", "placed")}`);
  if (!sameAsRecorded) {
    showToast(L(
      "Votre première demande était déjà enregistrée : seuls ses articles sont commandés. Les autres restent dans le panier.",
      "طلبكم الأول كان مسجّلًا من قبل: تم طلب منتجاته فقط، والباقي ما زال في السلة.",
      "Your first request was already recorded: only its items are ordered. The others stay in your cart."
    ));
  }
}

function resetConfirmedOrder() {
  state.lastConfirmedOrder = null;
  closeCartDrawer();
}

function renderCartDrawerContent() {
  const container = document.getElementById("cart-drawer-body");
  const drawerTitle = document.getElementById("cart-drawer-title");
  const drawerSub = document.getElementById("cart-drawer-sub");
  if (drawerTitle) drawerTitle.textContent = L("Votre Panier", "سلة المشتريات", "Your cart");
  if (drawerSub) drawerSub.textContent = L("Commande directe sans compte • Paiement à la livraison", "طلب مباشر بدون حساب • الدفع عند الاستلام", "Order without an account • Cash on delivery");

  if (state.lastConfirmedOrder) {
    const o = state.lastConfirmedOrder;
    container.innerHTML = `
      <div class="bg-white rounded-2xl p-6 border border-gold-reflective/40 text-center space-y-4 shadow-luxury">
        <div class="w-14 h-14 rounded-full bg-emerald-deep text-gold-reflective mx-auto flex items-center justify-center">
          <svg class="w-7 h-7 stroke-[2.5]" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <h4 class="font-luxury text-2xl font-bold text-emerald-deep">${L("Commande confirmée !", "تم تأكيد طلبك!", "Order confirmed!")}</h4>
        <p class="text-xs text-gray-600">${L("Merci pour votre achat,", "شكرًا على طلبك،", "Thank you for your order,")} <strong>${escapeHtml(o.customer_name)}</strong>.</p>
        <div class="bg-cream p-3.5 rounded-xl border border-gold-reflective/40">
          <p class="text-[11px] uppercase text-gray-500 font-bold">${L("Numéro de commande", "رقم الطلب", "Order number")}</p>
          <p class="font-mono text-lg font-extrabold text-emerald-deep mt-0.5" dir="ltr">#${escapeHtml(o.reference)}</p>
        </div>
        <div class="text-start text-xs space-y-1.5 bg-gray-50 p-4 rounded-xl border border-gray-200">
          <p><strong>${L("Destination :", "الوجهة:", "Destination:")}</strong> ${escapeHtml(o.wilaya_code)} - ${escapeHtml(o.wilaya_name)} (${escapeHtml(o.commune)})</p>
          <p><strong>${L("Mode de livraison :", "طريقة التوصيل:", "Delivery:")}</strong> ${o.delivery_method === "home" ? L("Livraison à domicile", "التوصيل إلى المنزل", "Home delivery") : L("Stop-Desk (Bureau relais)", "مكتب الاستلام (Stop-Desk)", "Stop-Desk (pick-up office)")}</p>
          <p><strong>${L("Paiement :", "الدفع:", "Payment:")}</strong> ${L("Paiement à la livraison (Espèces)", "نقدًا عند الاستلام", "Cash on delivery")}</p>
          <p class="text-sm font-extrabold text-emerald-deep pt-1.5 border-t border-gray-200">${o.estimated
            ? L("Total estimé à la réception :", "المبلغ التقديري عند الاستلام:", "Estimated amount on delivery:")
            : L("Total à payer à la réception :", "المبلغ الواجب دفعه عند الاستلام:", "To pay on delivery:")} ${formatDZD(o.total_dzd)}</p>
          ${o.estimated ? `<p data-estimate-note class="text-[11px] text-amber-800">${L("Le montant exact est dans le suivi de commande (numéro ci-dessus et votre téléphone).", "المبلغ الدقيق متوفر في تتبع الطلب (الرقم أعلاه وهاتفكم).", "The exact amount is in order tracking (number above and your phone).")}</p>` : ""}
        </div>
        <button type="button" onclick="resetConfirmedOrder()" class="w-full py-3 rounded-xl bg-emerald-deep text-gold-reflective font-bold text-xs">
          ${L("Retour à la boutique", "العودة إلى المتجر", "Back to the shop")}
        </button>
      </div>
    `;
    return;
  }

  if (state.cart.length === 0) {
    container.innerHTML = `
      <div class="bg-white rounded-2xl p-8 text-center border border-gold-reflective/25 space-y-3">
        <div class="w-12 h-12 rounded-full bg-cream mx-auto flex items-center justify-center text-emerald-deep">
          <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
        </div>
        <h4 class="font-luxury text-xl font-bold text-emerald-deep">${L("Votre panier est vide", "سلتك فارغة", "Your cart is empty")}</h4>
        <p class="text-xs text-gray-500">${L("Découvrez nos collections et commandez directement sans créer de compte.", "اكتشفوا تشكيلاتنا واطلبوا مباشرة دون إنشاء حساب.", "Discover our collections and order directly, no account needed.")}</p>
        <button type="button" onclick="closeCartDrawer()" class="px-6 py-2.5 rounded-full bg-emerald-deep text-gold-reflective font-bold text-xs">${L("Continuer mes achats", "مواصلة التسوق", "Continue shopping")}</button>
      </div>
    `;
    return;
  }

  const subtotal = computeCartSubtotal();
  const discount = computeCouponDiscount(subtotal);
  const defaultWilaya = WILAYAS.find((w) => w.code === state.checkoutWilaya) || WILAYAS[15] || WILAYAS[0];
  const activeMethod = state.checkoutMethod === "stop_desk" ? "stop_desk" : "home";
  const defaultFee = deliveryFeeFor(defaultWilaya, activeMethod, subtotal);
  const defaultFeeKnown = feesKnown(defaultWilaya);

  const itemsHtml = state.cart
    .map((item) => {
      const prod = state.products.find((p) => p.id === item.productId);
      const variant = prod ? prod.variants.find((v) => v.id === item.variantId) : null;
      if (!prod || !variant) {
        // No longer sold: keep the line visible with a way to remove it, so it
        // never blocks the order out of sight.
        return `
        <div class="flex items-center gap-3 bg-red-50 p-3 rounded-xl border border-red-200">
          <div class="flex-1 min-w-0">
            <p class="font-bold text-xs text-red-800">${prod ? prodName(prod) : L("Article", "منتج", "Item")} — ${L("plus disponible", "لم يعد متوفرًا", "no longer available")}</p>
            <p class="text-[11px] text-red-700">${L("Retirez-le pour valider la commande.", "احذفوه لإتمام الطلب.", "Remove it to place the order.")}</p>
          </div>
          <button type="button" onclick="removeCartLine(${Number(item.variantId)})" class="px-3 py-1.5 rounded-lg bg-white border border-red-300 text-red-700 font-bold text-[11px]">${L("Retirer", "حذف", "Remove")}</button>
        </div>`;
      }
      const unitPrice = variant.price || prod.selling_price_dzd;
      return `
        <div class="flex items-center gap-3 bg-white p-3 rounded-xl border border-gold-reflective/25 shadow-sm">
          <img src="${prod.image}" alt="${prodName(prod)}" class="w-16 h-16 rounded-lg object-cover border border-gray-100" />
          <div class="flex-1 min-w-0">
            <p class="font-bold text-xs text-charcoal truncate">${prodName(prod)}</p>
            <div class="flex items-center gap-1.5 mt-0.5">
              ${(() => {
                const colorVal = variant.attrs ? (variant.attrs.color || variant.attrs.couleur || Object.values(variant.attrs).find(v => COLOR_SWATCH_HEX[v])) : null;
                const hex = colorVal ? (COLOR_SWATCH_HEX[colorVal] || null) : null;
                return hex ? `<span class="w-3 h-3 rounded-full border border-black/20 shrink-0" style="background-color:${hex}"></span>` : "";
              })()}
              <span class="text-[11px] text-gray-600 font-semibold truncate">${variant.title}</span>
            </div>
            <p class="text-xs font-extrabold text-emerald-deep mt-0.5">${formatDZD(unitPrice)}</p>
          </div>
          <div class="flex items-center gap-1.5">
            <button type="button" onclick="updateCartItemQty(${variant.id}, -1)" class="w-7 h-7 rounded-lg bg-cream hover:bg-gray-200 font-bold text-xs">-</button>
            <span class="text-xs font-extrabold px-1">${item.quantity}</span>
            <button type="button" onclick="updateCartItemQty(${variant.id}, 1)" class="w-7 h-7 rounded-lg bg-cream hover:bg-gray-200 font-bold text-xs">+</button>
          </div>
        </div>
      `;
    })
    .join("");

  const freeShipThreshold = freeDeliveryThreshold();
  const remainingForFree = freeShipThreshold ? Math.max(0, freeShipThreshold - subtotal) : 0;
  const freeShipPct = freeShipThreshold ? Math.min(100, Math.round((subtotal / freeShipThreshold) * 100)) : 0;

  // What the customer already typed survives a re-render (quantity change,
  // tariff chosen in the tariff window).
  const typed = {};
  for (const id of ["chk-name", "chk-phone", "chk-address", "chk-coupon"]) {
    const el = document.getElementById(id);
    if (el) typed[id] = el.value;
  }
  const typedCommune = document.getElementById("chk-commune")?.value;

  container.innerHTML = `
    ${freeShipThreshold > 0 ? `
    <div class="p-3.5 rounded-xl bg-emerald-deep text-white border border-gold-reflective/40 space-y-2 shadow-sm">
      <div class="flex items-center justify-between text-[11px]">
        <span class="font-semibold text-gold-light">
          ${
            remainingForFree === 0
              ? L(`Livraison Prioritaire Offerte débloquée (Commande ≥ ${formatDZD(freeShipThreshold)})`, `التوصيل مجاني لطلبكم (طلب ≥ ${formatDZD(freeShipThreshold)})`, `Free delivery unlocked (order ≥ ${formatDZD(freeShipThreshold)})`)
              : L(`Plus que <strong class="text-gold-reflective">${formatDZD(remainingForFree)}</strong> pour la Livraison Gratuite (69 Wilayas)`, `بقي <strong class="text-gold-reflective">${formatDZD(remainingForFree)}</strong> للحصول على التوصيل المجاني (69 ولاية)`, `Only <strong class="text-gold-reflective">${formatDZD(remainingForFree)}</strong> more for free delivery (69 wilayas)`)
          }
        </span>
        <span class="font-mono font-bold text-gold-reflective">${freeShipPct}%</span>
      </div>
      <div class="w-full h-2 rounded-full bg-emerald-forest overflow-hidden border border-gold-reflective/25">
        <div class="h-full gold-cta transition-all duration-500" style="width: ${freeShipPct}%"></div>
      </div>
    </div>` : ""}

    <div class="space-y-2.5">
      <h4 class="font-bold text-xs uppercase tracking-wider text-emerald-deep">${L("Articles", "المنتجات", "Items")} (${state.cart.length})</h4>
      ${itemsHtml}
    </div>

    <div class="bg-white rounded-2xl p-5 border border-gold-reflective/35 shadow-sm space-y-4">
      <div class="border-b border-gray-100 pb-2.5">
        <h4 class="font-luxury text-lg font-bold text-emerald-deep">${L("Informations de livraison", "معلومات التوصيل", "Delivery details")}</h4>
        <p class="text-[11px] text-gray-500">${L("Veuillez remplir vos informations pour la livraison en Algérie", "يرجى ملء معلوماتكم للتوصيل داخل الجزائر", "Fill in your details for delivery in Algeria")}</p>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <label for="chk-name" class="block font-bold mb-1">${L("Nom complet", "الاسم الكامل", "Full name")} *</label>
          <input type="text" id="chk-name" autocomplete="name" placeholder="${L("Votre nom et prénom", "الاسم واللقب", "First and last name")}" class="w-full px-3.5 py-2.5 rounded-xl border border-gray-300 focus:outline-none focus:border-emerald-deep" />
        </div>
        <div>
          <label for="chk-phone" class="block font-bold mb-1">${L("Téléphone", "رقم الهاتف", "Phone")} *</label>
          <input type="tel" id="chk-phone" dir="ltr" inputmode="tel" autocomplete="tel" placeholder="05 XX XX XX XX" class="w-full px-3.5 py-2.5 rounded-xl border border-gray-300 font-mono focus:outline-none focus:border-emerald-deep" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <div class="flex items-center justify-between mb-1">
              <label for="chk-wilaya" class="block font-bold">${L("Wilaya (69 Wilayas)", "الولاية", "Wilaya")} *</label>
              <button type="button" onclick="openWilayaTariffsModal()" class="text-[10px] font-bold text-emerald-deep underline hover:text-gold-dark">${L("Voir grille tarifs", "أسعار التوصيل", "Delivery prices")}</button>
            </div>
            <select id="chk-wilaya" onchange="updateCheckoutCalculation()" class="w-full px-3 py-2.5 rounded-xl border border-gray-300 bg-white font-semibold focus:outline-none focus:border-emerald-deep">
              ${WILAYAS.map((w) => `<option value="${w.code}" ${w.code === defaultWilaya.code ? "selected" : ""}>${w.code} - ${wilayaName(w)} ${feesKnown(w) ? ` (${L("Dom", "منزل", "Home")}: ${deliveryFeeText(w, "home", subtotal)} | ${L("Desk", "مكتب", "Desk")}: ${deliveryFeeText(w, "stop_desk", subtotal)})` : ""}</option>`).join("")}
            </select>
          </div>
          <div>
            <label for="chk-commune" class="block font-bold mb-1">${L("Commune", "البلدية", "Commune")} *</label>
            <select id="chk-commune" data-wilaya="${defaultWilaya.code}" class="w-full px-3 py-2.5 rounded-xl border border-gray-300 bg-white focus:outline-none focus:border-emerald-deep">
              ${defaultWilaya.communes.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("")}
            </select>
          </div>
        </div>
        <div>
          <label class="block font-bold mb-1.5">${L("Mode de livraison (calcul automatique selon la Wilaya)", "طريقة التوصيل (السعر حسب الولاية)", "Delivery method (priced by wilaya)")} *</label>
          <input type="hidden" id="chk-method" value="${activeMethod}" />
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <button
              type="button"
              id="chk-card-home-btn"
              onclick="selectCheckoutDeliveryMethod('home')"
              class="${
                activeMethod === "home"
                  ? "p-3 rounded-xl border-2 border-gold-reflective bg-emerald-deep text-white text-left transition shadow-sm flex items-center justify-between gap-2"
                  : "p-3 rounded-xl border border-gray-300 bg-white text-charcoal hover:border-emerald-deep text-left transition flex items-center justify-between gap-2"
              }"
            >
              <div class="min-w-0">
                <div class="font-bold text-xs flex items-center gap-1.5">
                  <svg class="w-3.5 h-3.5 flex-shrink-0 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
                  <span>${L("À Domicile", "إلى المنزل", "Home")}</span>
                </div>
                <div id="chk-card-home-sub" class="text-[10px] ${activeMethod === "home" ? "text-gold-light/85" : "text-gray-500"} truncate">${L("À votre adresse", "إلى عنوانكم", "To your address")} (${defaultWilaya.code} - ${wilayaName(defaultWilaya)})</div>
              </div>
              <span id="chk-card-home-fee" class="font-extrabold text-xs ${activeMethod === "home" ? "text-gold-reflective" : "text-emerald-deep"} whitespace-nowrap">${deliveryFeeText(defaultWilaya, "home", subtotal, "+ ")}</span>
            </button>

            <button
              type="button"
              id="chk-card-desk-btn"
              onclick="selectCheckoutDeliveryMethod('stop_desk')"
              class="${
                activeMethod === "stop_desk"
                  ? "p-3 rounded-xl border-2 border-gold-reflective bg-emerald-deep text-white text-left transition shadow-sm flex items-center justify-between gap-2"
                  : "p-3 rounded-xl border border-gray-300 bg-white text-charcoal hover:border-emerald-deep text-left transition flex items-center justify-between gap-2"
              }"
            >
              <div class="min-w-0">
                <div class="font-bold text-xs flex items-center gap-1.5">
                  <svg class="w-3.5 h-3.5 flex-shrink-0 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>
                  <span>Stop-Desk</span>
                </div>
                <div id="chk-card-desk-sub" class="text-[10px] ${activeMethod === "stop_desk" ? "text-gold-light/85" : "text-gray-500"} truncate">${L("Bureau relais", "مكتب الاستلام", "Pick-up office")} (${defaultWilaya.code} - ${wilayaName(defaultWilaya)})</div>
              </div>
              <span id="chk-card-desk-fee" class="font-extrabold text-xs ${activeMethod === "stop_desk" ? "text-gold-reflective" : "text-emerald-deep"} whitespace-nowrap">${deliveryFeeText(defaultWilaya, "stop_desk", subtotal, "+ ")}</span>
            </button>
          </div>
        </div>
        <div>
          <label for="chk-address" class="block font-bold mb-1">${L("Adresse complète", "العنوان الكامل", "Full address")} *</label>
          <input type="text" id="chk-address" autocomplete="street-address" placeholder="${L("Votre adresse complète", "الحي، الشارع، رقم المنزل", "District, street, house number")}" class="w-full px-3.5 py-2.5 rounded-xl border border-gray-300 focus:outline-none focus:border-emerald-deep" />
        </div>
        <div>
          <label for="chk-coupon" class="block font-bold mb-1">${L("Code promo (facultatif)", "رمز التخفيض (اختياري)", "Promo code (optional)")}</label>
          <div class="flex gap-2">
            <input type="text" id="chk-coupon" placeholder="${L("Votre code", "رمز التخفيض", "Your code")}" class="flex-1 px-3.5 py-2 rounded-xl border border-gray-300 font-mono uppercase focus:outline-none focus:border-emerald-deep" />
            <button type="button" onclick="applyGuestCheckoutCoupon()" class="px-4 py-2 rounded-xl bg-emerald-deep text-gold-reflective font-bold text-xs">${L("Appliquer", "تطبيق", "Apply")}</button>
          </div>
        </div>
      </div>

      <div class="bg-cream p-4 rounded-xl border border-gold-reflective/35 space-y-1.5 text-xs">
        <div class="flex justify-between">
          <span class="text-gray-600">${L("Sous-total :", "المجموع الفرعي:", "Subtotal:")}</span>
          <span class="font-bold">${formatDZD(subtotal)}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-600">${L("Remise promo :", "التخفيض:", "Discount:")}</span>
          <span id="chk-summary-discount" class="font-bold text-emerald-700">${discount > 0 ? ltr(`- ${formatDZD(discount)}`) : formatDZD(0)}</span>
        </div>
        <div class="flex justify-between">
          <span id="chk-summary-fee-label" class="text-gray-600">${L("Livraison", "التوصيل", "Delivery")} (${defaultWilaya.code} - ${wilayaName(defaultWilaya)} • ${activeMethod === "stop_desk" ? "Stop-Desk" : L("À domicile", "إلى المنزل", "Home")}) :</span>
          <span id="chk-summary-fee" class="font-bold text-emerald-deep">${defaultFeeKnown ? ltr(`+ ${formatDZD(defaultFee)}`) : deliveryFeeText(defaultWilaya, activeMethod)}</span>
        </div>
        <div class="flex justify-between text-sm font-extrabold text-emerald-deep pt-2 border-t border-gold-reflective/30">
          <span>${L("Total (Paiement à la livraison) :", "المجموع (الدفع عند الاستلام):", "Total (cash on delivery):")}</span>
          <span id="chk-summary-total">${formatDZD(subtotal - discount + defaultFee)}${defaultFeeKnown ? "" : L(" + livraison", " + التوصيل", " + delivery")}</span>
        </div>
      </div>

      <button type="button" onclick="submitGuestCheckoutOrder()" class="w-full py-3.5 rounded-xl gold-cta text-emerald-forest font-extrabold text-sm shadow-lg transition uppercase tracking-wider">
        ${L("Confirmer la commande (Paiement à la livraison)", "تأكيد الطلب (الدفع عند الاستلام)", "Confirm order (cash on delivery)")}
      </button>
      <button type="button" onclick="openWhatsAppCartConcierge()" class="w-full py-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold text-xs flex items-center justify-center gap-2 transition">
        <svg class="w-4 h-4 text-emerald-700 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0 0 12.04 2m.01 1.67c2.2 0 4.26.86 5.82 2.42a8.225 8.225 0 0 1 2.41 5.83c0 4.54-3.7 8.24-8.24 8.24-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.196 8.196 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24m4.52 11.66c-.25-.13-1.47-.72-1.7-.81-.23-.08-.39-.13-.56.13-.17.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.13-1.06-.39-2.03-1.25-.75-.67-1.26-1.5-1.41-1.75-.15-.25-.02-.39.11-.51.11-.11.25-.29.37-.44.13-.14.17-.25.25-.42.08-.17.04-.31-.02-.44-.06-.13-.56-1.34-.76-1.84-.2-.49-.4-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1s.9 2.43 1.03 2.6c.13.17 1.77 2.7 4.29 3.79.6.26 1.07.41 1.44.53.6.19 1.15.16 1.58.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.15-1.18-.06-.1-.23-.17-.48-.29z"/></svg><span>${L("Commander en 1 clic via Conciergerie WhatsApp", "اطلبوا بنقرة واحدة عبر واتساب", "Order in 1 click on WhatsApp")} (<bdi>${escapeHtml(storePhoneDisplay())}</bdi>)</span>
      </button>
    </div>
  `;
  for (const [id, value] of Object.entries(typed)) {
    const el = document.getElementById(id);
    if (el && value) el.value = value;
  }
  // Apply live prices and the wilaya's available methods straight away.
  if (document.getElementById("chk-wilaya")) updateCheckoutCalculation();
  const communeSel = document.getElementById("chk-commune");
  if (communeSel && typedCommune && Array.from(communeSel.options).some((o) => o.value === typedCommune)) {
    communeSel.value = typedCommune;
  }
}

function removeCartLine(variantId) {
  state.cart = state.cart.filter((i) => i.variantId !== variantId);
  saveCartToStorage();
  renderStorefront();
  renderCartDrawerContent();
}

// ========================================================================

Object.assign(window, {
  quickAddToCart,
  removeCartLine,
  addToCartInternal,
  updateCartItemQty,
  openCartDrawer,
  closeCartDrawer,
  computeCartSubtotal,
  computeCouponDiscount,
  applyGuestCheckoutCoupon,
  selectCheckoutDeliveryMethod,
  updateCheckoutCalculation,
  submitGuestCheckoutOrder,
  resetConfirmedOrder,
  renderCartDrawerContent,
});
