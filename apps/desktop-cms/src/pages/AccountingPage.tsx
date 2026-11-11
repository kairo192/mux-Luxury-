import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  DollarSign,
  Receipt,
  BarChart3,
  Download,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Search,
  BookOpen,
  Tag,
  X,
} from "lucide-react";
import { DesktopCmsApi, getAccessToken } from "../api/adminClient";
import { useT } from "../i18n";
import { localDateIso } from "../utils/serverDate";

interface PnlStatement {
  gross_revenue_dzd: number;
  delivery_revenue_dzd: number;
  total_revenue_dzd: number;
  cogs_dzd: number;
  gross_profit_dzd: number;
  gross_margin_percent: number;
  operating_expenses_dzd: number;
  net_operating_profit_dzd: number;
  net_margin_percent: number;
  orders_count: number;
  units_sold: number;
  inventory_valuation_dzd: number;
}

interface ProductProfitability {
  id: number;
  name: string;
  sku: string;
  category_name?: string;
  purchase_cost_dzd: number;
  selling_price_dzd: number;
  unit_profit_dzd: number;
  unit_margin_percent: number;
  units_sold: number;
  total_revenue_dzd: number;
  total_profit_dzd: number;
}

interface LedgerEntry {
  id: number;
  entry_number: string;
  entry_date: string;
  account_code: string;
  account_name: string;
  debit_dzd: number;
  credit_dzd: number;
  description: string;
  reference_type?: string;
  reference_id?: string;
}

interface LedgerResponse {
  total_debits_dzd: number;
  total_credits_dzd: number;
  is_balanced: boolean;
  entries_count: number;
  entries: LedgerEntry[];
}

