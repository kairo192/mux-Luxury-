import React, { useState, useEffect } from "react";
import {
  Building2,
  Zap,
  Truck,
  FileSpreadsheet,
  Boxes,
  Plus,
  RefreshCw,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  X,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";
import { codeLabel } from "../utils/codeLabels";

interface TreasurySummary {
  cash_balance_dzd: number;
  bank_balance_dzd: number;
  total_liquidity_dzd: number;
  pending_cod_collections_dzd: number;
  supplier_debts_dzd: number;
  inventory_valuation_dzd: number;
}

interface CashMovement {
  id: number;
  movement_type: "inflow" | "outflow";
  account_type?: string;
  category?: string;
  source_type?: string;
  source_reference?: string;
  description?: string;
  amount_dzd: number;
  balance_after_dzd?: number;
  reference_type?: string;
  reference_id?: string;
  notes?: string;
  recorded_by?: number | string;
  created_by?: string;
  created_at: string;
}

export const TreasuryPage: React.FC = () => {
  const t = useT();
  const [summary, setSummary] = useState<TreasurySummary | null>(null);
  const [movements, setMovements] = useState<CashMovement[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);

  // New Movement Form State
  const [movType, setMovType] = useState<"inflow" | "outflow">("inflow");
  const [movCategory, setMovCategory] = useState<string>("cash_in");
  const [movAccount, setMovAccount] = useState<"cash_box" | "bank_account">("cash_box");
  const [movAmount, setMovAmount] = useState<string>("");
  const [movNotes, setMovNotes] = useState<string>("");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumData, movData] = await Promise.all([
        DesktopCmsApi.getTreasurySummary(),
        DesktopCmsApi.listCashMovements(60),
      ]);
      setSummary(sumData);
      setMovements(Array.isArray(movData) ? movData : (movData as any)?.items || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("status.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRecordMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedAmount = parseInt(movAmount, 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError("Le montant doit être un entier positif en DZD");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await DesktopCmsApi.recordCashMovement({
        movement_type: movType,
        account_type: movAccount,
        category: movCategory,
        amount_dzd: parsedAmount,
        notes: movNotes.trim() || undefined,
      });

      setSuccess(t("common.saved"));
      setShowModal(false);
      setMovAmount("");
      setMovNotes("");
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("status.error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#063D2E]/10">
        <div>
          <h2 className="text-2xl font-serif font-bold text-[#063D2E] tracking-tight">
            {t("treasury.title")}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            {t("treasury.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData()}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl border border-[#063D2E]/20 text-[#063D2E] hover:bg-[#063D2E]/5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>{t("common.refresh")}</span>
          </button>
          <button
            onClick={() => {
              setError(null);
              setSuccess(null);
              setShowModal(true);
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] shadow-xs transition-all"
          >
            <Plus className="w-4 h-4 text-[#D4AF62]" />
            <span>{t("treasury.btn_add_movement")}</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex justify-between items-center">
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </span>
          <button aria-label="Masquer le message" onClick={() => setError(null)} className="text-red-500 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl flex justify-between items-center">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            <span>{success}</span>
          </span>
          <button aria-label="Masquer le message" onClick={() => setSuccess(null)} className="text-emerald-600 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Summary KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Cash Balance */}
        <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
            <span className="flex items-center gap-1.5 font-bold text-gray-700">
              <DollarSign className="w-4 h-4 text-emerald-700" />
              {t("treasury.stat_cash")}
            </span>
            <span className="text-[10px] bg-emerald-50 text-emerald-800 font-bold px-2 py-0.5 rounded-full">Physique</span>
          </div>
          <div className="text-3xl font-bold font-mono text-[#063D2E] mt-2">
            {(summary?.cash_balance_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-[#D4AF62]">DZD</span>
          </div>
          <div className="text-[11px] text-gray-500 mt-2">
            Disponible immédiatement au tiroir-caisse
          </div>
        </div>

        {/* Bank Balance */}
        <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
            <span className="flex items-center gap-1.5 font-bold text-gray-700">
              <Building2 className="w-4 h-4 text-blue-600" />
              {t("treasury.stat_bank")}
            </span>
            <span className="text-[10px] bg-blue-50 text-blue-700 font-bold px-2 py-0.5 rounded-full">Banque</span>
          </div>
          <div className="text-3xl font-bold font-mono text-gray-900 mt-2">
            {(summary?.bank_balance_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-[#D4AF62]">DZD</span>
          </div>
          <div className="text-[11px] text-gray-500 mt-2">
            Fonds sur comptes bancaires professionnels
          </div>
        </div>

        {/* Total Liquidity */}
        <div className="p-5 bg-gradient-to-br from-[#063D2E] to-[#0A5C45] text-white rounded-2xl shadow-md relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-[#D4AF62]">
            <span className="flex items-center gap-1.5 font-bold">
              <Zap className="w-4 h-4 text-[#D4AF62]" />
              {t("treasury.stat_liquidity")}
            </span>
            <span className="text-[10px] bg-white/10 text-[#E8D4A5] font-bold px-2 py-0.5 rounded-full border border-white/15">Consolidé</span>
          </div>
          <div className="text-3xl font-bold font-mono text-white mt-2">
            {(summary?.total_liquidity_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-[#D4AF62]">DZD</span>
          </div>
          <div className="text-[11px] text-emerald-200 mt-2">
            Caisse physique + Comptes bancaires consolidés
          </div>
        </div>

        {/* Pending COD Collections */}
        <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
            <span className="flex items-center gap-1.5 font-bold text-gray-700">
              <Truck className="w-4 h-4 text-amber-600" />
              {t("treasury.stat_cod_pending")}
            </span>
            <span className="text-[10px] bg-amber-50 text-amber-700 font-bold px-2 py-0.5 rounded-full">En cours</span>
          </div>
          <div className="text-3xl font-bold font-mono text-amber-700 mt-2">
            {(summary?.pending_cod_collections_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-[#D4AF62]">DZD</span>
          </div>
          <div className="text-[11px] text-gray-500 mt-2">
            Commandes confirmées, en préparation ou expédiées : à encaisser à la livraison
          </div>
        </div>

        {/* Supplier Debts */}
        <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
            <span className="flex items-center gap-1.5 font-bold text-gray-700">
              <FileSpreadsheet className="w-4 h-4 text-red-600" />
              Dettes Fournisseurs
            </span>
            <span className="text-[10px] bg-red-50 text-red-700 font-bold px-2 py-0.5 rounded-full">Passif</span>
          </div>
          <div className="text-3xl font-bold font-mono text-red-600 mt-2">
            {(summary?.supplier_debts_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-red-400">DZD</span>
          </div>
        </div>

        {/* Global Inventory Valuation */}
        <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
            <span className="flex items-center gap-1.5 font-bold text-gray-700">
              <Boxes className="w-4 h-4 text-purple-600" />
              {t("accounting.stat_inventory_val")}
            </span>
            <span className="text-[10px] bg-purple-50 text-purple-700 font-bold px-2 py-0.5 rounded-full">PMP</span>
          </div>
          <div className="text-3xl font-bold font-mono text-purple-900 mt-2">
            {(summary?.inventory_valuation_dzd ?? 0).toLocaleString()}{" "}
            <span className="text-sm font-sans font-normal text-[#D4AF62]">DZD</span>
          </div>
        </div>
      </div>

      {/* Movements Table */}
      <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
        <div className="px-6 py-4 bg-[#063D2E]/5 border-b border-[#063D2E]/10 flex items-center justify-between">
          <h3 className="text-sm font-serif font-bold text-[#063D2E] uppercase tracking-wider">
            {t("treasury.subtitle")}
          </h3>
          <span className="text-xs text-gray-500 font-mono">
            {movements.length} mouvements
          </span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-xs text-gray-400">{t("status.loading")}</div>
        ) : movements.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-400">
            {t("status.empty")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">{t("treasury.th_date")}</th>
                  <th className="py-3 px-4">{t("treasury.th_type")} / {t("treasury.th_category")}</th>
                  <th className="py-3 px-4">{t("expense_report.th_desc")}</th>
                  <th className="py-3 px-4 text-right">{t("treasury.th_amount")}</th>
                  <th className="py-3 px-4 text-right">Solde du compte après</th>
                  <th className="py-3 px-4 text-right">Opérateur</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {movements.map((m) => {
                  const isInflow = m.movement_type === "inflow" || (m.movement_type as string) === "deposit";
                  return (
                    <tr key={m.id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="py-3 px-4 font-mono text-gray-400">#{m.id}</td>
                      <td className="py-3 px-4 font-mono text-gray-600 whitespace-nowrap">
                        {m.created_at ? m.created_at.replace("T", " ").slice(0, 19) : "—"}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                            isInflow
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {isInflow ? `↗ ${t("treasury.inflow")}` : `↘ ${t("treasury.outflow")}`} • {codeLabel(m.category || m.source_type || "")} · {codeLabel(m.account_type || "cash_box")}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-gray-700">
                        <div>{m.notes || m.description || "—"}</div>
                        {(m.reference_id || m.source_reference) && (
                          <div className="text-[11px] font-mono text-gray-400">
                            Réf. {m.reference_id || m.source_reference}
                          </div>
                        )}
                      </td>
                      <td
                        className={`py-3 px-4 text-right font-mono font-bold whitespace-nowrap ${
                          isInflow ? "text-emerald-700" : "text-red-600"
                        }`}
                      >
                        {isInflow ? "+" : "-"}{Number(m.amount_dzd || 0).toLocaleString()} DZD
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-gray-700 whitespace-nowrap">
                        {m.balance_after_dzd !== undefined && m.balance_after_dzd !== null
                          ? `${codeLabel(m.account_type || "cash_box")} : ${Number(m.balance_after_dzd).toLocaleString()} DZD`
                          : "—"}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-gray-500">
                        {m.created_by || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Record Cash Movement */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md border border-[#063D2E]/20 overflow-hidden">
            <div className="bg-[#063D2E] px-6 py-4 flex items-center justify-between">
              <h3 className="text-sm font-serif font-bold text-[#D4AF62] uppercase tracking-wider">
                {t("treasury.btn_add_movement")}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-[#D4AF62]/70 hover:text-[#D4AF62] text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRecordMovement} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Type *
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setMovType("inflow");
                      setMovCategory("cash_in");
                    }}
                    className={`py-2 text-xs font-bold rounded border text-center transition-all ${
                      movType === "inflow"
                        ? "bg-emerald-600 text-white border-emerald-600"
                        : "bg-gray-50 text-gray-700 border-gray-200"
                    }`}
                  >
                    ↗ {t("treasury.inflow")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMovType("outflow");
                      setMovCategory("cash_out");
                    }}
                    className={`py-2 text-xs font-bold rounded border text-center transition-all ${
                      movType === "outflow"
                        ? "bg-red-600 text-white border-red-600"
                        : "bg-gray-50 text-gray-700 border-gray-200"
                    }`}
                  >
                    ↘ {t("treasury.outflow")}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  {t("treasury.th_category")} *
                </label>
                <select
                  value={movCategory}
                  onChange={(e) => setMovCategory(e.target.value)}
                  className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                >
                  {movType === "inflow" ? (
                    <>
                      <option value="cash_in">Fond de caisse / alimentation (caisse)</option>
                      <option value="bank_withdrawal">Retrait à la banque vers la caisse (transfert)</option>
                      <option value="capital_contribution">Apport du propriétaire</option>
                      <option value="other_inflow">Autre entrée</option>
                    </>
                  ) : (
                    <>
                      <option value="cash_out">Retrait du propriétaire</option>
                      <option value="bank_deposit">Dépôt d'espèces à la banque (transfert)</option>
                      <option value="courier_remittance">Versement du livreur sur le compte (transfert)</option>
                      <option value="minor_expense">Petite dépense boutique (caisse)</option>
                      <option value="cash_adjustment">Régularisation d'écart de caisse</option>
                      <option value="other_outflow">Autre sortie</option>
                    </>
                  )}
                </select>
                <p className="text-[11px] text-gray-500 mt-1">
                  Les ventes en magasin, les commandes livrées et les dépenses sont enregistrées automatiquement :
                  utilisez ce formulaire seulement pour les autres mouvements.
                </p>
              </div>

              {["capital_contribution", "other_inflow", "cash_out", "other_outflow"].includes(movCategory) && (
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Compte</label>
                  <select
                    value={movAccount}
                    onChange={(e) => setMovAccount(e.target.value as "cash_box" | "bank_account")}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                  >
                    <option value="cash_box">Caisse (espèces)</option>
                    <option value="bank_account">Banque / CCP</option>
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  {t("treasury.th_amount")} *
                </label>
                <input
                  type="number"
                  required
                  min="1"
                  placeholder="50000"
                  value={movAmount}
                  onChange={(e) => setMovAmount(e.target.value)}
                  className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none font-mono font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  {t("treasury.th_notes")} *
                </label>
                <textarea
                  rows={2}
                  required
                  value={movNotes}
                  onChange={(e) => setMovNotes(e.target.value)}
                  className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 text-xs font-semibold text-[#D4AF62] bg-[#063D2E] hover:bg-[#0A5C45] rounded shadow transition-all disabled:opacity-50"
                >
                  {saving ? "..." : t("common.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
