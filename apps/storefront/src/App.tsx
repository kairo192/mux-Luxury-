import React, { useEffect, useState } from "react";
import {
  fetchStoreLayout,
  fetchCategories,
  fetchCategoryBySlug,
  fetchProducts,
  fetchProductBySlug,
  fetchDeliveryZones,
  calculateDeliveryTotal,
  validateCouponCode,
  submitGuestOrder,
  trackGuestOrder,
  fetchStaticPage,
} from "./api/client";

interface StoreCustomerNotice {
  type: "success" | "error" | "info";
  title: string;
  message: string;
}

export default function App() {
  const [layout, setLayout] = useState<any | null>(null);
  const [categories, setCategories] = useState<any[]>([]);
  const [activeCategoryDetail, setActiveCategoryDetail] = useState<any | null>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [wilayas, setWilayas] = useState<any[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);
  const [selectedAxes, setSelectedAxes] = useState<Record<string, string>>({});
  const [selectedVariant, setSelectedVariant] = useState<any | null>(null);
  const [cart, setCart] = useState<Array<{ variant: any; product: any; quantity: number }>>([]);
  const [selectedWilaya, setSelectedWilaya] = useState("09");
  const [deliveryMethod, setDeliveryMethod] = useState<"home" | "stop_desk">("home");
  const [calcPreview, setCalcPreview] = useState<any | null>(null);
  const [couponInput, setCouponInput] = useState("");
  const [appliedCoupon, setAppliedCoupon] = useState<any | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [commune, setCommune] = useState("Ouled Yaïch");
  const [address, setAddress] = useState("");
  const [orderConfirmed, setOrderConfirmed] = useState<any | null>(null);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [customerNotice, setCustomerNotice] = useState<StoreCustomerNotice | null>(null);

  // Order Tracking & Static Pages State
  const [trackRef, setTrackRef] = useState("");
  const [trackPhone, setTrackPhone] = useState("");
  const [trackedOrder, setTrackedOrder] = useState<any | null>(null);
  const [activeStaticPage, setActiveStaticPage] = useState<any | null>(null);

  useEffect(() => {
    fetchStoreLayout().then((res) => setLayout(res)).catch(() => null);
    fetchCategories().then((res) => setCategories(res.items || []));
    fetchDeliveryZones().then((res) => setWilayas(res.items || []));
  }, []);

  useEffect(() => {
    fetchProducts({ category: activeCategory, q: searchQuery }).then((res) => setProducts(res.items || []));
    if (activeCategory) {
      fetchCategoryBySlug(activeCategory).then((cat) => setActiveCategoryDetail(cat)).catch(() => setActiveCategoryDetail(null));
    } else {
      setActiveCategoryDetail(null);
    }
  }, [activeCategory, searchQuery]);

  const subtotal = cart.reduce(
    (sum, it) => sum + (it.variant.effective_price_dzd ?? it.product.selling_price_dzd) * it.quantity,
    0
  );
  const freeShipThreshold = Number(layout?.settings?.free_delivery_threshold_dzd || 25000);
  const remainingForFreeShip = Math.max(0, freeShipThreshold - subtotal);
  const freeShipPct = Math.min(100, Math.round((subtotal / freeShipThreshold) * 100));

  useEffect(() => {
    if (selectedWilaya) {
      calculateDeliveryTotal(selectedWilaya, deliveryMethod, subtotal, appliedCoupon?.code)
        .then((res) => {
          setCalcPreview(res);
          if (res.communes?.length && !res.communes.includes(commune)) {
            setCommune(res.communes[0]);
          }
          if (deliveryMethod === "stop_desk" && res.stop_desk_rate && !res.stop_desk_rate.is_supported) {
            setDeliveryMethod("home");
          } else if (deliveryMethod === "home" && res.home_rate && !res.home_rate.is_supported) {
            setDeliveryMethod("stop_desk");
          }
        })
        .catch(() => {});
    }
  }, [selectedWilaya, deliveryMethod, subtotal, appliedCoupon]);

  async function openProductDetails(slug: string) {
    try {
      const fullProd = await fetchProductBySlug(slug);
      setSelectedProduct(fullProd);
      const firstAvail = fullProd.variants.find((v: any) => v.stock_qty > 0) || fullProd.variants[0];
      setSelectedVariant(firstAvail || null);
      setSelectedAxes(firstAvail?.attributes || {});
    } catch (err: any) {
      setCustomerNotice({
        type: "error",
        title: "Article momentanément indisponible",
        message: err.message || "Impossible de charger les détails de cet article.",
      });
    }
  }

  function handleSelectAxis(attrKey: string, optionVal: string) {
    if (!selectedProduct) return;
    const nextAxes = { ...selectedAxes, [attrKey]: optionVal };
    setSelectedAxes(nextAxes);
    const exactMatch =
      selectedProduct.variants.find((v: any) =>
        Object.entries(nextAxes).every(([k, val]) => v.attributes?.[k] === val)
      ) || selectedProduct.variants.find((v: any) => v.attributes?.[attrKey] === optionVal);
    if (exactMatch) {
      setSelectedVariant(exactMatch);
      setSelectedAxes(exactMatch.attributes || {});
    }
  }

  function addToCart() {
    if (!selectedProduct || !selectedVariant) return;
    const maxAvail = Number(selectedVariant.stock_qty ?? 0);
    if (maxAvail <= 0) {
      setCustomerNotice({
        type: "error",
        title: "Variante en rupture de stock",
        message: "Cette taille ou couleur est momentanément épuisée. Veuillez sélectionner une autre variante disponible.",
      });
      return;
    }
    setCart((prev) => {
      const idx = prev.findIndex((it) => it.variant.id === selectedVariant.id);
      if (idx >= 0) {
        const nextQty = Math.min(maxAvail, prev[idx].quantity + 1);
        return prev.map((it, i) => (i === idx ? { ...it, quantity: nextQty } : it));
      }
      return [...prev, { product: selectedProduct, variant: selectedVariant, quantity: 1 }];
    });
    setSelectedProduct(null);
    setCustomerNotice({
      type: "success",
      title: "Ajouté à votre panier Mus Luxury",
      message: `${selectedProduct.name_fr} (${selectedVariant.title}) a été ajouté à votre sélection.`,
    });
  }

  function updateCartQuantity(variantId: number, delta: number) {
    setCart((prev) =>
      prev
        .map((it) => {
          if (it.variant.id !== variantId) return it;
          const maxAvail = Math.max(1, Number(it.variant.stock_qty ?? 50));
          const nextQ = Math.min(maxAvail, it.quantity + delta);
          return nextQ > 0 ? { ...it, quantity: nextQ } : null;
        })
        .filter(Boolean) as Array<{ variant: any; product: any; quantity: number }>
    );
  }

  function removeFromCart(variantId: number) {
    setCart((prev) => prev.filter((it) => it.variant.id !== variantId));
  }

  async function handleApplyCoupon() {
    setErrorMsg("");
    if (!couponInput.trim()) {
      setAppliedCoupon(null);
      return;
    }
    try {
      const cpn = await validateCouponCode(couponInput.trim(), subtotal);
      setAppliedCoupon(cpn);
      setCustomerNotice({
        type: "success",
        title: `Code promo ${cpn.code} activé`,
        message: `Une remise immédiate de ${cpn.discount_dzd} DA a été appliquée à votre panier.`,
      });
    } catch (err: any) {
      setAppliedCoupon(null);
      const msg = err.message || "Code promo invalide";
      setErrorMsg(msg);
      setCustomerNotice({ type: "error", title: "Code promotionnel non applicable", message: msg });
    }
  }

  async function handleTrackOrder(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg("");
    if (!trackRef.trim() || !trackPhone.trim()) {
      setCustomerNotice({
        type: "error",
        title: "Informations de suivi requises",
        message: "Veuillez saisir votre numéro de commande (ex: LUX-...) ainsi que le numéro de téléphone utilisé lors de l'achat.",
      });
      return;
    }
    try {
      const ord = await trackGuestOrder(trackRef.trim(), trackPhone.trim());
      setTrackedOrder(ord);
    } catch (err: any) {
      setTrackedOrder(null);
      const msg = err.message || "Commande introuvable";
      setErrorMsg(msg);
      setCustomerNotice({ type: "error", title: "Suivi de commande", message: msg });
    }
  }

  async function handleOpenStaticPage(slug: string) {
    try {
      const pg = await fetchStaticPage(slug);
      setActiveStaticPage(pg);
    } catch {
      setActiveStaticPage(null);
    }
  }

  async function handleCheckout(e: React.FormEvent) {
    e.preventDefault();
    if (isSubmittingOrder) return;
    setErrorMsg("");
    const cleanPhone = customerPhone.replace(/[\s\-\.]/g, "");
    if (customerName.trim().length < 3 || /[<>]/.test(customerName) || /[<>]/.test(address)) {
      const msg = "Veuillez vérifier votre nom complet et votre adresse de livraison (les caractères spéciaux < > ne sont pas autorisés).";
      setErrorMsg(msg);
      setCustomerNotice({ type: "error", title: "Coordonnées invalides", message: msg });
      return;
    }
    if (!/^(\+213|0)(5|6|7)[0-9]{8}$/.test(cleanPhone)) {
      const msg = "Veuillez saisir un numéro de téléphone mobile algérien valide (05, 06, 07 ou +213).";
      setErrorMsg(msg);
      setCustomerNotice({ type: "error", title: "Numéro de téléphone invalide", message: msg });
      return;
    }
    setIsSubmittingOrder(true);
    try {
      const cartFingerprint = cart
        .map((c) => `${c.variant.id}:${c.quantity}`)
        .sort()
        .join(",");
      const idemKey = `order-${cleanPhone}-${selectedWilaya}-${commune}-${cartFingerprint}`;
      const res = await submitGuestOrder(
        {
          full_name: customerName.trim(),
          phone: cleanPhone,
          wilaya_code: selectedWilaya,
          commune,
          delivery_address: address.trim(),
          delivery_method: deliveryMethod,
          coupon_code: appliedCoupon?.code || undefined,
          items: cart.map((c) => ({ variant_id: c.variant.id, quantity: c.quantity })),
        },
        idemKey
      );
      setOrderConfirmed(res);
      setCart([]);
      setAppliedCoupon(null);
      setCustomerNotice({
        type: "success",
        title: `Commande #${res.order_reference} confirmée !`,
        message: `Merci ${customerName.trim()}. Notre équipe à Ouled Yaïch vous contactera au ${cleanPhone} pour confirmer l'expédition (${res.total_dzd} DA à la livraison).`,
      });
    } catch (err: any) {
      const msg = err.message || "Erreur lors de la validation de la commande";
      setErrorMsg(msg);
      setCustomerNotice({ type: "error", title: "Validation de la commande", message: msg });
    } finally {
      setIsSubmittingOrder(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F6F0] text-[#202923]">
      {/* Customer Message Box Modal */}
      {customerNotice && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div role="dialog" aria-modal="true" className="bg-white rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]">
            <div className={`px-5 py-3.5 flex items-center justify-between ${customerNotice.type === "error" ? "bg-red-900 text-white" : "bg-[#063D2E] text-white"}`}>
              <span className="font-serif font-bold text-[#D4AF62] text-sm">
                {customerNotice.type === "error" ? "⛔ Vérification Requise" : "✨ Maison Mus Luxury — Conciergerie"}
              </span>
              <button onClick={() => setCustomerNotice(null)} className="text-xs font-bold px-2 py-1 rounded bg-black/25">✕</button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <h4 className="text-base font-serif font-bold text-[#063D2E]">{customerNotice.title}</h4>
              <p className="text-sm text-gray-700 leading-relaxed bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30">{customerNotice.message}</p>
              <div className="flex justify-end gap-2">
                <a href="https://wa.me/213655534154" target="_blank" rel="noopener noreferrer" className="px-3.5 py-2 rounded-xl bg-emerald-50 text-emerald-900 border border-emerald-300 font-bold">
                  WhatsApp 0655 53 41 54
                </a>
                <button onClick={() => setCustomerNotice(null)} className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold">
                  Compris
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top Luxury Announcement & Trust Bar */}
      <div className="bg-[#02291F] text-[#E8D4A5] px-6 py-2 text-[11px] flex flex-wrap items-center justify-between gap-2 border-b border-[#D4AF62]/20">
        <span>🚚 Livraison Rapide 69 Wilayas en Algérie (Domicile &amp; Stop-Desk) • Paiement en espèces à la réception</span>
        <div className="flex items-center gap-4">
          <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" className="hover:text-[#D4AF62] underline">
            {layout?.settings?.store_location || layout?.settings?.address_fr || "FVX6+GCJ Mus luxury, Ouled Yaïch"}
          </a>
          <a href="https://wa.me/213655534154" target="_blank" rel="noopener noreferrer" className="font-mono font-bold text-[#D4AF62]">
            WhatsApp : 0655 53 41 54
          </a>
        </div>
      </div>

      {/* Main Boutique Header */}
      <header className="bg-[#063D2E] text-white px-6 py-4 flex flex-wrap items-center justify-between gap-4 border-b border-[#D4AF62]/30 sticky top-0 z-40 shadow-lg">
        <div className="flex items-center gap-3">
          <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" className="h-11 w-auto rounded-lg border border-[#D4AF62]/40" />
          <div>
            <span className="font-serif font-bold text-lg text-[#D4AF62] block leading-none">MUS LUXURY</span>
            <span className="text-[10px] text-[#E8D4A5]/80 uppercase tracking-widest">Boutique Officielle • Algérie</span>
          </div>
        </div>
        <div className="flex-1 max-w-xs">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher un sac, chaussure, montre..."
            className="w-full px-4 py-2 rounded-full bg-[#02291F] border border-[#D4AF62]/40 text-xs text-white placeholder-[#E8D4A5]/60"
          />
        </div>
        <nav className="flex gap-2 text-xs overflow-x-auto">
          <button onClick={() => setActiveCategory("")} className={`px-3.5 py-1.5 rounded-full font-bold ${!activeCategory ? "bg-[#D4AF62] text-[#02291F]" : "text-[#E8D4A5] hover:bg-[#02291F]"}`}>
            Toutes les Collections
          </button>
          {categories.map((c) => (
            <button key={c.slug} onClick={() => setActiveCategory(c.slug)} className={`px-3.5 py-1.5 rounded-full font-semibold ${activeCategory === c.slug ? "bg-[#D4AF62] text-[#02291F] font-bold" : "hover:bg-[#02291F] text-[#E8D4A5]"}`}>
              {c.name_fr}
            </button>
          ))}
          <button onClick={() => handleOpenStaticPage("about")} className="px-3.5 py-1.5 rounded-full hover:bg-[#02291F] text-[#D4AF62] font-semibold">
            La Maison
          </button>
          <button onClick={() => handleOpenStaticPage("returns")} className="px-3.5 py-1.5 rounded-full hover:bg-[#02291F] text-[#E8D4A5]">
            Livraison &amp; Retours
          </button>
        </nav>
      </header>

      {activeCategoryDetail && (
        <div className="max-w-7xl mx-auto px-6 pt-4 text-xs text-[#063D2E] font-semibold">
          Collection : {activeCategoryDetail.name_fr} ({activeCategoryDetail.attributes?.length || 0} attributs dynamiques)
        </div>
      )}

      <main className="max-w-7xl mx-auto p-4 sm:p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 items-stretch flex-1">
        {products.map((p) => (
          <article key={p.id} onClick={() => openProductDetails(p.slug)} className="cursor-pointer bg-white rounded-2xl p-4 border border-[#D4AF62]/30 shadow-sm hover:shadow-xl transition flex flex-col justify-between">
            <div>
              <div className="relative overflow-hidden rounded-xl bg-[#F8F6F0]">
                <img src={p.main_image_url} alt={p.name_fr} className="w-full h-56 object-cover hover:scale-105 transition duration-500" />
                <span className="absolute top-2.5 left-2.5 px-2.5 py-0.5 rounded-full bg-[#063D2E] text-[#D4AF62] text-[10px] font-bold">
                  {p.total_stock > 0 ? `En stock (${p.total_stock})` : "Rupture"}
                </span>
              </div>
              <p className="text-[10px] uppercase tracking-widest text-[#B68F40] font-bold mt-3">{p.brand?.name || p.brand_name || "MUS LUXURY"}</p>
              <h3 className="font-bold text-sm mt-0.5">{p.name_fr}</h3>
            </div>
            <div className="pt-3 flex items-center justify-between">
              <span className="text-lg font-extrabold text-[#063D2E]">{p.selling_price_dzd} DA</span>
              <span className="px-3 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] text-xs font-bold">Choisir</span>
            </div>
          </article>
        ))}
      </main>

      {cart.length > 0 && (
        <section className="max-w-3xl mx-auto w-full p-6 bg-white rounded-2xl border-2 border-[#D4AF62] my-6 space-y-4 text-xs shadow-xl">
          <div className="p-3.5 rounded-xl bg-[#063D2E] text-white space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span>
                {remainingForFreeShip === 0
                  ? "✨ Livraison Prioritaire Offerte débloquée !"
                  : `Plus que ${remainingForFreeShip} DA pour la livraison gratuite (Seuil ${freeShipThreshold} DA)`}
              </span>
              <span className="font-mono font-bold text-[#D4AF62]">{freeShipPct}%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-[#02291F] overflow-hidden">
              <div className="h-full bg-[#D4AF62]" style={{ width: `${freeShipPct}%` }} />
            </div>
          </div>

          <div className="space-y-2 border-b border-[#D4AF62]/30 pb-3">
            <h4 className="font-serif font-bold text-sm text-[#063D2E]">Votre Sélection ({cart.reduce((s, c) => s + c.quantity, 0)} article(s))</h4>
            {cart.map((item) => {
              const unitPrice = item.variant.effective_price_dzd ?? item.product.selling_price_dzd;
              return (
                <div key={item.variant.id} className="flex items-center justify-between gap-2 bg-[#F8F6F0] px-3 py-2 rounded-xl border border-[#D4AF62]/20">
                  <div>
                    <p className="font-bold text-[#063D2E]">{item.product.name_fr}</p>
                    <p className="text-[11px] text-gray-600">{item.variant.title} • {unitPrice} DA / unité</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button type="button" onClick={() => updateCartQuantity(item.variant.id, -1)} className="px-2 py-0.5 rounded bg-white border font-bold">−</button>
                    <span className="font-mono font-bold px-1.5">{item.quantity}</span>
                    <button type="button" onClick={() => updateCartQuantity(item.variant.id, 1)} className="px-2 py-0.5 rounded bg-white border font-bold">+</button>
                    <button type="button" onClick={() => removeFromCart(item.variant.id)} className="ml-1 px-2 py-0.5 rounded bg-red-50 text-red-700 font-bold">✕</button>
                  </div>
                </div>
              );
            })}
          </div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E]">Commande Directe sans Compte (69 Wilayas • Paiement à la livraison)</h3>
          {errorMsg && <div className="p-3 rounded-xl bg-red-100 text-red-800 font-bold">{errorMsg}</div>}
          <form onSubmit={handleCheckout} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} required placeholder="Nom et prénom *" className="px-3.5 py-2.5 border rounded-xl" />
              <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} required placeholder="Téléphone mobile (0655 53 41 54) *" className="px-3.5 py-2.5 border rounded-xl font-mono" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <select value={selectedWilaya} onChange={(e) => setSelectedWilaya(e.target.value)} className="px-3.5 py-2.5 border rounded-xl bg-white font-bold">
                {wilayas.map((w) => (
                  <option key={w.wilaya_code} value={w.wilaya_code}>
                    {w.wilaya_code} - {w.wilaya_name_fr}
                  </option>
                ))}
              </select>
              <select value={commune} onChange={(e) => setCommune(e.target.value)} className="px-3.5 py-2.5 border rounded-xl bg-white font-bold">
                {(calcPreview?.communes?.length ? calcPreview.communes : [commune || "Centre-Ville"]).map((cm: string) => (
                  <option key={cm} value={cm}>{cm}</option>
                ))}
              </select>
            </div>
            <select value={deliveryMethod} onChange={(e) => setDeliveryMethod(e.target.value as "home" | "stop_desk")} className="w-full px-3.5 py-2.5 border rounded-xl bg-white font-bold">
              <option value="home" disabled={calcPreview?.home_rate?.is_supported === false}>
                Livraison à Domicile ({calcPreview?.home_rate?.fee_dzd ?? 500} DA)
              </option>
              <option value="stop_desk" disabled={calcPreview?.stop_desk_rate?.is_supported === false}>
                Stop-Desk / Bureau Relais ({calcPreview?.stop_desk_rate?.fee_dzd ?? 350} DA)
              </option>
            </select>
            <input value={address} onChange={(e) => setAddress(e.target.value)} required placeholder="Adresse exacte de livraison *" className="w-full px-3.5 py-2.5 border rounded-xl" />
            <div className="flex gap-2">
              <input value={couponInput} onChange={(e) => setCouponInput(e.target.value)} placeholder="Code promo (ex: BIENVENUE10)" className="flex-1 px-3.5 py-2 border rounded-xl font-mono uppercase" />
              <button type="button" onClick={handleApplyCoupon} className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
                Appliquer
              </button>
            </div>
            <div className="p-3.5 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/40 font-extrabold text-sm text-[#063D2E] flex justify-between">
              <span>Total à payer à la livraison (Wilaya {selectedWilaya}) :</span>
              <span>{calcPreview?.total_dzd ?? subtotal} DA</span>
            </div>
            <button type="submit" disabled={isSubmittingOrder} className="w-full py-3.5 rounded-xl bg-[#063D2E] hover:bg-[#02291F] disabled:opacity-50 text-[#D4AF62] font-extrabold text-sm">
              {isSubmittingOrder ? "Validation en cours..." : "Confirmer ma commande (Cash on Delivery)"}
            </button>
          </form>
        </section>
      )}

      {/* Visual 4-Step Order Tracking Section */}
      <section className="max-w-3xl mx-auto w-full px-6 pb-6 text-xs space-y-3">
        <form onSubmit={handleTrackOrder} className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40 flex flex-wrap gap-2 items-center shadow-sm">
          <span className="font-bold text-[#063D2E]">📦 Suivre ma commande :</span>
          <input value={trackRef} onChange={(e) => setTrackRef(e.target.value)} placeholder="N° (ex: LUX-12345)" className="px-3 py-1.5 border rounded-xl font-mono uppercase" />
          <input value={trackPhone} onChange={(e) => setTrackPhone(e.target.value)} placeholder="0655 53 41 54" className="px-3 py-1.5 border rounded-xl font-mono" />
          <button type="submit" className="px-4 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">Rechercher</button>
        </form>
        {trackedOrder && (
          <div className="bg-white p-4 rounded-2xl border border-[#D4AF62] space-y-2 shadow-sm">
            <div className="flex justify-between items-center">
              <span className="font-mono font-extrabold text-[#063D2E]">#{trackedOrder.order_reference}</span>
              <span className="px-2.5 py-0.5 rounded-full bg-[#063D2E] text-[#D4AF62] font-bold">{trackedOrder.status}</span>
            </div>
            {(() => {
              const st = String(trackedOrder.status || "new");
              const step2 = ["confirmed", "preparing", "ready_for_shipment", "shipped", "delivered"].includes(st);
              const step3 = ["shipped", "delivered"].includes(st);
              const step4 = st === "delivered";
              const isCancelOrReturn = st === "cancelled" || st === "returned";
              return isCancelOrReturn ? (
                <div className="p-2 rounded-xl bg-red-50 border border-red-200 text-red-800 font-bold text-center">
                  Statut de la commande : {st === "cancelled" ? "Annulée" : "Retournée"}
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-1.5 text-[10px] font-bold text-center">
                  <div className="py-1 rounded bg-[#063D2E] text-[#D4AF62]">1. Reçue</div>
                  <div className={`py-1 rounded ${step2 ? "bg-[#063D2E] text-[#D4AF62]" : "bg-[#F8F6F0] text-gray-500"}`}>2. Confirmée</div>
                  <div className={`py-1 rounded ${step3 ? "bg-[#063D2E] text-[#D4AF62]" : "bg-[#F8F6F0] text-gray-500"}`}>3. Expédiée</div>
                  <div className={`py-1 rounded ${step4 ? "bg-[#063D2E] text-[#D4AF62]" : "bg-[#F8F6F0] text-gray-500"}`}>4. Livrée (COD)</div>
                </div>
              );
            })()}
            <p className="font-bold text-emerald-900">Total à régler à la réception : {trackedOrder.total_dzd} DA</p>
          </div>
        )}
      </section>

      {orderConfirmed && (
        <div className="max-w-xl mx-auto p-6 bg-emerald-50 border-2 border-[#D4AF62] rounded-2xl my-4 text-xs space-y-2">
          <p className="font-bold text-emerald-950 text-sm">✓ Commande confirmée : #{orderConfirmed.order_reference} — Total : {orderConfirmed.total_dzd} DA</p>
          <a
            href={`https://wa.me/213655534154?text=${encodeURIComponent(`Bonjour Mus Luxury, je confirme ma commande #${orderConfirmed.order_reference} (${orderConfirmed.total_dzd} DA)`)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold"
          >
            Confirmer par WhatsApp (0655 53 41 54)
          </a>
        </div>
      )}

      {activeStaticPage && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 space-y-3 text-xs border border-[#D4AF62]">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-serif font-bold text-[#063D2E]">{activeStaticPage.title_fr}</h3>
              <button onClick={() => setActiveStaticPage(null)} className="font-bold">✕</button>
            </div>
            <p className="leading-relaxed">{activeStaticPage.content_fr}</p>
          </div>
        </div>
      )}

      {selectedProduct && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 space-y-4 border-2 border-[#D4AF62]">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-serif font-bold text-[#063D2E]">{selectedProduct.name_fr}</h2>
              <button onClick={() => setSelectedProduct(null)} className="text-sm font-bold">✕</button>
            </div>
            <p className="text-xl font-extrabold text-[#B68F40]">
              {selectedVariant?.effective_price_dzd ?? selectedProduct.selling_price_dzd} DA
            </p>
            {(selectedProduct.category?.attributes || [])
              .filter((a: any) => a.is_variant_axis)
              .map((axis: any) => (
                <div key={axis.attr_key} className="space-y-1.5">
                  <p className="text-xs font-bold">{axis.label_fr} : {selectedAxes[axis.attr_key]}</p>
                  <div className="flex flex-wrap gap-2">
                    {(axis.options || []).map((opt: any) => (
                      <button
                        key={opt.value}
                        onClick={() => handleSelectAxis(axis.attr_key, opt.value)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold border ${
                          selectedAxes[axis.attr_key] === opt.value
                            ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]"
                            : "bg-white text-[#202923] border-gray-300"
                        }`}
                      >
                        {opt.label_fr}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            <div className="pt-3 border-t text-xs space-y-1">
              {Object.entries(selectedProduct.attributes || {}).map(([k, v]) => (
                <p key={k}><strong>{k} :</strong> {String(v)}</p>
              ))}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button onClick={addToCart} className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs">
                Ajouter au panier
              </button>
              <a
                href={`https://wa.me/213655534154?text=${encodeURIComponent(`Bonjour Mus Luxury, je souhaite commander : ${selectedProduct.name_fr}`)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs text-center"
              >
                Commander via WhatsApp (0655 53 41 54)
              </a>
            </div>
          </div>
        </div>
      )}

      <footer className="bg-[#02291F] text-[#E8D4A5] px-6 py-6 text-xs flex flex-wrap justify-between items-center gap-4 border-t border-[#D4AF62]/30">
        <div>
          <strong>Mus Luxury</strong> — FVX6+GCJ Mus luxury, Ouled Yaïch (Blida 09) • WhatsApp :{" "}
          <a href="https://wa.me/213655534154" className="underline text-[#D4AF62] font-mono">0655 53 41 54</a>
        </div>
        <div className="flex gap-4">
          <a href="https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux" target="_blank" rel="noopener noreferrer" className="underline">
            Instagram @musluxury09
          </a>
          <a href="https://www.tiktok.com/@musluxury.092?_r=1&_t=ZS-9B2mO0gpA7V" target="_blank" rel="noopener noreferrer" className="underline">
            TikTok @musluxury.092
          </a>
        </div>
      </footer>
    </div>
  );
}
