// Order tracking, information pages, delivery prices by wilaya.
// Part of the shop page (index.html). Loaded by main.js in order; what a file defines is put
// on window at its end, so the HTML (onclick="…") and the other files can use it.

// ORDER TRACKING & STATIC PAGES
// ========================================================================
function openOrderTrackingModal() {
  const texts = {
    "trk-title": L("Suivi de Commande", "تتبع الطلب", "Track my order"),
    "trk-intro": L("Saisissez votre numéro de commande et le numéro de téléphone utilisé lors de votre achat :", "أدخلوا رقم الطلب ورقم الهاتف المستعمل عند الشراء:", "Enter your order number and the phone number used for the order:"),
    "trk-ref-label": L("N° de commande *", "رقم الطلب *", "Order number *"),
    "trk-phone-label": L("Téléphone *", "رقم الهاتف *", "Phone *"),
    "trk-submit": L("Rechercher ma commande", "البحث عن طلبي", "Find my order"),
  };
  Object.entries(texts).forEach(([id, text]) => { const el = document.getElementById(id); if (el) el.textContent = text; });
  document.getElementById("order-tracking-modal").classList.remove("hidden");
  lookupGuestOrderStatus();
}

function closeOrderTrackingModal() {
  document.getElementById("order-tracking-modal").classList.add("hidden");
}

