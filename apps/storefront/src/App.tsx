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

export default function App() {
  const [layout, setLayout] = useState<any | null>(null);
  const [categories, setCategories] = useState<any[]>([]);
  const [activeCategoryDetail, setActiveCategoryDetail] = useState<any | null>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [wilayas, setWilayas] = useState<any[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("");
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
  const [errorMsg, setErrorMsg] = useState("");

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
    fetchProducts({ category: activeCategory }).then((res) => setProducts(res.items || []));
    if (activeCategory) {
      fetchCategoryBySlug(activeCategory).then((cat) => setActiveCategoryDetail(cat)).catch(() => setActiveCategoryDetail(null));
    } else {
      setActiveCategoryDetail(null);
    }
  }, [activeCategory]);

  const subtotal = cart.reduce(
    (sum, it) => sum + (it.variant.effective_price_dzd ?? it.product.selling_price_dzd) * it.quantity,
    0
  );

  useEffect(() => {
    if (selectedWilaya) {
      calculateDeliveryTotal(selectedWilaya, deliveryMethod, subtotal, appliedCoupon?.code)
        .then((res) => {
          setCalcPreview(res);
          if (res.communes?.length && !res.communes.includes(commune)) {
            setCommune(res.communes[0]);
          }
        })
        .catch(() => {});
    }
  }, [selectedWilaya, deliveryMethod, subtotal, appliedCoupon]);

  async function openProductDetails(slug: string) {
    const fullProd = await fetchProductBySlug(slug);
    setSelectedProduct(fullProd);
    const firstAvail = fullProd.variants.find((v: any) => v.stock_qty > 0) || fullProd.variants[0];
    setSelectedVariant(firstAvail || null);
    setSelectedAxes(firstAvail?.attributes || {});
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
    setCart((prev) => [...prev, { product: selectedProduct, variant: selectedVariant, quantity: 1 }]);
    setSelectedProduct(null);
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
    } catch (err: any) {
      setAppliedCoupon(null);
      setErrorMsg(err.message || "Code promo invalide");
    }
  }

  async function handleTrackOrder(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg("");
    try {
      const ord = await trackGuestOrder(trackRef.trim(), trackPhone.trim());
      setTrackedOrder(ord);
    } catch (err: any) {
      setTrackedOrder(null);
      setErrorMsg(err.message || "Commande introuvable");
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
    setErrorMsg("");
    try {
      const idemKey = `order-${customerPhone}-${Date.now()}`;
      const res = await submitGuestOrder(
        {
          full_name: customerName,
          phone: customerPhone,
          wilaya_code: selectedWilaya,
          commune,
          delivery_address: address,
          delivery_method: deliveryMethod,
          coupon_code: appliedCoupon?.code || undefined,
          items: cart.map((c) => ({ variant_id: c.variant.id, quantity: c.quantity })),
        },
        idemKey
      );
      setOrderConfirmed(res);
      setCart([]);
      setAppliedCoupon(null);
    } catch (err: any) {
      setErrorMsg(err.message || "Erreur lors de la validation de la commande");
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F6F0] text-[#202923]">
      <header className="bg-[#063D2E] text-white px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
        <div className="flex items-center gap-3">
          <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" className="h-11 w-auto rounded" />
          <a
            href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[#E8D4A5] underline hidden sm:inline"
          >
            {layout?.settings?.store_location || layout?.settings?.address_fr || "FVX6+GCJ Mus luxury, Ouled Yaïch"}
          </a>
        </div>
        <nav className="flex gap-2 text-xs overflow-x-auto">
          <button onClick={() => setActiveCategory("")} className="px-3.5 py-1.5 rounded-full bg-[#D4AF62] text-[#02291F] font-bold">
            Accueil
          </button>
          {categories.map((c) => (
            <button key={c.slug} onClick={() => setActiveCategory(c.slug)} className="px-3.5 py-1.5 rounded-full hover:bg-[#02291F] text-[#E8D4A5]">
              {c.name_fr}
            </button>
          ))}
          <button onClick={() => handleOpenStaticPage("about")} className="px-3.5 py-1.5 rounded-full hover:bg-[#02291F] text-[#D4AF62]">
            La Maison
          </button>
        </nav>
      </header>

      {activeCategoryDetail && (
        <div className="max-w-7xl mx-auto px-6 pt-4 text-xs text-[#063D2E] font-semibold">
          Collection : {activeCategoryDetail.name_fr} ({activeCategoryDetail.attributes?.length || 0} attributs dynamiques)
        </div>
      )}

      <main className="max-w-7xl mx-auto p-4 sm:p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 items-stretch flex-1">
        {products.map((p) => (
          <article key={p.id} onClick={() => openProductDetails(p.slug)} className="cursor-pointer bg-white rounded-2xl p-4 border border-[#D4AF62]/30 shadow-sm hover:shadow-lg transition">
            <img src={p.main_image_url} alt={p.name_fr} className="w-full h-56 object-cover rounded-xl" />
            <h3 className="font-bold mt-3">{p.name_fr}</h3>
            <p className="text-lg font-extrabold text-[#B68F40] mt-1">{p.selling_price_dzd} DA</p>
          </article>
        ))}
      </main>

      {cart.length > 0 && (
        <section className="max-w-3xl mx-auto w-full p-6 bg-white rounded-2xl border border-[#D4AF62]/40 my-6 space-y-4 text-xs">
          <h3 className="text-lg font-serif font-bold text-[#063D2E]">Commande Directe (69 Wilayas • Paiement à la livraison)</h3>
          {errorMsg && <div className="p-3 rounded bg-red-100 text-red-800 font-bold">{errorMsg}</div>}
          <form onSubmit={handleCheckout} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} required placeholder="Nom complet" className="px-3 py-2 border rounded-xl" />
              <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} required placeholder="0655 53 41 54" className="px-3 py-2 border rounded-xl font-mono" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <select value={selectedWilaya} onChange={(e) => setSelectedWilaya(e.target.value)} className="px-3 py-2 border rounded-xl bg-white font-bold">
                {wilayas.map((w) => (
                  <option key={w.wilaya_code} value={w.wilaya_code}>
                    {w.wilaya_code} - {w.wilaya_name_fr}
                  </option>
                ))}
              </select>
              <select value={deliveryMethod} onChange={(e) => setDeliveryMethod(e.target.value as "home" | "stop_desk")} className="px-3 py-2 border rounded-xl bg-white font-bold">
                <option value="home">À Domicile ({calcPreview?.home_rate?.fee_dzd ?? 500} DA)</option>
                <option value="stop_desk">Stop-Desk ({calcPreview?.stop_desk_rate?.fee_dzd ?? 350} DA)</option>
              </select>
            </div>
            <input value={address} onChange={(e) => setAddress(e.target.value)} required placeholder="Adresse de livraison" className="w-full px-3 py-2 border rounded-xl" />
            <div className="flex gap-2">
              <input value={couponInput} onChange={(e) => setCouponInput(e.target.value)} placeholder="Code promo" className="flex-1 px-3 py-2 border rounded-xl font-mono uppercase" />
              <button type="button" onClick={handleApplyCoupon} className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
                Appliquer
              </button>
            </div>
            <div className="p-3 rounded-xl bg-[#F8F6F0] font-extrabold text-sm text-[#063D2E]">
              Total (Articles + Livraison {selectedWilaya}) : {calcPreview?.total_dzd ?? subtotal} DA
            </div>
            <button type="submit" className="w-full py-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold">
              Confirmer la commande
            </button>
          </form>
        </section>
      )}

      <section className="max-w-3xl mx-auto w-full px-6 pb-6 text-xs">
        <form onSubmit={handleTrackOrder} className="bg-white p-4 rounded-2xl border border-[#D4AF62]/30 flex flex-wrap gap-2 items-center">
          <span className="font-bold text-[#063D2E]">Suivi de commande :</span>
          <input value={trackRef} onChange={(e) => setTrackRef(e.target.value)} placeholder="Réf (ex: LUX-12345)" className="px-3 py-1.5 border rounded-xl font-mono uppercase" />
          <input value={trackPhone} onChange={(e) => setTrackPhone(e.target.value)} placeholder="0655 53 41 54" className="px-3 py-1.5 border rounded-xl font-mono" />
          <button type="submit" className="px-4 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">Suivre</button>
          {trackedOrder && (
            <span className="font-bold text-emerald-800 ml-2">
              #{trackedOrder.order_reference} — Statut : {trackedOrder.status} ({trackedOrder.total_dzd} DA)
            </span>
          )}
        </form>
      </section>

      {orderConfirmed && (
        <div className="max-w-xl mx-auto p-6 bg-emerald-50 border border-emerald-300 rounded-2xl my-4 text-xs">
          <p className="font-bold text-emerald-900">Commande confirmée : #{orderConfirmed.order_reference} — Total : {orderConfirmed.total_dzd} DA</p>
        </div>
      )}

      {activeStaticPage && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 space-y-3 text-xs">
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
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 space-y-4">
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
            <button onClick={addToCart} className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs">
              Ajouter au panier
            </button>
          </div>
        </div>
      )}

      <footer className="bg-[#02291F] text-[#E8D4A5] px-6 py-6 text-xs flex flex-wrap justify-between items-center gap-4">
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
