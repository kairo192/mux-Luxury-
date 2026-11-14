// Part of the category builder (pages/CategoryBuilderPage.tsx), which owns the state.
import React from "react";
import { useT } from "../../i18n";
import { PLACEHOLDER_IMG, mediaUrl } from "../../api/adminClient";
import { ImageUploadField } from "../../components/ImageUploadField";
import { ATTRIBUTE_TYPES, LUXURY_PALETTE, getCategoryIconComponent, typeLabel } from "./catalogSetup";
import { CATEGORY_PRESETS } from "./presets";
import { Check, ChevronDown, ChevronUp, Eye, Palette, Plus, Shirt, SlidersHorizontal, Sparkles, Trash2, X } from "lucide-react";
import type { CategoryPreset, DraftAttribute, DraftAttributeOption } from "./catalogSetup";

/** New category: presets, names, pictures, attributes, live shop preview. */
export function CategoryCreateForm({ handleSaveCategory, setShowCreateForm, activePresetId, applyCategoryPreset, nameFr, setNameFr, slug, setSlug, nameAr, setNameAr, nameEn, setNameEn, descriptionFr, setDescriptionFr, displayOrder, setDisplayOrder, imageUrl, setImageUrl, bannerUrl, setBannerUrl, attributes, moveDraftAttribute, removeDraftAttribute, newKey, setNewKey, newLabelFr, setNewLabelFr, newType, setNewType, newUnit, setNewUnit, setTempColorName, setTempColorHex, tempColorHex, tempColorName, addColorToRichList, newRichColors, removeColorFromRichList, setNewOptionsCsv, newOptionsCsv, newVariantAxis, setNewVariantAxis, newFilterable, setNewFilterable, newVisibleOnStorefront, setNewVisibleOnStorefront, newRequired, setNewRequired, addDraftAttribute }: {
  handleSaveCategory: (e: React.FormEvent) => Promise<void>;
  setShowCreateForm: React.Dispatch<React.SetStateAction<boolean>>;
  activePresetId: string | null;
  applyCategoryPreset: (preset: CategoryPreset) => void;
  nameFr: string;
  setNameFr: React.Dispatch<React.SetStateAction<string>>;
  slug: string;
  setSlug: React.Dispatch<React.SetStateAction<string>>;
  nameAr: string;
  setNameAr: React.Dispatch<React.SetStateAction<string>>;
  nameEn: string;
  setNameEn: React.Dispatch<React.SetStateAction<string>>;
  descriptionFr: string;
  setDescriptionFr: React.Dispatch<React.SetStateAction<string>>;
  displayOrder: number;
  setDisplayOrder: React.Dispatch<React.SetStateAction<number>>;
  imageUrl: string;
  setImageUrl: React.Dispatch<React.SetStateAction<string>>;
  bannerUrl: string;
  setBannerUrl: React.Dispatch<React.SetStateAction<string>>;
  attributes: DraftAttribute[];
  moveDraftAttribute: (idx: number, dir: "up" | "down") => void;
  removeDraftAttribute: (idx: number) => void;
  newKey: string;
  setNewKey: React.Dispatch<React.SetStateAction<string>>;
  newLabelFr: string;
  setNewLabelFr: React.Dispatch<React.SetStateAction<string>>;
  newType: string;
  setNewType: React.Dispatch<React.SetStateAction<string>>;
  newUnit: string;
  setNewUnit: React.Dispatch<React.SetStateAction<string>>;
  setTempColorName: React.Dispatch<React.SetStateAction<string>>;
  setTempColorHex: React.Dispatch<React.SetStateAction<string>>;
  tempColorHex: string;
  tempColorName: string;
  addColorToRichList: () => void;
  newRichColors: DraftAttributeOption[];
  removeColorFromRichList: (val: string) => void;
  setNewOptionsCsv: React.Dispatch<React.SetStateAction<string>>;
  newOptionsCsv: string;
  newVariantAxis: boolean;
  setNewVariantAxis: React.Dispatch<React.SetStateAction<boolean>>;
  newFilterable: boolean;
  setNewFilterable: React.Dispatch<React.SetStateAction<boolean>>;
  newVisibleOnStorefront: boolean;
  setNewVisibleOnStorefront: React.Dispatch<React.SetStateAction<boolean>>;
  newRequired: boolean;
  setNewRequired: React.Dispatch<React.SetStateAction<boolean>>;
  addDraftAttribute: () => void;
}) {
  const t = useT();
  return (
    <form
      onSubmit={handleSaveCategory}
      className="bg-white p-6 rounded-2xl border-2 border-[#D4AF62] shadow-xl space-y-6 animate-in fade-in duration-200"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#D4AF62]/30 pb-3">
        <div>
          <h2 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-[#D4AF62]" />
            <span>{t("cat_builder.form_create_title")}</span>
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {t("cat_builder.form_create_sub")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreateForm(false)}
          className="p-1 rounded-lg text-gray-400 hover:text-gray-700 transition"
          aria-label="Fermer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* 1. Guided Reusable Presets Toolbar */}
      <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#D4AF62]" />
            <span>{t("cat_builder.presets_title")}</span>
          </span>
          <span className="text-[11px] text-gray-500">{t("cat_builder.presets_hint")}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORY_PRESETS.map((preset) => {
            const IconComp = preset.iconName === "shirt" ? Shirt : getCategoryIconComponent(preset.slug, preset.iconName);
            const isSelected = activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyCategoryPreset(preset)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition border ${
                  isSelected
                    ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E] shadow-sm"
                    : "bg-white text-gray-800 border-gray-200 hover:border-[#D4AF62] hover:bg-amber-50/50"
                }`}
              >
                <IconComp className="w-3.5 h-3.5 text-[#D4AF62]" />
                <span>{preset.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Category Identity Inputs */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#063D2E] uppercase tracking-wider border-b border-gray-200 pb-1">
          1. Identité &amp; Informations de la Catégorie
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div>
            <label className="block font-bold text-[#063D2E] mb-1">Nom Français (FR) *</label>
            <input
              value={nameFr}
              onChange={(e) => {
                setNameFr(e.target.value);
                if (!slug) {
                  setSlug(
                    e.target.value
                      .toLowerCase()
                      .normalize("NFD")
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-|-$/g, "")
                  );
                }
              }}
              placeholder="ex: T-shirts & Prêt-à-porter"
              required
              className="w-full px-3 py-2 border rounded-xl font-semibold"
            />
          </div>
          <div>
            <label className="block font-bold text-[#063D2E] mb-1">Nom Arabe (AR)</label>
            <input
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              placeholder="قمصان وملابس فاخرة"
              dir="rtl"
              className="w-full px-3 py-2 border rounded-xl"
            />
          </div>
          <div>
            <label className="block font-bold text-[#063D2E] mb-1">Nom Anglais (EN)</label>
            <input
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
              placeholder="T-Shirts & Apparel"
              className="w-full px-3 py-2 border rounded-xl"
            />
          </div>
          <div>
            <label className="block font-bold text-[#063D2E] mb-1">Identifiant URL (Slug) *</label>
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="t-shirts"
              required
              className="w-full px-3 py-2 border rounded-xl font-mono text-gray-700"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="md:col-span-3">
            <label className="block font-bold text-[#063D2E] mb-1">Description (FR)</label>
            <input
              value={descriptionFr}
              onChange={(e) => setDescriptionFr(e.target.value)}
              placeholder="T-shirts d'exception, polos raffinés et créations prêt-à-porter en coton Pima noble."
              className="w-full px-3 py-2 border rounded-xl"
            />
          </div>
          <div>
            <label className="block font-bold text-[#063D2E] mb-1">Ordre d'affichage</label>
            <input
              type="number"
              value={displayOrder}
              onChange={(e) => setDisplayOrder(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-xl font-mono"
            />
          </div>
        </div>

        {/* Visual Media Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-1">
          <ImageUploadField
            label="Photo de la catégorie"
            value={imageUrl}
            onChange={setImageUrl}
            hint="Affichée dans « Nos catégories » sur la boutique. Sans photo, une vignette neutre est affichée."
          />
          <ImageUploadField
            label="Bannière (haut de la page catégorie)"
            value={bannerUrl}
            onChange={setBannerUrl}
            wide
            hint="Optionnelle."
          />
        </div>
      </div>

      {/* 3. Two-Column Layout: Attributes Manager (Left) + Live Category Card Preview (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-2 border-t border-gray-200">
        {/* Left Column: Attributes & Options Builder */}
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-[#D4AF62]" />
              <span>2. Modèle d'Attributs &amp; Déclinaisons ({attributes.length})</span>
            </h3>
            <span className="text-[11px] text-gray-500">
              Définissez les couleurs, tailles et caractéristiques héritées par les produits
            </span>
          </div>

          {/* Configured Attributes List */}
          <div className="space-y-2">
            {attributes.map((attr, idx) => (
              <div
                key={idx}
                className="p-3 bg-[#F8F6F0] rounded-xl border border-[#D4AF62]/35 space-y-2 hover:border-[#D4AF62] transition"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold text-[#063D2E] bg-white px-2 py-0.5 rounded border border-gray-200 text-xs">
                      {attr.attr_key}
                    </span>
                    <span className="font-bold text-gray-900 text-xs">{attr.label_fr}</span>
                    <span className="px-2 py-0.5 rounded bg-gray-200/80 text-[10px] font-mono text-gray-700">
                      {typeLabel(attr.input_type)}
                    </span>
                    {attr.is_variant_axis && (
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 text-[10px] font-bold border border-emerald-300">
                        ⚡ Axe de variante (Stock dédié)
                      </span>
                    )}
                    {attr.is_filterable && (
                      <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-bold border border-amber-300">
                        Filtre boutique
                      </span>
                    )}
                    {attr.is_required && (
                      <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-900 text-[10px] font-bold border border-rose-200">
                        Requis
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => moveDraftAttribute(idx, "up")}
                      disabled={idx === 0}
                      className="p-1 rounded text-gray-500 hover:text-gray-900 disabled:opacity-25"
                      title="Monter"
                    >
                      <ChevronUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveDraftAttribute(idx, "down")}
                      disabled={idx === attributes.length - 1}
                      className="p-1 rounded text-gray-500 hover:text-gray-900 disabled:opacity-25"
                      title="Descendre"
                    >
                      <ChevronDown className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeDraftAttribute(idx)}
                      className="p-1 rounded text-rose-600 hover:bg-rose-50 transition"
                      title="Supprimer cet attribut"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Rich Options preview */}
                {attr.rich_options && attr.rich_options.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {attr.rich_options.map((opt, oIdx) => (
                      <span
                        key={oIdx}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white border border-gray-200 text-[11px] font-medium text-gray-800 shadow-2xs"
                      >
                        <span
                          className="w-3 h-3 rounded-full border border-gray-300 shadow-xs"
                          style={{ backgroundColor: opt.color_hex || "#063D2E" }}
                        />
                        <span>{opt.value}</span>
                      </span>
                    ))}
                  </div>
                ) : attr.options_csv ? (
                  <div className="flex flex-wrap items-center gap-1 pt-1">
                    {attr.options_csv.split(",").map((v, vIdx) => (
                      <span
                        key={vIdx}
                        className="px-2 py-0.5 rounded-md bg-white border border-gray-200 text-[11px] text-gray-700 font-medium"
                      >
                        {v.trim()}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {/* Sub-Builder to add a custom attribute */}
          <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/40 shadow-sm space-y-3 text-xs">
            <span className="font-bold text-[#063D2E] uppercase tracking-wider block">
              + Ajouter un attribut sur-mesure au modèle
            </span>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <div>
                <label className="block font-semibold mb-1">Clé technique *</label>
                <input
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="ex: col_type"
                  className="w-full px-2.5 py-1.5 border rounded-lg font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">Libellé (FR) *</label>
                <input
                  value={newLabelFr}
                  onChange={(e) => setNewLabelFr(e.target.value)}
                  placeholder="ex: Type de Col"
                  className="w-full px-2.5 py-1.5 border rounded-lg"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">Type de champ</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full px-2.5 py-1.5 border rounded-lg bg-white"
                >
                  {ATTRIBUTE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-semibold mb-1">Unité (optionnelle)</label>
                <input
                  value={newUnit}
                  onChange={(e) => setNewUnit(e.target.value)}
                  placeholder="ex: cm, ml, g"
                  className="w-full px-2.5 py-1.5 border rounded-lg"
                />
              </div>
            </div>

            {/* Color Swatch Builder UI */}
            {(newType === "color" || newKey === "color" || newKey.includes("couleur")) ? (
              <div className="p-3 bg-amber-50/40 rounded-xl border border-amber-200/60 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#063D2E] flex items-center gap-1.5">
                    <Palette className="w-4 h-4 text-[#D4AF62]" />
                    <span>Nuancier Visuel &amp; Pastilles Circulaires</span>
                  </span>
                  <span className="text-[11px] text-gray-500">Ajoutez les teintes avec leur pastille couleur</span>
                </div>

                {/* Preconfigured Colors Quick Add Palette */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-bold text-gray-600 mr-1">Palettes Luxe :</span>
                  {LUXURY_PALETTE.map((pal) => (
                    <button
                      key={pal.name}
                      type="button"
                      onClick={() => {
                        setTempColorName(pal.name);
                        setTempColorHex(pal.hex);
                      }}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-gray-200 text-[10px] font-medium hover:border-[#D4AF62] transition"
                    >
                      <span className="w-2.5 h-2.5 rounded-full border border-gray-300" style={{ backgroundColor: pal.hex }} />
                      <span>{pal.name}</span>
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <div className="flex items-center gap-1.5 bg-white px-2 py-1 border rounded-lg">
                    <input
                      type="color"
                      value={tempColorHex}
                      onChange={(e) => setTempColorHex(e.target.value)}
                      className="w-6 h-6 rounded cursor-pointer border-0 p-0"
                    />
                    <input
                      value={tempColorHex}
                      onChange={(e) => setTempColorHex(e.target.value)}
                      className="w-16 font-mono text-[11px] outline-none"
                      placeholder="#063D2E"
                    />
                  </div>
                  {/* Live circular preview beside name input */}
                  <span
                    className="w-4 h-4 rounded-full border border-gray-300 shadow-xs flex-shrink-0"
                    style={{ backgroundColor: tempColorHex }}
                    title={tempColorHex}
                  />
                  <input
                    value={tempColorName}
                    onChange={(e) => setTempColorName(e.target.value)}
                    placeholder="Nom de la couleur (ex: Vert Émeraude)"
                    className="flex-1 px-2.5 py-1.5 border rounded-lg bg-white text-xs font-medium"
                  />
                  <button
                    type="button"
                    onClick={addColorToRichList}
                    className="px-3 py-1.5 bg-[#063D2E] text-[#D4AF62] font-bold rounded-lg hover:brightness-110 transition"
                  >
                    + Ajouter cette nuance
                  </button>
                </div>

                {/* Current Swatches in Draft */}
                {newRichColors.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {newRichColors.map((col) => (
                      <span
                        key={col.value}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white border border-gray-300 text-[11px] font-bold shadow-2xs"
                      >
                        <span className="w-3.5 h-3.5 rounded-full border border-gray-400" style={{ backgroundColor: col.color_hex }} />
                        <span>{col.value}</span>
                        <button aria-label="Retirer cette couleur"
                          type="button"
                          onClick={() => removeColorFromRichList(col.value)}
                          className="text-gray-400 hover:text-red-600 transition"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block font-semibold">Options prédéfinies (séparées par virgule)</label>
                  {(newType === "size" || newKey === "size" || newKey.includes("taille") || newKey.includes("pointure")) && (
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setNewOptionsCsv("XS, S, M, L, XL, XXL")}
                        className="text-[10px] text-[#063D2E] font-bold hover:underline"
                      >
                        + Tailles Vêtements
                      </button>
                      <span className="text-gray-300">·</span>
                      <button
                        type="button"
                        onClick={() => setNewOptionsCsv("36, 37, 38, 39, 40, 41, 42, 43, 44")}
                        className="text-[10px] text-[#063D2E] font-bold hover:underline"
                      >
                        + Pointures Souliers
                      </button>
                    </div>
                  )}
                </div>
                <input
                  value={newOptionsCsv}
                  onChange={(e) => setNewOptionsCsv(e.target.value)}
                  placeholder="ex: Col Rond, Col V, Col Montant"
                  className="w-full px-2.5 py-1.5 border rounded-lg"
                />
              </div>
            )}

            {/* Toggles */}
            <div className="flex flex-wrap gap-4 pt-1">
              <label className="inline-flex items-center gap-1.5 cursor-pointer font-semibold text-[#063D2E]">
                <input
                  type="checkbox"
                  checked={newVariantAxis}
                  onChange={(e) => setNewVariantAxis(e.target.checked)}
                  className="rounded text-[#063D2E]"
                />
                <span>⚡ Axe de variante (génère stocks &amp; déclinaisons)</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer font-semibold">
                <input
                  type="checkbox"
                  checked={newFilterable}
                  onChange={(e) => setNewFilterable(e.target.checked)}
                  className="rounded text-[#063D2E]"
                />
                <span>Filtrable sur la boutique</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newVisibleOnStorefront}
                  onChange={(e) => setNewVisibleOnStorefront(e.target.checked)}
                  className="rounded text-[#063D2E]"
                />
                <span>Visible sur fiche article</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                  className="rounded text-[#063D2E]"
                />
                <span>Obligatoire</span>
              </label>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={addDraftAttribute}
                className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold hover:bg-[#02291F] transition flex items-center gap-1.5"
              >
                <Plus className="w-4 h-4" />
                <span>Ajouter cet attribut au modèle</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Live Storefront Category Card & Attributes Preview */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-4 h-4 text-[#D4AF62]" />
              <span>Aperçu Vitrine en Direct</span>
            </span>
            <span className="text-[10px] font-bold text-[#D4AF62] bg-[#063D2E] px-2 py-0.5 rounded-full">
              Live Preview
            </span>
          </div>

          {/* Card Container */}
          <div className="rounded-2xl border-2 border-[#D4AF62]/50 bg-[#063D2E] text-white p-4 shadow-xl space-y-3 overflow-hidden relative">
            {/* Image Banner */}
            <div className="relative h-32 rounded-xl overflow-hidden bg-black/40 border border-white/10">
              <img
                src={imageUrl ? mediaUrl(imageUrl) : PLACEHOLDER_IMG}
                alt={nameFr || "Catégorie"}
                className="w-full h-full object-cover object-center"
                onError={(e: any) => {
                  e.target.onerror = null;
                  e.target.src = PLACEHOLDER_IMG;
                }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#063D2E] via-transparent to-black/20" />
              <span className="absolute bottom-2 left-2 text-[10px] font-mono tracking-widest text-[#D4AF62] uppercase bg-black/60 px-2 py-0.5 rounded-full backdrop-blur-xs">
                /{slug || "slug-url"}
              </span>
            </div>

            {/* Identity */}
            <div>
              <h4 className="font-serif text-lg font-bold text-[#D4AF62]">
                {nameFr || "T-shirts & Prêt-à-porter"}
              </h4>
              {nameAr && <p className="text-xs text-amber-100/70" dir="rtl">{nameAr}</p>}
              <p className="text-xs text-gray-200/90 mt-1 line-clamp-2">
                {descriptionFr || "Description de la collection d'exception..."}
              </p>
            </div>

            {/* Variant Dimensions Preview */}
            <div className="pt-2 border-t border-white/15 space-y-2 text-xs">
              <span className="text-[11px] font-bold text-[#D4AF62] uppercase tracking-wider block">
                Déclinaisons &amp; Sélecteurs Fiche Produit :
              </span>

              {attributes.filter((a) => a.is_variant_axis).length === 0 ? (
                <span className="text-[11px] text-gray-300 italic">Aucun axe de déclinaison configuré</span>
              ) : (
                attributes
                  .filter((a) => a.is_variant_axis)
                  .map((axis, aIdx) => (
                    <div key={aIdx} className="space-y-1">
                      <span className="text-[11px] text-gray-300 font-semibold">{axis.label_fr} :</span>
                      {axis.input_type === "color" && axis.rich_options ? (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {axis.rich_options.map((opt, oIdx) => (
                            <span
                              key={oIdx}
                              className="w-4 h-4 rounded-full border border-white/40 shadow-xs inline-block"
                              style={{ backgroundColor: opt.color_hex || "#FFFFFF" }}
                              title={opt.label_fr || opt.value}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="flex flex-wrap items-center gap-1">
                          {(axis.rich_options || axis.options_csv.split(",").map((v) => ({ value: v.trim() })))
                            .slice(0, 6)
                            .map((opt, oIdx) => (
                              <span
                                key={oIdx}
                                className="px-1.5 py-0.5 rounded bg-white/15 text-[9px] font-bold text-white border border-white/20"
                              >
                                {opt.value}
                              </span>
                            ))}
                        </div>
                      )}
                    </div>
                  ))
              )}
            </div>

            {/* Filters preview */}
            <div className="pt-2 border-t border-white/15 text-[10px]">
              <span className="font-bold text-amber-200/80 uppercase block mb-1">
                Filtres Boutique ({attributes.filter((a) => a.is_filterable).length}) :
              </span>
              <div className="flex flex-wrap gap-1">
                {attributes
                  .filter((a) => a.is_filterable)
                  .map((a, fIdx) => (
                    <span key={fIdx} className="px-1.5 py-0.5 rounded bg-black/40 text-amber-200 border border-white/10">
                      {a.label_fr}
                    </span>
                  ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Form Actions */}
      <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#D4AF62]/30">
        <button
          type="button"
          onClick={() => setShowCreateForm(false)}
          className="px-4 py-2.5 rounded-xl border border-gray-300 font-bold text-gray-700 text-xs hover:bg-gray-50 transition"
        >
          {t("cat_builder.btn_cancel")}
        </button>
        <button
          type="submit"
          className="px-6 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs shadow-md hover:brightness-105 transition flex items-center gap-2"
        >
          <Check className="w-4 h-4" />
          <span>{t("cat_builder.btn_save_category")}</span>
        </button>
      </div>
    </form>
  );
}