export const AccountingPage: React.FC = () => {
  const t = useT();
  const [activeTab, setActiveTab] = useState<"pnl" | "products" | "ledger">("pnl");
  const [pnl, setPnl] = useState<PnlStatement | null>(null);
  const [products, setProducts] = useState<ProductProfitability[]>([]);
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchProduct, setSearchProduct] = useState<string>("");

  const loadAllAccountingData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pnlData, prodData, ledgerData] = await Promise.all([
        DesktopCmsApi.getPnlStatement(),
        DesktopCmsApi.getProductsProfitability(),
        DesktopCmsApi.getAccountingLedger(100),
      ]);
      setPnl(pnlData);
      setProducts(Array.isArray(prodData) ? prodData : (prodData as any)?.items || []);
      setLedger(ledgerData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("status.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllAccountingData();
  }, []);

  const handleExportOrdersCsv = async () => {
    try {
      const token = getAccessToken();
      const res = await fetch("http://127.0.0.1:8000/api/v1/admin/orders/export.csv", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `orders_${localDateIso()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError(t("status.error"));
    }
  };

  const filteredProducts = products.filter((p) => {
    const q = (searchProduct || "").toLowerCase();
    const pName = p.name || (p as any).name_fr || "";
    const pSku = p.sku || "";
    return !q || pName.toLowerCase().includes(q) || pSku.toLowerCase().includes(q);
  });

  // Safe numerical resolvers
  const grossRev = pnl?.gross_revenue_dzd ?? (pnl as any)?.revenue?.subtotal_merchandise_dzd ?? 0;
  const deliveryRev = pnl?.delivery_revenue_dzd ?? (pnl as any)?.revenue?.delivery_fees_dzd ?? 0;
  const totalRev = pnl?.total_revenue_dzd ?? (pnl as any)?.revenue?.total_sales_dzd ?? 0;
  const cogsVal = pnl?.cogs_dzd ?? (pnl as any)?.cogs?.cogs_all_orders_dzd ?? 0;
  const grossProfit = pnl?.gross_profit_dzd ?? (pnl as any)?.margins?.gross_profit_all_dzd ?? 0;
  const grossMarginPct = pnl?.gross_margin_percent ?? (pnl as any)?.margins?.gross_margin_pct_all ?? 0;
  const opExpenses = pnl?.operating_expenses_dzd ?? (pnl as any)?.operating_expenses?.total_expenses_dzd ?? 0;
  const netProfit = pnl?.net_operating_profit_dzd ?? (pnl as any)?.net_results?.net_profit_all_dzd ?? 0;
  const netMarginPct = pnl?.net_margin_percent ?? (pnl as any)?.net_results?.net_margin_pct_all ?? 0;
  const ordCount = pnl?.orders_count ?? (pnl as any)?.revenue?.orders_count ?? 0;
  const unitsSold = pnl?.units_sold ?? 0;
  const storeCount = (pnl as any)?.in_store_sales_count ?? 0;

  const ledgerEntries: LedgerEntry[] = ledger?.entries || (ledger as any)?.items || [];
  const totDebits = ledger?.total_debits_dzd ?? (ledger as any)?.total_debit_dzd ?? 0;
  const totCredits = ledger?.total_credits_dzd ?? (ledger as any)?.total_credit_dzd ?? 0;
  const isBalanced = Boolean(ledger?.is_balanced);
  const entriesCount = ledger?.entries_count ?? ledgerEntries.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#063D2E]/10">
        <div>
          <h2 className="text-2xl font-serif font-bold text-[#063D2E] tracking-tight">
            {t("accounting.title")}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            {t("accounting.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadAllAccountingData()}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl border border-[#063D2E]/20 text-[#063D2E] hover:bg-[#063D2E]/5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>{t("common.refresh")}</span>
          </button>
          <button
            onClick={handleExportOrdersCsv}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] shadow-xs transition-all"
          >
            <Download className="w-3.5 h-3.5 text-[#D4AF62]" />
            <span>CSV</span>
          </button>
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("pnl")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative inline-flex items-center gap-1.5 ${
            activeTab === "pnl"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>{t("accounting.tab_pnl")}</span>
        </button>
        <button
          onClick={() => setActiveTab("products")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative inline-flex items-center gap-1.5 ${
            activeTab === "products"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          <Tag className="w-3.5 h-3.5" />
          <span>{t("accounting.tab_products")} ({products.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("ledger")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative inline-flex items-center gap-1.5 ${
            activeTab === "ledger"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>{t("accounting.tab_ledger")}</span>
        </button>
      </div>

      {/* Error notification */}
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

      {/* Loading state */}
      {loading && (
        <div className="p-12 text-center text-xs text-gray-400">
          {t("status.loading")}
        </div>
      )}

      {/* TAB 1: P&L Statement */}
      {!loading && activeTab === "pnl" && (
        <div className="space-y-6">
          {/* High level KPI cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200">
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 font-semibold">
                <span className="flex items-center gap-1.5 font-bold text-gray-700">
                  <DollarSign className="w-4 h-4 text-[#063D2E]" />
                  {t("accounting.stat_revenue")}
                </span>
              </div>
              <div className="text-2xl font-bold font-mono text-gray-900 mt-2">
                {totalRev.toLocaleString()} <span className="text-xs font-sans text-[#D4AF62]">DZD</span>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                Articles {grossRev.toLocaleString()} + livraison {deliveryRev.toLocaleString()} DZD
                <br />
                {ordCount} commande(s) en ligne • {storeCount} vente(s) magasin • {unitsSold} pièce(s)
              </div>
            </div>

            <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200">
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 font-semibold">
                <span className="flex items-center gap-1.5 font-bold text-emerald-800">
                  <TrendingUp className="w-4 h-4 text-emerald-700" />
                  {t("accounting.stat_gross_margin")}
                </span>
                <span className="text-[10px] bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full">{grossMarginPct}%</span>
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-700 mt-2">
                {grossProfit.toLocaleString()} <span className="text-xs font-sans text-emerald-600">DZD</span>
              </div>
              <div className="text-[11px] text-emerald-600 font-semibold mt-1">
                Chiffre d'affaires − coût d'achat
              </div>
            </div>

            <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200">
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 font-semibold">
                <span className="flex items-center gap-1.5 font-bold text-red-800">
                  <Receipt className="w-4 h-4 text-red-600" />
                  {t("accounting.cost_of_goods")}
                </span>
              </div>
              <div className="text-2xl font-bold font-mono text-red-600 mt-2">
                -{cogsVal.toLocaleString()} <span className="text-xs font-sans text-red-400">DZD</span>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">COGS / CAMV</div>
            </div>

            <div
              className={`p-5 rounded-2xl shadow-sm border transition-all duration-200 ${
                netProfit >= 0
                  ? "bg-gradient-to-br from-[#063D2E] to-[#0A5C45] text-white border-[#063D2E]"
                  : "bg-red-50 text-red-900 border-red-200"
              }`}
            >
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-[#D4AF62] font-bold">
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-[#D4AF62]" />
                  {t("accounting.stat_net_profit")}
                </span>
                <span className="text-[10px] bg-white/10 text-[#E8D4A5] font-bold px-2 py-0.5 rounded-full border border-white/15">
                  {netMarginPct}%
                </span>
              </div>
              <div className="text-2xl font-bold font-mono mt-2">
                {netProfit.toLocaleString()} <span className="text-xs font-sans">DZD</span>
              </div>
            </div>
          </div>

          {/* Visual Profit Waterfall Breakdown */}
          {totalRev > 0 && (
            <div className="p-4 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#063D2E]">{t("accounting.tab_pnl")}</span>
                <span className="text-[11px] text-gray-400 font-mono">CA: {totalRev.toLocaleString()} DZD</span>
              </div>
              {(() => {
                const cogsPct = Math.min(100, Math.max(0, ((cogsVal / totalRev) * 100))).toFixed(1);
                const opexPct = Math.min(100, Math.max(0, ((opExpenses / totalRev) * 100))).toFixed(1);
                const netPct = Math.min(100, Math.max(0, ((Math.max(0, netProfit) / totalRev) * 100))).toFixed(1);
                return (
                  <div className="space-y-1.5">
                    <div className="h-3.5 w-full bg-gray-100 rounded-full overflow-hidden flex shadow-inner">
                      <div style={{ width: `${cogsPct}%` }} className="bg-amber-600 transition-all" />
                      <div style={{ width: `${opexPct}%` }} className="bg-red-500 transition-all" />
                      <div style={{ width: `${netPct}%` }} className="bg-emerald-600 transition-all" />
                    </div>
                    <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-500 pt-0.5">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-600" /> COGS: <strong>{cogsPct}%</strong> ({cogsVal.toLocaleString()} DZD)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> OPEX: <strong>{opexPct}%</strong> ({opExpenses.toLocaleString()} DZD)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" /> {t("accounting.stat_net_profit")}: <strong>{netPct}%</strong> ({netProfit.toLocaleString()} DZD)
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Product Profitability Matrix */}
      {!loading && activeTab === "products" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-50 p-3 rounded-xl border border-gray-200">
            <div className="relative w-full sm:w-80">
              <input
                type="text"
                placeholder={t("common.search")}
                value={searchProduct}
                onChange={(e) => setSearchProduct(e.target.value)}
                className="w-full text-xs pl-8 pr-3 py-2 border border-gray-300 rounded-xl focus:border-[#063D2E] outline-none"
              />
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
            </div>
            <div className="text-xs text-gray-500">
              {filteredProducts.length} référence(s)
            </div>
          </div>

          <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">{t("accounting.th_product")}</th>
                    <th className="py-3 px-4">SKU</th>
                    <th className="py-3 px-4 text-right">{t("accounting.th_cost")}</th>
                    <th className="py-3 px-4 text-right">{t("accounting.th_price")}</th>
                    <th className="py-3 px-4 text-right">{t("accounting.net_margin")}</th>
                    <th className="py-3 px-4 text-center">{t("accounting.th_margin")}</th>
                    <th className="py-3 px-4 text-center">{t("accounting.th_units")}</th>
                    <th className="py-3 px-4 text-right">{t("accounting.stat_revenue")}</th>
                    <th className="py-3 px-4 text-right">{t("accounting.th_profit")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredProducts.map((p) => {
                    const prodName = p.name || (p as any).name_fr || `Produit #${p.id}`;
                    const prodSku = p.sku || "—";
                    const cost = Number(p.purchase_cost_dzd ?? (p as any).purchase_cost_dzd ?? 0);
                    const sell = Number(p.selling_price_dzd ?? (p as any).selling_price_dzd ?? 0);
                    const unitProfit = Number(p.unit_profit_dzd ?? (sell - cost));
                    const marginPct = Number(p.unit_margin_percent ?? (p as any).gross_margin_pct ?? (sell > 0 ? (unitProfit / sell) * 100 : 0)).toFixed(1);
                    const units = Number(p.units_sold || 0);
                    const rev = Number(p.total_revenue_dzd || 0);
                    const totProfit = Number(p.total_profit_dzd ?? (unitProfit * units));
                    const isHighMargin = Number(marginPct) >= 50;
                    const isPositive = totProfit >= 0;
                    return (
                      <tr key={p.id} className="hover:bg-gray-50/80 transition-colors">
                        <td className="py-3 px-4 font-semibold text-gray-800">
                          {prodName}
                        </td>
                        <td className="py-3 px-4 font-mono text-gray-400">
                          {prodSku}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-gray-600">
                          {cost.toLocaleString()} DZD
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-gray-900">
                          {sell.toLocaleString()} DZD
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-emerald-700">
                          +{unitProfit.toLocaleString()} DZD
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              isHighMargin
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {marginPct}%
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-bold text-gray-700">
                          {units}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-gray-700">
                          {rev.toLocaleString()} DZD
                        </td>
                        <td
                          className={`py-3 px-4 text-right font-mono font-bold ${
                            isPositive ? "text-emerald-700" : "text-red-600"
                          }`}
                        >
                          {totProfit.toLocaleString()} DZD
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Accounting Ledger (Double-Entry) */}
      {!loading && activeTab === "ledger" && (
        <div className="space-y-4">
          <div
            className={`p-4 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
              isBalanced
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            <div className="flex items-center gap-3">
              {isBalanced ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-700 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-red-700 shrink-0" />
              )}
              <div>
                <div className="font-bold text-xs">
                  {isBalanced
                    ? "Grand Livre Conforme & Équilibré"
                    : "Déséquilibre détecté !"}
                </div>
                <div className="text-[11px] opacity-80">
                  Débits = {totDebits.toLocaleString()} DZD | Crédits = {totCredits.toLocaleString()} DZD
                </div>
              </div>
            </div>
            <div className="text-xs font-mono font-semibold">
              {entriesCount} écritures
            </div>
          </div>

          <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">N°</th>
                    <th className="py-3 px-4">{t("expense_report.th_date")}</th>
                    <th className="py-3 px-4">Compte</th>
                    <th className="py-3 px-4">{t("expense_report.th_desc")}</th>
                    <th className="py-3 px-4 text-right">Débit</th>
                    <th className="py-3 px-4 text-right">Crédit</th>
                    <th className="py-3 px-4 text-right">Réf</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ledgerEntries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-gray-700 whitespace-nowrap">
                        {entry.entry_number}
                      </td>
                      <td className="py-3 px-4 font-mono text-gray-500 whitespace-nowrap">
                        {entry.entry_date}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="font-mono font-bold text-[#063D2E] mr-1.5">
                          {entry.account_code}
                        </span>
                        <span className="text-gray-500 text-[11px]">{entry.account_name}</span>
                      </td>
                      <td className="py-3 px-4 text-gray-700">
                        {entry.description}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-gray-900 whitespace-nowrap">
                        {entry.debit_dzd > 0 ? `${entry.debit_dzd.toLocaleString()} DZD` : "—"}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-gray-900 whitespace-nowrap">
                        {entry.credit_dzd > 0 ? `${entry.credit_dzd.toLocaleString()} DZD` : "—"}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-gray-400 whitespace-nowrap">
                        {entry.reference_id ? `${entry.reference_type} #${entry.reference_id}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
