import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";

const ATTRIBUTE_TYPES = [
  "short_text",
  "long_text",
  "number",
  "price",
  "boolean",
  "single_select",
  "multi_select",
  "color",
  "size",
  "image",
  "date",
  "measurement",
  "brand",
  "barcode_sku",
];

interface DraftAttribute {
  attr_key: string;
  label_fr: string;
  label_ar: string;
  label_en: string;
  input_type: string;
  unit: string;
  is_required: boolean;
  is_filterable: boolean;
  is_variant_axis: boolean;
  options_csv: string;
}

export function CategoryBuilderPage({ onCategoryChanged }: { onCategoryChanged?: () => void }) {
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  const [nameFr, setNameFr] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [slug, setSlug] = useState("");
  const [descriptionFr, setDescriptionFr] = useState("");
  const [displayOrder, setDisplayOrder] = useState(10);
  const [attributes, setAttributes] = useState<DraftAttribute[]>([
    {
      attr_key: "color",
      label_fr: "Couleur",
      label_ar: "اللون",
      label_en: "Color",
      input_type: "color",
      unit: "",
      is_required: true,
      is_filterable: true,
      is_variant_axis: true,
      options_csv: "Noir, Or, Vert Émeraude",
    },
    {
      attr_key: "size",
      label_fr: "Taille / Pointure",
      label_ar: "المقاس",
      label_en: "Size",
      input_type: "size",
      unit: "",
      is_required: true,
      is_filterable: true,
      is_variant_axis: true,
      options_csv: "S, M, L",
    },
  ]);

  // New attribute draft inputs
  const [newKey, setNewKey] = useState("");
  const [newLabelFr, setNewLabelFr] = useState("");
  const [newType, setNewType] = useState("short_text");
  const [newUnit, setNewUnit] = useState("");
  const [newRequired, setNewRequired] = useState(false);
  const [newFilterable, setNewFilterable] = useState(true);
  const [newVariantAxis, setNewVariantAxis] = useState(false);
  const [newOptionsCsv, setNewOptionsCsv] = useState("");

  async function loadCategories() {
    setLoading(true);
    setError("");
    try {
      const res = await DesktopCmsApi.listCategories();
      setCategories(res.items || []);
    } catch (err: any) {
      setError(err.message || "Erreur lors du chargement des catégories");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

  function addDraftAttribute() {
    const cleanKey = newKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanKey || !newLabelFr.trim()) return;
    setAttributes((prev) => [
      ...prev,
      {
        attr_key: cleanKey,
        label_fr: newLabelFr.trim(),
        label_ar: newLabelFr.trim(),
        label_en: newLabelFr.trim(),
        input_type: newType,
        unit: newUnit.trim(),
        is_required: newRequired,
        is_filterable: newFilterable,
        is_variant_axis: newVariantAxis,
        options_csv: newOptionsCsv,
      },
    ]);
    setNewKey("");
    setNewLabelFr("");
    setNewOptionsCsv("");
  }

  function removeDraftAttribute(idx: number) {
    setAttributes((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSaveCategory(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setStatusMsg("");
    try {
      const created = await DesktopCmsApi.createCategory({
        slug: slug.trim().toLowerCase(),
        name_fr: nameFr.trim(),
        name_ar: (nameAr || nameFr).trim(),
        name_en: (nameEn || nameFr).trim(),
        description_fr: descriptionFr.trim(),
        display_order: Number(displayOrder) || 10,
        is_active: true,
        show_on_homepage: true,
      });

      for (let i = 0; i < attributes.length; i++) {
        const attr = attributes[i];
        const parsedOptions = attr.options_csv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .map((val, idx) => ({
            value: val,
            label_fr: val,
            label_ar: val,
            label_en: val,
            display_order: idx + 1,
          }));

        await DesktopCmsApi.addCategoryAttribute({
          category_id: created.id,
          attr_key: attr.attr_key,
          label_fr: attr.label_fr,
          label_ar: attr.label_ar,
          label_en: attr.label_en,
          input_type: attr.input_type,
          unit: attr.unit,
          is_required: attr.is_required,
          is_filterable: attr.is_filterable,
          is_variant_axis: attr.is_variant_axis,
          display_order: i + 1,
          options: parsedOptions,
        });
      }

      setStatusMsg(`Catégorie "${nameFr}" et ses ${attributes.length} attribut(s) enregistrés sur le serveur.`);
      setNameFr("");
      setNameAr("");
      setNameEn("");
      setSlug("");
      setDescriptionFr("");
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      setError(err.message || "Erreur lors de la création de la catégorie");
    }
  }

  async function handleDeleteAttribute(attrId: number) {
    setError("");
    try {
      await DesktopCmsApi.deleteCategoryAttribute(attrId, true);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      setError(err.message || "Impossible de supprimer l'attribut");
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSaveCategory} className="space-y-4 bg-white p-6 rounded-2xl border border-[#D4AF62]/40 shadow-sm">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 className="text-xl font-serif font-bold text-[#063D2E]">+ Ajouter une catégorie personnalisée &amp; ses attributs</h2>
            <p className="text-xs text-gray-500">
              Les attributs définis ici adaptent automatiquement le formulaire Produit, les filtres et les sélecteurs client (Couleur, Taille, Pointure, Calibre, etc.).
            </p>
          </div>
        </div>

        {statusMsg && <div className="p-3 rounded-xl bg-emerald-100 text-emerald-900 text-xs font-bold">{statusMsg}</div>}
        {error && <div className="p-3 rounded-xl bg-red-100 text-red-800 text-xs font-bold">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div>
            <label className="block font-bold mb-1">Nom (FR) *</label>
            <input
              value={nameFr}
              onChange={(e) => {
                setNameFr(e.target.value);
                if (!slug) {
                  setSlug(
                    e.target.value
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-|-$/g, "")
                  );
                }
              }}
              placeholder="ex: Parfums"
              required
              className="w-full px-3 py-2 border rounded-xl"
            />
          </div>
          <div>
            <label className="block font-bold mb-1">Nom (AR)</label>
            <input value={nameAr} onChange={(e) => setNameAr(e.target.value)} placeholder="عطور" dir="rtl" className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">Nom (EN)</label>
            <input value={nameEn} onChange={(e) => setNameEn(e.target.value)} placeholder="Perfumes" className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">Slug URL *</label>
            <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="parfums-luxe" required className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="md:col-span-3">
            <label className="block font-bold mb-1">Description (FR)</label>
            <input value={descriptionFr} onChange={(e) => setDescriptionFr(e.target.value)} placeholder="Description affichée sur la boutique..." className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">Ordre d'affichage</label>
            <input type="number" value={displayOrder} onChange={(e) => setDisplayOrder(Number(e.target.value))} className="w-full px-3 py-2 border rounded-xl" />
          </div>
        </div>

        {/* Dynamic Attribute Builder Section */}
        <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-3 text-xs">
          <h3 className="font-bold text-[#063D2E]">Attributs dynamiques de cette catégorie ({attributes.length})</h3>

          <div className="space-y-2">
            {attributes.map((attr, idx) => (
              <div key={idx} className="flex flex-wrap items-center justify-between gap-2 bg-white p-2.5 rounded-lg border">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-bold text-[#063D2E]">{attr.attr_key}</span>
                  <span className="font-semibold">{attr.label_fr}</span>
                  <span className="px-2 py-0.5 rounded bg-gray-100 text-[11px] font-mono">{attr.input_type}</span>
                  {attr.is_variant_axis && <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 text-[10px] font-bold">Axe de variante (Stock/Prix)</span>}
                  {attr.is_filterable && <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-bold">Filtrable</span>}
                  {attr.options_csv && <span className="text-gray-500">Options: [{attr.options_csv}]</span>}
                </div>
                <button type="button" onClick={() => removeDraftAttribute(idx)} className="text-red-600 font-bold hover:underline">
                  Retirer
                </button>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-6 gap-2 pt-2 border-t border-gray-200 items-end">
            <div>
              <label className="block font-semibold mb-1">Clé technique</label>
              <input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="ex: volume_ml" className="w-full px-2.5 py-1.5 border rounded-lg font-mono" />
            </div>
            <div>
              <label className="block font-semibold mb-1">Libellé (FR)</label>
              <input value={newLabelFr} onChange={(e) => setNewLabelFr(e.target.value)} placeholder="ex: Contenance" className="w-full px-2.5 py-1.5 border rounded-lg" />
            </div>
            <div>
              <label className="block font-semibold mb-1">Type de champ</label>
              <select value={newType} onChange={(e) => setNewType(e.target.value)} className="w-full px-2.5 py-1.5 border rounded-lg bg-white">
                {ATTRIBUTE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block font-semibold mb-1">Options (séparées par virgule)</label>
              <input value={newOptionsCsv} onChange={(e) => setNewOptionsCsv(e.target.value)} placeholder="ex: 50ml, 100ml" className="w-full px-2.5 py-1.5 border rounded-lg" />
            </div>
            <div>
              <button type="button" onClick={addDraftAttribute} className="w-full py-1.5 px-3 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold">
                + Ajouter attribut
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 pt-1">
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={newVariantAxis} onChange={(e) => setNewVariantAxis(e.target.checked)} />
              <span>Axe de variante (génère déclinaisons &amp; stock dédié)</span>
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={newFilterable} onChange={(e) => setNewFilterable(e.target.checked)} />
              <span>Afficher dans les filtres boutique</span>
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={newRequired} onChange={(e) => setNewRequired(e.target.checked)} />
              <span>Champ obligatoire</span>
            </label>
          </div>
        </div>

        <button type="submit" className="px-6 py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs shadow">
          Enregistrer &amp; Publier la Catégorie sur le Serveur (/api/v1/admin/categories)
        </button>
      </form>

      {/* Existing Categories & Attributes List */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-serif font-bold text-[#063D2E]">Catégories Actives ({categories.length})</h3>
          <button type="button" onClick={loadCategories} className="text-xs font-bold text-[#063D2E] underline">
            Actualiser
          </button>
        </div>
        {loading ? (
          <p className="text-xs text-gray-500">Chargement des catégories depuis le serveur...</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {categories.map((c) => (
              <div key={c.id} className="p-4 rounded-xl border border-gray-200 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-[#063D2E]">
                    {c.name_fr} <span className="text-gray-400 font-mono text-xs">({c.slug})</span>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 font-bold text-[11px]">
                    {(c.attributes || []).length} attribut(s)
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(c.attributes || []).map((a: any) => (
                    <span key={a.id} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#F8F6F0] border text-[11px]">
                      <strong>{a.label_fr}</strong> ({a.input_type}{a.is_variant_axis ? " • Variante" : ""})
                      <button
                        type="button"
                        onClick={() => handleDeleteAttribute(a.id)}
                        className="text-red-600 font-bold ml-1 hover:underline"
                        title="Supprimer cet attribut"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
