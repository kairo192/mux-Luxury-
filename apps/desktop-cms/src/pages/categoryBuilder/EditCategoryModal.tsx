// Part of the category builder (pages/CategoryBuilderPage.tsx), which owns the state.
import React from "react";
import { ImageUploadField } from "../../components/ImageUploadField";
import { LUXURY_ICONS } from "./catalogSetup";
import { Edit3, X } from "lucide-react";

/** Edit a category's names, pictures, icon, order and visibility. */
export function EditCategoryModal({ editingCategory, setEditingCategory, handleSubmitEdit, editNameFr, setEditNameFr, editNameAr, setEditNameAr, editNameEn, setEditNameEn, editSlug, setEditSlug, editOrder, setEditOrder, editDescFr, setEditDescFr, editImageUrl, setEditImageUrl, editBannerUrl, setEditBannerUrl, editIconKey, setEditIconKey, editShowHomepage, setEditShowHomepage, editIsActive, setEditIsActive, savingEdit }: {
  editingCategory: any | null;
  setEditingCategory: React.Dispatch<React.SetStateAction<any | null>>;
  handleSubmitEdit: (e: React.FormEvent) => Promise<void>;
  editNameFr: string;
  setEditNameFr: React.Dispatch<React.SetStateAction<string>>;
  editNameAr: string;
  setEditNameAr: React.Dispatch<React.SetStateAction<string>>;
  editNameEn: string;
  setEditNameEn: React.Dispatch<React.SetStateAction<string>>;
  editSlug: string;
  setEditSlug: React.Dispatch<React.SetStateAction<string>>;
  editOrder: number;
  setEditOrder: React.Dispatch<React.SetStateAction<number>>;
  editDescFr: string;
  setEditDescFr: React.Dispatch<React.SetStateAction<string>>;
  editImageUrl: string;
  setEditImageUrl: React.Dispatch<React.SetStateAction<string>>;
  editBannerUrl: string;
  setEditBannerUrl: React.Dispatch<React.SetStateAction<string>>;
  editIconKey: string;
  setEditIconKey: React.Dispatch<React.SetStateAction<string>>;
  editShowHomepage: boolean;
  setEditShowHomepage: React.Dispatch<React.SetStateAction<boolean>>;
  editIsActive: boolean;
  setEditIsActive: React.Dispatch<React.SetStateAction<boolean>>;
  savingEdit: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border-2 border-[#D4AF62] shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-4 p-6">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62]">
              <Edit3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-serif font-bold text-[#063D2E]">
                Modifier la Catégorie : {editingCategory.name_fr}
              </h2>
              <p className="text-xs text-gray-500">Mettez à jour les traductions, le slug et la visibilité.</p>
            </div>
          </div>
          <button aria-label="Fermer"
            type="button"
            onClick={() => setEditingCategory(null)}
            className="text-gray-400 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmitEdit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-bold mb-1 text-gray-700">Nom Français (FR) *</label>
              <input
                value={editNameFr}
                onChange={(e) => setEditNameFr(e.target.value)}
                required
                className="w-full px-3 py-2 border rounded-xl font-bold"
              />
            </div>
            <div>
              <label className="block font-bold mb-1 text-gray-700">Nom Arabe (AR)</label>
              <input
                value={editNameAr}
                onChange={(e) => setEditNameAr(e.target.value)}
                dir="rtl"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold mb-1 text-gray-700">Nom Anglais (EN)</label>
              <input
                value={editNameEn}
                onChange={(e) => setEditNameEn(e.target.value)}
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold mb-1 text-gray-700">Slug URL *</label>
              <input
                value={editSlug}
                onChange={(e) => setEditSlug(e.target.value)}
                required
                className="w-full px-3 py-2 border rounded-xl font-mono text-gray-700"
              />
            </div>
            <div>
              <label className="block font-bold mb-1 text-gray-700">Ordre d'affichage</label>
              <input
                type="number"
                value={editOrder}
                onChange={(e) => setEditOrder(Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-xl font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block font-bold mb-1 text-gray-700">Description (FR)</label>
            <textarea
              value={editDescFr}
              onChange={(e) => setEditDescFr(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border rounded-xl"
              placeholder="Description affichée sur la boutique..."
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ImageUploadField label="Photo de la catégorie" value={editImageUrl} onChange={setEditImageUrl} />
            <ImageUploadField label="Bannière" value={editBannerUrl} onChange={setEditBannerUrl} wide />
          </div>

          {/* Icon Choice */}
          <div className="p-3 bg-[#F8F6F0] rounded-xl border border-gray-200 space-y-2">
            <label className="block font-bold text-[#063D2E]">Icône de représentation :</label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
              {LUXURY_ICONS.map((item) => {
                const Icon = item.icon;
                const isSelected = editIconKey === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setEditIconKey(item.key)}
                    className={`flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition ${
                      isSelected
                        ? "bg-[#063D2E] text-[#D4AF62] border-[#D4AF62] shadow-sm font-bold"
                        : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-[10px] text-center truncate w-full">{item.label.split(" ")[0]}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Toggles */}
          <div className="flex flex-wrap gap-5 p-3 rounded-xl bg-gray-50 border border-gray-200">
            <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
              <input
                type="checkbox"
                checked={editShowHomepage}
                onChange={(e) => setEditShowHomepage(e.target.checked)}
                className="w-4 h-4 rounded text-[#063D2E]"
              />
              <span>Afficher sur la Page d'Accueil</span>
            </label>

            <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
              <input
                type="checkbox"
                checked={editIsActive}
                onChange={(e) => setEditIsActive(e.target.checked)}
                className="w-4 h-4 rounded text-[#063D2E]"
              />
              <span>Catégorie Active</span>
            </label>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t">
            <button
              type="button"
              onClick={() => setEditingCategory(null)}
              className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={savingEdit}
              className="px-6 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold shadow hover:bg-[#02291F] transition"
            >
              {savingEdit ? "Enregistrement..." : "Enregistrer les modifications"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
