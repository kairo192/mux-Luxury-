import React, { useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";

const ATTRIBUTE_TYPES = [
  "short_text", "long_text", "number", "price", "boolean",
  "single_select", "multi_select", "color", "size", "image",
  "date", "measurement", "brand", "barcode_sku"
];

export function CategoryBuilderPage() {
  const [nameFr, setNameFr] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [slug, setSlug] = useState("");
  const [attributes, setAttributes] = useState<any[]>([]);
  const [statusMsg, setStatusMsg] = useState("");

  async function handleSaveCategory(e: React.FormEvent) {
    e.preventDefault();
    const created = await DesktopCmsApi.createCategory({
      slug,
      name_fr: nameFr,
      name_ar: nameAr || nameFr,
      name_en: nameEn || nameFr,
      is_active: true,
      show_on_homepage: true,
    });
    for (const attr of attributes) {
      await DesktopCmsApi.addCategoryAttribute({
        category_id: created.id,
        ...attr,
      });
    }
    setStatusMsg(`Catégorie "${nameFr}" synchronisée sur le serveur et publiée sur le site web.`);
  }

  return (
    <form onSubmit={handleSaveCategory} className="space-y-4 bg-white p-6 rounded-2xl border border-[#D4AF62]/40">
      <h2 className="text-xl font-serif font-bold text-[#063D2E]">+ Ajouter une catégorie personnalisée</h2>
      {statusMsg && <div className="p-3 rounded bg-emerald-100 text-emerald-900 text-xs font-bold">{statusMsg}</div>}
      <div className="grid grid-cols-3 gap-3">
        <input value={nameFr} onChange={(e) => setNameFr(e.target.value)} placeholder="Nom FR" required className="px-3 py-2 border rounded" />
        <input value={nameAr} onChange={(e) => setNameAr(e.target.value)} placeholder="Nom AR" dir="rtl" className="px-3 py-2 border rounded" />
        <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="slug-categorie" required className="px-3 py-2 border rounded font-mono" />
      </div>
      <button type="submit" className="px-5 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs">
        Synchroniser avec le serveur (/api/v1/admin/categories)
      </button>
    </form>
  );
}