async function lookupGuestOrderStatus() {
  const ref = (document.getElementById("track-order-ref").value || "").trim().toUpperCase().replace(/^#/, "");
  const phone = (document.getElementById("track-order-phone").value || "").trim().replace(/[\s\-\.]/g, "");
  const resEl = document.getElementById("track-order-result");
  if (!ref || !phone) {
    resEl.innerHTML = `<div class="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 font-semibold">${L("Veuillez saisir votre numéro de commande et votre numéro de téléphone.", "يرجى إدخال رقم الطلب ورقم الهاتف.", "Please enter your order number and phone number.")}</div>`;
    return;
  }
  let found = null;
  let serverAnswered = false;
  try {
    const trackRes = await fetch(`/api/v1/orders/track?reference=${encodeURIComponent(ref)}&phone=${encodeURIComponent(phone)}`, { headers: { "X-Request-ID": "sf_" + Date.now().toString(36) } });
    serverAnswered = trackRes.ok || trackRes.status === 404;
    if (trackRes.ok) {
      const apiOrd = await trackRes.json();
      found = {
        reference: apiOrd.order_reference,
        status: apiOrd.status,
        customer_name: apiOrd.customer_name,
        wilaya_code: apiOrd.wilaya_code,
        wilaya_name: apiOrd.wilaya_name,
        commune: apiOrd.commune,
        total_dzd: apiOrd.total_dzd,
        items: apiOrd.items || [],
      };
    }
  } catch (_e) {}
  // The shop's answer is the truth; the copy kept in this browser is only
  // used when the shop cannot be reached at all.
  if (!found && !serverAnswered) {
    found = state.orders.find((o) => o.reference.toUpperCase() === ref && o.customer_phone.replace(/[\s\-\.]/g, "") === phone);
  }
  if (!found) {
    resEl.innerHTML = `<div class="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 font-semibold">${L("Aucune commande trouvée pour ce numéro et ce téléphone.", "لم نجد أي طلب بهذا الرقم وهذا الهاتف.", "No order found for this number and phone.")}</div>`;
    return;
  }
  const ORDER_STATUS = {
    new:                  { fr: "Reçue — nous allons vous appeler", ar: "تم الاستلام — سنتصل بك", en: "Received — we will call you", step: 1 },
    pending_confirmation: { fr: "En attente de confirmation", ar: "في انتظار التأكيد", en: "Awaiting confirmation", step: 1 },
    confirmed:            { fr: "Confirmée", ar: "مؤكدة", en: "Confirmed", step: 2 },
    preparing:            { fr: "En préparation", ar: "قيد التحضير", en: "Being prepared", step: 2 },
    ready_for_shipment:   { fr: "Prête à expédier", ar: "جاهزة للشحن", en: "Ready to ship", step: 2 },
    shipped:              { fr: "Expédiée — chez le livreur", ar: "تم الشحن — عند عامل التوصيل", en: "Shipped — with the courier", step: 3 },
    delivered:            { fr: "Livrée", ar: "تم التوصيل", en: "Delivered", step: 4 },
    cancelled:            { fr: "Annulée", ar: "ملغاة", en: "Cancelled", step: 0 },
    returned:             { fr: "Retournée", ar: "مرتجعة", en: "Returned", step: 0 },
  };
  const lang = state.lang === "ar" || state.lang === "en" ? state.lang : "fr";
  const stInfo = ORDER_STATUS[String(found.status || "")] || null;
  const statusLabel = stInfo ? stInfo[lang] : String(found.status || "");
  const stepIdx = stInfo ? stInfo.step : 1;
  const steps = lang === "ar" ? ["1. استلام", "2. تأكيد", "3. شحن", "4. توصيل"]
    : lang === "en" ? ["1. Received", "2. Confirmed", "3. Shipped", "4. Delivered"]
    : ["1. Reçue", "2. Confirmée", "3. Expédiée", "4. Livrée"];
  const lbl = lang === "ar" ? { client: "الزبون", items: "المنتجات", total: "المبلغ عند الاستلام" }
    : lang === "en" ? { client: "Customer", items: "Items", total: "Cash on delivery" }
    : { client: "Client", items: "Articles", total: "Total COD" };
  const timelineHtml = steps
    .map((label, idx) => {
      const active = idx + 1 <= stepIdx;
      return `<div class="flex-1 text-center py-1.5 px-1 rounded-lg border text-[10px] font-bold ${
        active
          ? "bg-emerald-deep text-gold-reflective border-gold-reflective"
          : "bg-white text-gray-400 border-gray-200"
      }">${label}</div>`;
    })
    .join("");

  resEl.innerHTML = `
    <div class="p-4 rounded-xl bg-cream border border-gold-reflective/40 space-y-3">
      <div class="flex items-center justify-between">
        <span class="font-mono font-extrabold text-emerald-deep text-sm" dir="ltr">#${escapeHtml(found.reference)}</span>
        <span class="px-2.5 py-0.5 rounded-full ${stepIdx === 0 ? "bg-red-700 text-white" : "bg-emerald-deep text-gold-reflective"} font-bold text-[11px]">${escapeHtml(statusLabel)}</span>
      </div>
      ${stepIdx === 0
        ? `<div class="p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-700 font-semibold text-xs">${escapeHtml(statusLabel)}</div>`
        : `<div class="flex items-center gap-1.5">${timelineHtml}</div>`}
      <div class="space-y-1 text-xs">
        <p><strong>${lbl.client} :</strong> ${escapeHtml(found.customer_name)} (${escapeHtml(found.wilaya_code)} - ${escapeHtml(found.wilaya_name)}, ${escapeHtml(found.commune)})</p>
        <p><strong>${lbl.items} :</strong> ${found.items.map((i) => `${Number(i.quantity) || 1}× ${escapeHtml(i.product_name)}`).join(", ")}</p>
      </div>
      <div class="flex items-center justify-between pt-2 border-t border-gold-reflective/25">
        <span class="font-extrabold text-emerald-deep">${lbl.total} : ${formatDZD(found.total_dzd)}</span>
        <a href="https://wa.me/${waNumber()}?text=${encodeURIComponent(`Bonjour Mus Luxury, suivi commande #${found.reference}`)}" target="_blank" rel="noopener noreferrer" class="px-3 py-1 rounded-lg bg-emerald-deep text-gold-reflective font-bold text-[11px]">Support WhatsApp</a>
      </div>
    </div>
  `;
}

const STATIC_PAGES_CONTENT = {
  about: {
    title: "La Maison Mus Luxury — Ouled Yaïch",
    // A getter: the phone / WhatsApp number is read when the page opens, so
    // a number changed in the CMS since the shop loaded is the one shown.
    get body() {
      return `
      <p><strong>Mus Luxury</strong> sélectionne pour vous des pièces de maroquinerie, chaussures, châles, coffrets de maquillage, lunettes et montres alliant coupe contemporaine et finitions soignées.</p>
      <p>Nous livrons dans les <strong>69 Wilayas d'Algérie</strong> (à domicile ou en bureau Stop-Desk) avec paiement simple et sécurisé à la réception de votre colis.</p>
      <div class="p-4 rounded-xl bg-cream border border-gold-reflective/40 space-y-2 mt-3 text-xs">
        <p><strong>Adresse Boutique :</strong> <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="text-emerald-deep underline font-bold">FVX6+GCJ Mus luxury, Ouled Yaïch (Blida — 09)</a></p>
        <p><strong>Téléphone &amp; WhatsApp :</strong> <a href="https://wa.me/${waNumber()}" target="_blank" rel="noopener noreferrer" class="font-mono font-bold text-emerald-deep underline">${storePhoneDisplay()}</a></p>
        <p><strong>Instagram officiel :</strong> <a href="https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux" target="_blank" rel="noopener noreferrer" class="text-emerald-deep underline font-semibold">@musluxury09</a></p>
        <p><strong>TikTok officiel :</strong> <a href="https://www.tiktok.com/@musluxury.092?_r=1&_t=ZS-9B2mO0gpA7V" target="_blank" rel="noopener noreferrer" class="text-emerald-deep underline font-semibold">@musluxury.092</a></p>
      </div>
    `;
    },
  },
  faq: {
    title: "Questions Fréquentes (FAQ)",
    body: `
      <div class="space-y-3">
        <div><p class="font-bold text-emerald-deep">1. Comment passer commande ?</p><p>Sélectionnez votre article et sa variante, cliquez sur « Ajouter au panier », puis renseignez votre nom, numéro de téléphone, Wilaya et Commune. Aucun compte n'est requis.</p></div>
        <div><p class="font-bold text-emerald-deep">2. Quand s'effectue le paiement ?</p><p>Le paiement s'effectue intégralement en espèces à la livraison (Cash on Delivery) à la réception de votre commande.</p></div>
      </div>
    `
  },
  returns: {
    title: "Livraison & Retours sous 7 Jours",
    body: `
      <p><strong>Livraison 69 Wilayas :</strong> à domicile ou en bureau Stop-Desk ; le délai dépend de la wilaya.</p>
      <p><strong>Échange & Retour :</strong> Vous disposez de 7 jours après réception pour demander un échange de taille ou de modèle dans son emballage d'origine.</p>
    `
  },
  terms: {
    title: "Conditions Générales & Confidentialité",
    body: `
      <p>Tous nos tarifs sont affichés en Dinar Algérien (DA). Les coordonnées transmises lors de votre commande sont utilisées uniquement pour l'expédition et le suivi de votre colis.</p>
    `
  }
};

async function openStaticPageModal(pageKey) {
  const p = STATIC_PAGES_CONTENT[pageKey] || STATIC_PAGES_CONTENT.about;
  document.getElementById("static-page-title").textContent = p.title;
  document.getElementById("static-page-body").innerHTML = p.body;
  document.getElementById("static-page-modal").classList.remove("hidden");
  try {
    const pgRes = await fetch(`/api/v1/pages/${encodeURIComponent(pageKey)}`, { headers: { "X-Request-ID": "sf_" + Date.now().toString(36) } });
    if (pgRes.ok) {
      const pgData = await pgRes.json();
      // The customer's language when the owner wrote it, French otherwise.
      const lang = state.lang || "fr";
      const title = (pgData["title_" + lang] || "").trim() || pgData.title_fr;
      const content = (pgData["content_" + lang] || "").trim() || pgData.content_fr;
      const bodyEl = document.getElementById("static-page-body");
      if (title) document.getElementById("static-page-title").textContent = title;
      if (content) {
        bodyEl.textContent = content;
        bodyEl.style.whiteSpace = "pre-line";
      }
      bodyEl.dir = (pgData["content_" + lang] || "").trim() && lang === "ar" ? "rtl" : "ltr";
    }
  } catch (_e) {}
}

function closeStaticPageModal() {
  document.getElementById("static-page-modal").classList.add("hidden");
}

function openWilayaTariffsModal() {
  renderWilayaTariffsTable();
  document.getElementById("wilaya-tariffs-modal").classList.remove("hidden");
}

function closeWilayaTariffsModal() {
  document.getElementById("wilaya-tariffs-modal").classList.add("hidden");
}


function selectWilayaFromTariffModal(wilayaCode, method) {
  state.checkoutWilaya = wilayaCode;
  state.checkoutMethod = method === "stop_desk" ? "stop_desk" : "home";
  state.activePdpWilaya = wilayaCode;
  state.activePdpDeliveryMethod = state.checkoutMethod;
  closeWilayaTariffsModal();
  if (!document.getElementById("product-detail-modal").classList.contains("hidden")) {
    renderPdpModalContent();
  }
  if (!document.getElementById("cart-checkout-modal").classList.contains("hidden")) {
    renderCartDrawerContent();
  } else {
    const w = WILAYAS.find((x) => x.code === wilayaCode);
    if (w) {
      showToast(`Wilaya ${w.code} - ${w.name_fr} sélectionnée (${state.checkoutMethod === "stop_desk" ? "Stop-Desk" : "À domicile"} : ${deliveryFeeText(w, state.checkoutMethod)})`);
    }
  }
}

function renderWilayaTariffsTable() {
  const tbody = document.getElementById("wilaya-tariffs-tbody");
  if (!tbody) return;
  const q = (document.getElementById("wilaya-modal-search")?.value || "").trim().toLowerCase();
  const filtered = WILAYAS.filter(
    (w) =>
      !q ||
      w.code.toLowerCase().includes(q) ||
      w.name_fr.toLowerCase().includes(q) ||
      (w.name_ar && w.name_ar.includes(q))
  );

  tbody.innerHTML = filtered
    .map(
      (w) => `
      <tr class="hover:bg-cream/60 transition">
        <td class="py-2 px-3 font-mono font-extrabold text-emerald-deep">${escapeHtml(w.code)}</td>
        <td class="py-2 px-3 font-bold text-charcoal">${escapeHtml(w.name_fr)} <span class="text-gray-400 font-normal text-[11px] ml-1">${escapeHtml(w.name_ar || "")}</span></td>
        <td class="py-2 px-3">
          <span class="inline-flex items-center gap-1 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1 font-extrabold text-emerald-900 text-xs">
            ${deliveryFeeText(w, "home")}
          </span>
        </td>
        <td class="py-2 px-3">
          <span class="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1 font-extrabold text-amber-900 text-xs">
            ${deliveryFeeText(w, "stop_desk")}
          </span>
        </td>
        <td class="py-2 px-3 text-right whitespace-nowrap space-x-1">
          <button
            type="button"
            onclick="selectWilayaFromTariffModal('${w.code}', 'home')"
            class="px-2.5 py-1 rounded-lg bg-emerald-deep text-gold-reflective font-bold text-[10px] hover:bg-emerald-forest transition"
          >
            Choisir Domicile
          </button>
          <button
            type="button"
            onclick="selectWilayaFromTariffModal('${w.code}', 'stop_desk')"
            class="px-2.5 py-1 rounded-lg bg-cream border border-gold-reflective/50 text-emerald-deep font-bold text-[10px] hover:bg-gold-reflective/20 transition"
          >
            Choisir Desk
          </button>
        </td>
      </tr>
    `
    )
    .join("");
}

// The API returns at most 50 products per page: read every page so the

Object.assign(window, {
  openOrderTrackingModal,
  closeOrderTrackingModal,
  lookupGuestOrderStatus,
  STATIC_PAGES_CONTENT,
  openStaticPageModal,
  closeStaticPageModal,
  openWilayaTariffsModal,
  closeWilayaTariffsModal,
  selectWilayaFromTariffModal,
  renderWilayaTariffsTable,
});
