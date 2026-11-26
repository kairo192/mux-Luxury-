// Part of the category builder (pages/CategoryBuilderPage.tsx), which owns the state.
import React from "react";
import { ATTRIBUTE_TYPES } from "./catalogSetup";
import { Plus, X } from "lucide-react";
import { useT } from "../../i18n";
import { pickLang } from "../../i18n/translations";

/** Add one attribute to an existing category. */
export function QuickAttributeModal({ quickAttrCategory, setQuickAttrCategory, handleAddAttributeToExisting, quickAttrKey, setQuickAttrKey, quickAttrLabelFr, setQuickAttrLabelFr, quickAttrType, setQuickAttrType, quickAttrOptions, setQuickAttrOptions, quickAttrVariant, setQuickAttrVariant, quickAttrFilterable, setQuickAttrFilterable, quickAttrRequired, setQuickAttrRequired, savingQuickAttr }: {
  quickAttrCategory: any | null;
  setQuickAttrCategory: React.Dispatch<React.SetStateAction<any | null>>;
  handleAddAttributeToExisting: (e: React.FormEvent) => Promise<void>;
  quickAttrKey: string;
  setQuickAttrKey: React.Dispatch<React.SetStateAction<string>>;
  quickAttrLabelFr: string;
  setQuickAttrLabelFr: React.Dispatch<React.SetStateAction<string>>;
  quickAttrType: string;
  setQuickAttrType: React.Dispatch<React.SetStateAction<string>>;
  quickAttrOptions: string;
  setQuickAttrOptions: React.Dispatch<React.SetStateAction<string>>;
  quickAttrVariant: boolean;
  setQuickAttrVariant: React.Dispatch<React.SetStateAction<boolean>>;
  quickAttrFilterable: boolean;
  setQuickAttrFilterable: React.Dispatch<React.SetStateAction<boolean>>;
  quickAttrRequired: boolean;
  setQuickAttrRequired: React.Dispatch<React.SetStateAction<boolean>>;
  savingQuickAttr: boolean;
}) {
  const t = useT();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border-2 border-[#D4AF62] shadow-2xl max-w-lg w-full space-y-4 p-6 text-xs">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62]">
              <Plus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-serif font-bold text-base text-[#063D2E]">
                {t("cbf.qa_title", { name: pickLang(quickAttrCategory, "name") })}
              </h3>
              <p className="text-gray-500 font-medium">{t("cbf.qa_sub")}</p>
            </div>
          </div>
          <button aria-label={t("cbf.close")}
            type="button"
            onClick={() => setQuickAttrCategory(null)}
            className="text-gray-400 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleAddAttributeToExisting} className="space-y-3">
          <div>
            <label className="block font-bold mb-1 text-gray-700">{t("cbf.qa_key")}</label>
            <input
              value={quickAttrKey}
              onChange={(e) => setQuickAttrKey(e.target.value)}
              placeholder={t("cbf.qa_key_ph")}
              required
              className="w-full px-3 py-2 border rounded-xl font-mono text-gray-800"
            />
          </div>

          <div>
            <label className="block font-bold mb-1 text-gray-700">{t("cbf.qa_label")}</label>
            <input
              value={quickAttrLabelFr}
              onChange={(e) => setQuickAttrLabelFr(e.target.value)}
              placeholder={t("cbf.qa_label_ph")}
              required
              className="w-full px-3 py-2 border rounded-xl font-bold"
            />
          </div>

          <div>
            <label className="block font-bold mb-1 text-gray-700">{t("cbf.qa_type")}</label>
            <select
              value={quickAttrType}
              onChange={(e) => setQuickAttrType(e.target.value)}
              className="w-full px-3 py-2 border rounded-xl bg-white"
            >
              {ATTRIBUTE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-bold mb-1 text-gray-700">{t("cbf.qa_options")}</label>
            <input
              value={quickAttrOptions}
              onChange={(e) => setQuickAttrOptions(e.target.value)}
              placeholder="ex: 37, 38, 39, 40, 41"
              className="w-full px-3 py-2 border rounded-xl"
            />
          </div>

          <div className="flex flex-col gap-2 pt-1 p-3 rounded-xl bg-[#F8F6F0] border">
            <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
              <input
                type="checkbox"
                checked={quickAttrVariant}
                onChange={(e) => setQuickAttrVariant(e.target.checked)}
              />
              <span>{t("cbf.qa_axis")}</span>
            </label>
            <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
              <input
                type="checkbox"
                checked={quickAttrFilterable}
                onChange={(e) => setQuickAttrFilterable(e.target.checked)}
              />
              <span>{t("cbf.qa_filter")}</span>
            </label>
            <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
              <input
                type="checkbox"
                checked={quickAttrRequired}
                onChange={(e) => setQuickAttrRequired(e.target.checked)}
              />
              <span>{t("cbf.qa_required")}</span>
            </label>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t">
            <button
              type="button"
              onClick={() => setQuickAttrCategory(null)}
              className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
            >
              {t("cbf.cancel")}
            </button>
            <button
              type="submit"
              disabled={savingQuickAttr}
              className="px-6 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold shadow hover:bg-[#02291F] transition"
            >
              {savingQuickAttr ? t("cbf.qa_adding") : t("cbf.qa_add")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
