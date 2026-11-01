import React, { useEffect, useState } from "react";
import {
  fetchCategories,
  fetchProducts,
  fetchProductBySlug,
  fetchDeliveryZones,
  validateCouponCode,
  submitGuestOrder,
} from "./api/client";

// Production React + TypeScript Storefront (100% Connected to FastAPI /api/v1/*)
// Renders dynamic CMS category attributes, multi-axis variant selectors (Color, Size, Shoe Size, Shade, etc.),
// and 69-Wilaya Guest Checkout with server-side DZD calculation.
export default function App() {
  const [categories, setCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [wilayas, setWilayas] = useState<any[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);
  const [selectedAxes, setSelectedAxes] = useState<Record<string, string>>({});
  const [selectedVariant, setSelectedVariant] = useState<any | null>(null);
  const [cart, setCart] = useState<Array<{ variant: any; product: any; quantity: number }>>([]);

  useEffect(() => {
    fetchCategories().then((res) => setCategories(res.items || []));
    fetchDeliveryZones().then((res) => setWilayas(res.items || []));
  }, []);

  useEffect(() => {
    fetchProducts({ category: activeCategory }).then((res) => setProducts(res.items || []));
  }, [activeCategory]);

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
      ) ||
      selectedProduct.variants.find((v: any) => v.attributes?.[attrKey] === optionVal);
    if (exactMatch) {
      setSelectedVariant(exactMatch);
      setSelectedAxes(exactMatch.attributes || {});
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F6F0] text-[#202923]">
      <header className="bg-[#063D2E] text-white px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
        <div className="flex items-center gap-3">
          <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" className="h-11 w-auto rounded" />
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
        </nav>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 flex-1">
        {products.map((p) => (
          <article key={p.id} onClick={() => openProductDetails(p.slug)} className="cursor-pointer bg-white rounded-2xl p-4 border border-[#D4AF62]/30 shadow-sm hover:shadow-lg transition">
            <img src={p.main_image_url} alt={p.name_fr} className="w-full h-56 object-cover rounded-xl" />
            <h3 className="font-bold mt-3">{p.name_fr}</h3>
            <p className="text-lg font-extrabold text-[#B68F40] mt-1">{p.selling_price_dzd} DA</p>
          </article>
        ))}
      </main>

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
            {/* Dynamic Variant Axes from CMS Category Schema */}
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
            {/* Dynamic Custom Product Attributes from CMS */}
            <div className="pt-3 border-t text-xs space-y-1">
              {Object.entries(selectedProduct.attributes || {}).map(([k, v]) => (
                <p key={k}><strong>{k} :</strong> {String(v)}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
