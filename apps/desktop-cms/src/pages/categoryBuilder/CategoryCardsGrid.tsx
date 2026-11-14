// Part of the category builder (pages/CategoryBuilderPage.tsx), which owns the state.
import React from "react";
import { useT } from "../../i18n";
import { getCategoryIconComponent, typeLabel } from "./catalogSetup";
import { Edit3, Eye, EyeOff, Plus, Sparkles, Tags, Trash2 } from "lucide-react";

/** The category cards (or loading / empty state). */
export function CategoryCardsGrid({ loading, filteredCategories, liveCategories, activeFilter, handleInitializeLuxuryStarterCollections, setShowCreateForm, setSearchQuery, setActiveFilter, setQuickAttrCategory, handleDeleteAttribute, handleRestoreCategory, setDeletingCategory, handleToggleCategoryHomepage, handleOpenEdit }: {
  loading: boolean;
  filteredCategories: any;
  liveCategories: any;
  activeFilter: "all" | "active" | "homepage" | "with_attrs" | "archived";
  handleInitializeLuxuryStarterCollections: () => Promise<void>;
  setShowCreateForm: React.Dispatch<React.SetStateAction<boolean>>;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  setActiveFilter: React.Dispatch<React.SetStateAction<"all" | "active" | "homepage" | "with_attrs" | "archived">>;
  setQuickAttrCategory: React.Dispatch<React.SetStateAction<any | null>>;
  handleDeleteAttribute: (attrId: number) => Promise<void>;
  handleRestoreCategory: (catId: number, catName: string) => Promise<void>;
  setDeletingCategory: React.Dispatch<React.SetStateAction<any | null>>;
  handleToggleCategoryHomepage: (cat: any) => Promise<void>;
  handleOpenEdit: (cat: any) => void;
}) {
  const t = useT();
  return (
  loading ? (
    <div className="p-12 text-center text-xs text-gray-500 bg-white rounded-2xl border border-[#D4AF62]/30">
      {t("cat_builder.loading")}
    </div>
  ) : filteredCategories.length === 0 ? (
    liveCategories.length === 0 && activeFilter !== "archived" ? (
      <div className="p-12 text-center bg-[#F8F6F0]/60 rounded-2xl border-2 border-dashed border-[#D4AF62]/50 space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center mx-auto text-[#D4AF62] shadow-md">
          <Sparkles className="w-8 h-8 text-[#D4AF62]" />
        </div>
        <div className="max-w-md mx-auto space-y-1">
          <h4 className="text-lg font-serif font-bold text-[#063D2E]">{t("cat_builder.empty_title")}</h4>
          <p className="text-xs text-gray-600 leading-relaxed">
            Aucune catégorie n'est actuellement enregistrée dans la base de données. Vous pouvez initialiser en un clic les 4 collections de prestige Mus Luxury (Sacs, Souliers, Cosmétiques, Soieries) ou créer une catégorie sur mesure.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleInitializeLuxuryStarterCollections}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold text-xs shadow-xs hover:brightness-105 transition"
          >
            <Sparkles className="w-4 h-4 text-[#02291F]" />
            <span>{t("cat_builder.btn_init_starter")}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs shadow-xs hover:bg-[#084e3b] transition"
          >
            <Plus className="w-4 h-4 text-[#D4AF62]" />
            <span>{t("cat_builder.btn_create_custom")}</span>
          </button>
        </div>
      </div>
    ) : (
      <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-[#D4AF62]/40 space-y-3">
        <Tags className="w-10 h-10 text-gray-300 mx-auto" />
        <p className="text-sm font-bold text-gray-600">{t("cat_builder.no_results")}</p>
        <button
          type="button"
          onClick={() => {
            setSearchQuery("");
            setActiveFilter("all");
          }}
          className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] text-xs font-bold"
        >
          {t("cat_builder.btn_reset_filters")}
        </button>
      </div>
    )
  ) : (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {filteredCategories.map((c) => {
        const IconComp = getCategoryIconComponent(c.slug || c.name_fr);
        const attrs = c.attributes || [];
        return (
          <div
            key={c.id}
            className="bg-white rounded-2xl border border-[#D4AF62]/40 shadow-sm hover:shadow-md transition-all flex flex-col justify-between overflow-hidden"
          >
            {/* Card Top */}
            <div className="p-5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-2xl bg-[#063D2E] text-[#D4AF62] shadow-sm">
                    <IconComp className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-base text-[#063D2E] leading-tight">
                      {c.name_fr}
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {c.name_ar && (
                        <span className="text-xs text-gray-500 font-medium font-sans" dir="rtl">
                          {c.name_ar}
                        </span>
                      )}
                      <span className="text-[11px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                        #{c.slug}
                      </span>
                    </div>
                  </div>
                </div>

                <span className="text-[11px] font-mono text-gray-400 font-semibold">
                  Ordre #{c.display_order ?? 1}
                </span>
              </div>

              {c.description_fr && (
                <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed">
                  {c.description_fr}
                </p>
              )}

              {/* Status Pills */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px]">
                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold ${
                    c.show_on_homepage
                      ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                      : "bg-gray-100 text-gray-500 border border-gray-200"
                  }`}
                >
                  {c.show_on_homepage ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                  <span>{c.show_on_homepage ? t("cat_builder.badge_home_visible") : t("cat_builder.badge_home_hidden")}</span>
                </span>

                <span className="px-2.5 py-0.5 rounded-full bg-[#F8F6F0] text-[#063D2E] font-bold border border-[#D4AF62]/30">
                  {t("cat_builder.attrs_count", { count: attrs.length })}
                </span>
              </div>

              {/* Dynamic Attributes List for this category */}
              <div className="pt-2 border-t border-gray-100 space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-bold text-gray-500">
                  <span>{t("cat_builder.attrs_and_filters")}</span>
                  <button
                    type="button"
                    onClick={() => setQuickAttrCategory(c)}
                    className="text-[#063D2E] hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>{t("cat_builder.btn_add_attr")}</span>
                  </button>
                </div>

                {attrs.length === 0 ? (
                  <p className="text-[11px] text-gray-400 italic">{t("cat_builder.no_attrs")}</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                    {attrs.map((a: any) => (
                      <span
                        key={a.id}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-[#F8F6F0] border border-gray-200 text-[11px] text-gray-700 font-medium"
                      >
                        <strong>{a.label_fr}</strong>
                        <span className="text-[10px] text-gray-400 font-mono">
                          ({typeLabel(a.input_type)}
                          {a.is_variant_axis ? " • crée les variantes" : ""})
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDeleteAttribute(a.id)}
                          className="text-red-500 hover:text-red-800 font-bold ml-0.5"
                          title="Supprimer cet attribut"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Card Action Buttons Toolbar */}
            {c.deleted_at ? (
            <div className="p-3 bg-amber-50/70 border-t border-amber-100 flex items-center justify-between gap-1 text-xs font-bold">
              <span className="text-amber-800 text-[11px]">{t("cat_builder.archived_badge")}</span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => handleRestoreCategory(c.id, c.name_fr)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-[#D4AF62] text-[#063D2E] hover:bg-[#D4AF62]/20 transition shadow-sm"
                >
                  <span>{t("cat_builder.btn_restore")}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeletingCategory(c)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 transition"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-600" />
                  <span>{t("cat_builder.btn_delete_forever")}</span>
                </button>
              </div>
            </div>
            ) : (
            <div className="p-3 bg-[#F8F6F0]/80 border-t border-gray-100 flex items-center justify-between gap-1 text-xs font-bold">
              <button
                type="button"
                onClick={() => handleToggleCategoryHomepage(c)}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-white transition"
                title={c.show_on_homepage ? "Masquer de la page d'accueil" : "Afficher sur la page d'accueil"}
              >
                {c.show_on_homepage ? <EyeOff className="w-3.5 h-3.5 text-gray-500" /> : <Eye className="w-3.5 h-3.5 text-emerald-600" />}
                <span>{c.show_on_homepage ? t("cat_builder.btn_toggle_home_hide") : t("cat_builder.btn_toggle_home_show")}</span>
              </button>

              <div className="flex items-center gap-1.5">
                {/* EDIT CATEGORY BUTTON */}
                <button
                  type="button"
                  onClick={() => handleOpenEdit(c)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-[#D4AF62] text-[#063D2E] hover:bg-[#D4AF62]/20 transition shadow-sm"
                  title="Modifier les noms, slug, description et icône"
                >
                  <Edit3 className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>{t("cat_builder.btn_modify")}</span>
                </button>

                {/* DELETE / ARCHIVE BUTTON */}
                <button
                  type="button"
                  onClick={() => setDeletingCategory(c)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 transition"
                  title="Archiver ou Supprimer définitivement cette catégorie"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-600" />
                  <span>{t("cat_builder.btn_delete")}</span>
                </button>
              </div>
            </div>
            )}
          </div>
        );
      })}
    </div>
  )
  );
}
