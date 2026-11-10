import React, { useEffect, useState, useCallback } from "react";
import { Landmark, Save, RefreshCw, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";

export const FiscalSettingsPage: React.FC = () => {
  const t = useT();
  const [values, setValues] = useState<Record<string, string>>({});
  const [taxRate, setTaxRate] = useState("0");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const textFields: Array<{ key: string; label: string; hint?: string; mono?: boolean }> = [
    { key: "fiscal_legal_name", label: t("fiscal.company_name") },
    { key: "fiscal_commercial_name", label: t("fiscal.commercial_name") },
    { key: "fiscal_address", label: t("fiscal.address") },
    { key: "fiscal_phone", label: t("fiscal.phone"), mono: true },
    { key: "fiscal_nif", label: "NIF", hint: t("fiscal.nif"), mono: true },
    { key: "fiscal_nis", label: "NIS", hint: t("fiscal.nis"), mono: true },
    { key: "fiscal_rc", label: "RC", hint: t("fiscal.rc"), mono: true },
    { key: "fiscal_article", label: t("fiscal.article"), mono: true },
    { key: "receipt_footer_line", label: t("fiscal.receipt_footer_line") },
  ];

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.getFiscalSettings();
      const v: Record<string, string> = {};
      textFields.forEach((f) => (v[f.key] = d[f.key] ?? ""));
      setValues(v);
      setTaxRate(String(d.pos_tax_rate_percent ?? 0));
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || t("status.error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    const rate = parseInt(taxRate || "0", 10);
    if (isNaN(rate) || rate < 0 || rate > 100) return setError(t("fiscal.tax_rate_invalid"));
    setBusy(true);
    setError(null);
    try {
      await DesktopCmsApi.updateFiscalSettings({ pos_tax_rate_percent: rate, settings: values });
      setSuccess(t("fiscal.flash_saved"));
      setTimeout(() => setSuccess(null), 3500);
      load();
    } catch (e: any) {
      setError(e?.userMessage || t("fiscal.save_error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 text-sm max-w-3xl">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <Landmark className="w-5 h-5" /> {t("fiscal.title")}
        </h3>
        <p className="text-gray-500 mt-1">{t("fiscal.subtitle")}</p>
      </div>

      <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600 flex items-start gap-2">
        <Info className="w-5 h-5 shrink-0 mt-0.5 text-[#063D2E]" />
        <span>{t("fiscal.accountant_notice")}</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("status.loading")}
        </div>
      ) : (
        <div className="bg-white p-5 rounded-3xl border border-gray-200 space-y-4">
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("fiscal.tax_rate_label")}</span>
            <input
              type="number"
              min={0}
              max={100}
              value={taxRate}
              onChange={(e) => setTaxRate(e.target.value)}
              className="w-32 h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono"
            />
            <span className="block text-[11px] text-gray-400 mt-1">{t("fiscal.tax_rate_hint")}</span>
          </label>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {textFields.map((f) => (
              <label key={f.key} className={`block ${f.key === "fiscal_address" || f.key === "receipt_footer_line" ? "md:col-span-2" : ""}`}>
                <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{f.label}</span>
                <input
                  value={values[f.key] ?? ""}
                  onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                  className={`w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none ${f.mono ? "font-mono" : ""}`}
                />
                {f.hint && <span className="block text-[11px] text-gray-400 mt-0.5">{f.hint}</span>}
              </label>
            ))}
          </div>

          <button type="button" disabled={busy} onClick={save} className="w-full md:w-auto h-14 px-8 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold flex items-center justify-center gap-2 disabled:opacity-50 active:scale-[0.99]">
            <Save className="w-5 h-5" /> {t("fiscal.btn_save")}
          </button>
        </div>
      )}
    </div>
  );
};
