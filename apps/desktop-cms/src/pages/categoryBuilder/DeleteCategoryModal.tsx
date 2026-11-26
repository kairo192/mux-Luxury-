// Part of the category builder (pages/CategoryBuilderPage.tsx), which owns the state.
import React from "react";
import { AlertTriangle, Archive, Trash2 } from "lucide-react";
import { useT } from "../../i18n";

/** Archive, restore or delete a category. */
export function DeleteCategoryModal({ deletingCategory, handleArchiveCategory, isDeleting, handlePermanentDeleteCategory, setDeletingCategory }: {
  deletingCategory: any | null;
  handleArchiveCategory: (catId: number, catName: string) => Promise<void>;
  isDeleting: boolean;
  handlePermanentDeleteCategory: (catId: number, catName: string) => Promise<void>;
  setDeletingCategory: React.Dispatch<React.SetStateAction<any | null>>;
}) {
  const t = useT();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border-2 border-red-300 shadow-2xl max-w-lg w-full space-y-4 p-6 text-xs">
        <div className="flex items-center gap-3 text-red-700">
          <div className="p-2.5 rounded-xl bg-red-100">
            <AlertTriangle className="w-6 h-6 text-red-600" />
          </div>
          <div>
            <h3 className="text-base font-serif font-bold">
              {t("cbf.del_title")}
            </h3>
            <p className="text-gray-500 font-medium">« {deletingCategory.name_fr} » (#{deletingCategory.slug})</p>
          </div>
        </div>

        <p className="text-gray-600 leading-relaxed">
          {t("cbf.del_intro")}
        </p>

        <div className="space-y-3">
          {/* Option 1: Safe Archive */}
          <div className="p-3.5 rounded-xl border border-amber-300 bg-amber-50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-900 flex items-center gap-1.5">
                <Archive className="w-4 h-4 text-amber-700" />
                <span>{t("cbf.opt1")}</span>
              </span>
              <span className="px-2 py-0.5 rounded bg-amber-200 text-amber-900 font-bold text-[10px]">
                {t("cbf.no_risk")}
              </span>
            </div>
            <p className="text-gray-600 text-[11px]">
              {t("cbf.opt1_body")}
            </p>
            <button
              type="button"
              onClick={() => handleArchiveCategory(deletingCategory.id, deletingCategory.name_fr)}
              className="w-full py-2 rounded-xl bg-amber-700 text-white font-extrabold hover:bg-amber-800 transition flex items-center justify-center gap-1.5"
            >
              <Archive className="w-4 h-4 text-white" />
              <span>{t("cbf.archive_btn")}</span>
            </button>
          </div>

          {/* Option 2: Hard Delete */}
          <div className="p-3.5 rounded-xl border border-red-300 bg-red-50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-red-900 flex items-center gap-1.5">
                <Trash2 className="w-4 h-4 text-red-600" />
                <span>{t("cbf.opt2")}</span>
              </span>
              <span className="px-2 py-0.5 rounded bg-red-200 text-red-900 font-bold text-[10px]">
                {t("cbf.irreversible")}
              </span>
            </div>
            <p className="text-gray-600 text-[11px]">
              {t("cbf.opt2_body")}
            </p>
            <button
              type="button"
              disabled={isDeleting}
              onClick={() => handlePermanentDeleteCategory(deletingCategory.id, deletingCategory.name_fr)}
              className="w-full py-2 rounded-xl bg-red-700 text-white font-extrabold hover:bg-red-800 transition disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              <Trash2 className="w-4 h-4 text-white" />
              <span>{isDeleting ? t("cbf.deleting") : t("cbf.delete_btn")}</span>
            </button>
          </div>
        </div>

        <div className="pt-2 text-right">
          <button
            type="button"
            onClick={() => setDeletingCategory(null)}
            className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
          >
            {t("cbf.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
