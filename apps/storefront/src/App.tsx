import React, { useEffect, useState } from "react";
import { fetchCategories, fetchProducts, submitGuestOrder } from "./api/client";

// Pure Public E-Commerce Website (Storefront)
// Connects strictly to public /api/v1/* endpoints. Contains zero CMS or admin code.
export default function App() {
  const [categories, setCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("");

  useEffect(() => {
    fetchCategories().then((res) => setCategories(res.items || []));
  }, []);

  useEffect(() => {
    fetchProducts({ category: activeCategory }).then((res) => setProducts(res.items || []));
  }, [activeCategory]);

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F6F0] text-[#202923]">
      <header className="bg-[#063D2E] text-white px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
        <div className="flex items-center gap-3">
          <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" className="h-12 w-auto rounded" />
          <span className="font-serif text-xl text-[#D4AF62] font-bold">MUS LUXURY</span>
        </div>
        <nav className="flex gap-3 text-sm overflow-x-auto">
          <button onClick={() => setActiveCategory("")} className="px-3 py-1 rounded bg-[#D4AF62] text-[#02291F] font-bold">Accueil</button>
          {categories.map((c) => (
            <button key={c.slug} onClick={() => setActiveCategory(c.slug)} className="px-3 py-1 rounded hover:bg-[#02291F] text-[#E8D4A5]">
              {c.name_fr}
            </button>
          ))}
        </nav>
      </header>
      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 flex-1">
        {products.map((p) => (
          <article key={p.id} className="bg-white rounded-2xl p-4 border border-[#D4AF62]/30 shadow-sm">
            <img src={p.main_image_url} alt={p.name_fr} className="w-full h-52 object-cover rounded-xl" />
            <h3 className="font-bold mt-3">{p.name_fr}</h3>
            <p className="text-lg font-extrabold text-[#063D2E] mt-1">{p.selling_price_dzd} DA</p>
          </article>
        ))}
      </main>
    </div>
  );
}
