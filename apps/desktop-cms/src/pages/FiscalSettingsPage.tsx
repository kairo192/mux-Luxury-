import React, { useEffect, useState, useCallback } from "react";
import { Landmark, Save, RefreshCw, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

const TEXT_FIELDS: Array<{ key: string; label: string; hint?: string; mono?: boolean }> = [
  { key: "fiscal_legal_name", label: "Raison sociale" },
  { key: "fiscal_commercial_name", label: "Nom commercial (affiché sur les reçus)" },
  { key: "fiscal_address", label: "Adresse" },
  { key: "fiscal_phone", label: "Téléphone", mono: true },
  { key: "fiscal_nif", label: "NIF", hint: "Numéro d'Identification Fiscale", mono: true },
  { key: "fiscal_nis", label: "NIS", hint: "Numéro d'Identification Statistique", mono: true },
  { key: "fiscal_rc", label: "RC", hint: "Registre de Commerce", mono: true },
  { key: "fiscal_article", label: "Article d'imposition", mono: true },
  { key: "receipt_footer_line", label: "Message de bas de reçu" },
];

export const FiscalSettingsPage: React.FC = () => {
  const [values, setValues] = useState<Record<string, string>>({});
  const [taxRate, setTaxRate] = useState("0");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.getFiscalSettings();
      const v: Record<string, string> = {};
      TEXT_FIELDS.forEach((f) => (v[f.key] = d[f.key] ?? ""));
      setValues(v);
      setTaxRate(String(d.pos_tax_rate_percent ?? 0));
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    const rate = parseInt(taxRate || "0", 10);
    if (isNaN(rate) || rate < 0 || rate > 100) return setError("Le taux de taxe doit être compris entre 0 et 100");
    setBusy(true);
    setError(null);
    try {
      await DesktopCmsApi.updateFiscalSettings({ pos_tax_rate_percent: rate, settings: values });
      setSuccess("Paramètres enregistrés");
      setTimeout(() => setSuccess(null), 3500);
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Enregistrement refusé (droit « settings:write » requis)");
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
          <Landmark className="w-5 h-5" /> Paramètres fiscaux & identité
        </h3>
        <p className="text-gray-500 mt-1">Ces valeurs apparaissent sur les reçus et les étiquettes. Rien n'est codé en dur.</p>
      </div>

      <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600 flex items-start gap-2">
        <Info className="w-5 h-5 shrink-0 mt-0.5 text-[#063D2E]" />
        <span>
          Les taux et mentions légales doivent être validés par un <strong>comptable</strong> selon la réglementation algérienne en vigueur. Cette application ne garantit pas la conformité fiscale officielle.
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
        </div>
      ) : (
        <div className="bg-white p-5 rounded-3xl border border-gray-200 space-y-4">
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Taux de taxe appliqué au POS (%)</span>
            <input
              type="number"
              min={0}
              max={100}
              value={taxRate}
              onChange={(e) => setTaxRate(e.target.value)}
              className="w-32 h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono"
            />
            <span className="block text-[11px] text-gray-400 mt-1">0 = aucune taxe ajoutée. S'applique aux nouvelles ventes magasin uniquement.</span>
          </label>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TEXT_FIELDS.map((f) => (
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
            <Save className="w-5 h-5" /> Enregistrer
          </button>
        </div>
      )}
    </div>
  );
};
