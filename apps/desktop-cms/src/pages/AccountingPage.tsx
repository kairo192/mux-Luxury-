import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  DollarSign,
  Receipt,
  PieChart,
  BarChart3,
  Layers,
  Download,
  RefreshCw,
  Sparkles,
  ArrowUpRight,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

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
      setError(err instanceof Error ? err.message : "Erreur lors du chargement des états comptables");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllAccountingData();
  }, []);

  const handleExportOrdersCsv = () => {
    const token = localStorage.getItem("luxe_admin_token") || "";
    const apiBase = "http://127.0.0.1:8000";
    window.open(`${apiBase}/api/v1/admin/orders/export.csv?token=${token}`, "_blank");
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
            Comptabilité, Rentabilité & Grand Livre
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Compte de résultat en temps réel, marges par produit et journal d'écritures en partie double équilibrée.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadAllAccountingData()}
            className="px-4 py-2 text-xs font-semibold rounded border border-[#063D2E]/20 text-[#063D2E] hover:bg-[#063D2E]/5 transition-colors"
          >
            🔄 Actualiser
          </button>
          <button
            onClick={handleExportOrdersCsv}
            className="px-4 py-2 text-xs font-semibold rounded bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] shadow-sm transition-all flex items-center gap-2"
          >
            <span>📥</span> Exporter Commandes CSV
          </button>
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("pnl")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative ${
            activeTab === "pnl"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          📊 Compte de Résultat (P&L)
        </button>
        <button
          onClick={() => setActiveTab("products")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative ${
            activeTab === "products"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          🏷️ Rentabilité par Produit ({products.length})
        </button>
        <button
          onClick={() => setActiveTab("ledger")}
          className={`pb-3 px-4 text-xs font-bold transition-all relative ${
            activeTab === "ledger"
              ? "text-[#063D2E] border-b-2 border-[#063D2E]"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          📜 Grand Livre & Journal Comptable
        </button>
      </div>

      {/* Error notification */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md flex justify-between items-center">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="text-red-500 font-bold">&times;</button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="p-12 text-center text-xs text-gray-400">
          Calcul des agrégats comptables et consolidation du grand livre...
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
                  Chiffre d'Affaires Brut
                </span>
                <span className="text-[10px] bg-[#063D2E]/10 text-[#063D2E] font-bold px-2 py-0.5 rounded-full">Ventes</span>
              </div>
              <div className="text-2xl font-bold font-mono text-gray-900 mt-2">
                {grossRev.toLocaleString()} <span className="text-xs font-sans text-[#D4AF62]">DZD</span>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">
                {ordCount} commandes • {unitsSold} pièces
              </div>
            </div>

            <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200">
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 font-semibold">
                <span className="flex items-center gap-1.5 font-bold text-emerald-800">
                  <TrendingUp className="w-4 h-4 text-emerald-700" />
                  Marge Brute Ventes
                </span>
                <span className="text-[10px] bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full">{grossMarginPct}%</span>
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-700 mt-2">
                {grossProfit.toLocaleString()} <span className="text-xs font-sans text-emerald-600">DZD</span>
              </div>
              <div className="text-[11px] text-emerald-600 font-semibold mt-1">
                Taux de marge brute commerciale
              </div>
            </div>

            <div className="p-5 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md transition-all duration-200">
              <div className="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 font-semibold">
                <span className="flex items-center gap-1.5 font-bold text-red-800">
                  <Receipt className="w-4 h-4 text-red-600" />
                  Charges d'Exploitation
                </span>
                <span className="text-[10px] bg-red-50 text-red-700 font-bold px-2 py-0.5 rounded-full">OPEX</span>
              </div>
              <div className="text-2xl font-bold font-mono text-red-600 mt-2">
                -{opExpenses.toLocaleString()} <span className="text-xs font-sans text-red-400">DZD</span>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">Loyers, salaires, packaging, pub...</div>
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
                  Bénéfice Net d'Exploitation
                </span>
                <span className="text-[10px] bg-white/10 text-[#E8D4A5] font-bold px-2 py-0.5 rounded-full border border-white/15">
                  {netMarginPct}%
                </span>
              </div>
              <div className="text-2xl font-bold font-mono mt-2">
                {netProfit.toLocaleString()} <span className="text-xs font-sans">DZD</span>
              </div>
              <div className="text-[11px] mt-1 font-semibold text-[#D4AF62]">
                Résultat net après COGS et charges
              </div>
            </div>
          </div>

          {/* Visual Profit Waterfall Breakdown */}
          {totalRev > 0 && (
            <div className="p-4 bg-white rounded-2xl border border-[#063D2E]/10 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#063D2E]">Décomposition Visuelle de la Rentabilité</span>
                <span className="text-[11px] text-gray-400 font-mono">CA Consolidé: {totalRev.toLocaleString()} DZD</span>
              </div>
              {(() => {
                const cogsPct = Math.min(100, Math.max(0, ((cogsVal / totalRev) * 100))).toFixed(1);
                const opexPct = Math.min(100, Math.max(0, ((opExpenses / totalRev) * 100))).toFixed(1);
                const netPct = Math.min(100, Math.max(0, ((Math.max(0, netProfit) / totalRev) * 100))).toFixed(1);
                return (
                  <div className="space-y-1.5">
                    <div className="h-3.5 w-full bg-gray-100 rounded-full overflow-hidden flex shadow-inner">
                      <div style={{ width: `${cogsPct}%` }} className="bg-amber-600 transition-all" title={`Coût d'achat: ${cogsPct}%`} />
                      <div style={{ width: `${opexPct}%` }} className="bg-red-500 transition-all" title={`Charges d'exploitation: ${opexPct}%`} />
                      <div style={{ width: `${netPct}%` }} className="bg-emerald-600 transition-all" title={`Bénéfice net: ${netPct}%`} />
                    </div>
                    <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-500 pt-0.5">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-600" /> Coût d'achat (COGS): <strong>{cogsPct}%</strong> ({cogsVal.toLocaleString()} DZD)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Charges (OPEX): <strong>{opexPct}%</strong> ({opExpenses.toLocaleString()} DZD)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" /> Bénéfice Net: <strong>{netPct}%</strong> ({netProfit.toLocaleString()} DZD)
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* Detailed Statement Table */}
          <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-[#063D2E] text-white flex items-center justify-between">
              <h3 className="text-sm font-serif font-bold text-[#D4AF62] uppercase tracking-wider">
                Compte de Résultat Synthétique (Système Comptable Financier - DZD)
              </h3>
              <span className="text-xs text-white/80 font-mono">Période Globale à date</span>
            </div>

            <div className="divide-y divide-gray-100 text-xs">
              {/* Gross Revenue */}
              <div className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div>
                  <span className="font-bold text-gray-900">1. Chiffre d'Affaires Produits (Ventes HT)</span>
                  <p className="text-[11px] text-gray-500">Compte SCF 701 — Ventes de marchandises catalogue</p>
                </div>
                <div className="font-mono font-bold text-gray-900">
                  +{grossRev.toLocaleString()} DZD
                </div>
              </div>

              {/* Delivery Revenue */}
              <div className="flex items-center justify-between p-4 hover:bg-gray-50 bg-gray-50/50">
                <div>
                  <span className="font-medium text-gray-700">2. Prestations Logistiques & Port Facturé</span>
                  <p className="text-[11px] text-gray-500">Compte SCF 706 — Frais de livraison 58 wilayas facturés</p>
                </div>
                <div className="font-mono text-gray-700">
                  +{deliveryRev.toLocaleString()} DZD
                </div>
              </div>

              {/* Total Revenue */}
              <div className="flex items-center justify-between p-4 bg-emerald-50/40 font-bold">
                <div>
                  <span className="text-[#063D2E] uppercase">Total Recettes d'Exploitation</span>
                </div>
                <div className="font-mono text-[#063D2E]">
                  {totalRev.toLocaleString()} DZD
                </div>
              </div>

              {/* COGS */}
              <div className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div>
                  <span className="font-bold text-red-600">3. Coût d'Achat des Marchandises Vendues (COGS / CAMV)</span>
                  <p className="text-[11px] text-gray-500">
                    Compte SCF 607 — Coût d'achat réel des articles vendus (valorisé au PMP)
                  </p>
                </div>
                <div className="font-mono font-bold text-red-600">
                  -{cogsVal.toLocaleString()} DZD
                </div>
              </div>

              {/* Gross Profit Subtotal */}
              <div className="flex items-center justify-between p-4 bg-[#063D2E]/5 font-bold border-t-2 border-b-2 border-[#063D2E]/20">
                <div>
                  <span className="text-gray-900 uppercase">
                    = MARGE COMMERCIALE BRUTE ({grossMarginPct}% DU CA)
                  </span>
                </div>
                <div className="font-mono text-emerald-800 text-sm">
                  {grossProfit.toLocaleString()} DZD
                </div>
              </div>

              {/* Operating Expenses */}
              <div className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div>
                  <span className="font-bold text-red-700">4. Charges d'Exploitation & Frais Généraux</span>
                  <p className="text-[11px] text-gray-500">
                    Comptes SCF 61/62/63/64 — Loyers, salaires, packaging, publicités, énergie
                  </p>
                </div>
                <div className="font-mono font-bold text-red-700">
                  -{opExpenses.toLocaleString()} DZD
                </div>
              </div>

              {/* Net Operating Profit */}
              <div
                className={`flex items-center justify-between p-5 font-bold text-sm ${
                  netProfit >= 0
                    ? "bg-[#063D2E] text-[#D4AF62]"
                    : "bg-red-100 text-red-800"
                }`}
              >
                <div>
                  <span className="uppercase tracking-wider">
                    = RÉSULTAT NET D'EXPLOITATION (BÉNÉFICE NET RÉEL)
                  </span>
                  <p className="text-[11px] font-normal opacity-80">
                    Solde final net après déduction intégrale des achats et des charges opérationnelles
                  </p>
                </div>
                <div className="font-mono text-base">
                  {netProfit.toLocaleString()} DZD ({netMarginPct}%)
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Product Profitability Matrix */}
      {!loading && activeTab === "products" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-50 p-3 rounded-lg border border-gray-200">
            <div className="relative w-full sm:w-80">
              <input
                type="text"
                placeholder="Rechercher produit, référence..."
                value={searchProduct}
                onChange={(e) => setSearchProduct(e.target.value)}
                className="w-full text-xs pl-8 pr-3 py-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
              />
              <span className="absolute left-2.5 top-2 text-gray-400 text-xs">🔍</span>
            </div>
            <div className="text-xs text-gray-500">
              {filteredProducts.length} référence(s) analysée(s)
            </div>
          </div>

          <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Article</th>
                    <th className="py-3 px-4">Réf (SKU)</th>
                    <th className="py-3 px-4 text-right">Prix d'Achat (PMP)</th>
                    <th className="py-3 px-4 text-right">Prix de Vente</th>
                    <th className="py-3 px-4 text-right">Marge Unitaire</th>
                    <th className="py-3 px-4 text-center">Taux Marge %</th>
                    <th className="py-3 px-4 text-center">Qté Vendue</th>
                    <th className="py-3 px-4 text-right">CA Total Généré</th>
                    <th className="py-3 px-4 text-right">Bénéfice Net Total</th>
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
          {/* Balance validation alert */}
          <div
            className={`p-4 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
              isBalanced
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">{isBalanced ? "✓" : "⚠️"}</span>
              <div>
                <div className="font-bold text-xs">
                  {isBalanced
                    ? "Grand Livre Conforme & Équilibré (Partie Double Vérifiée)"
                    : "Déséquilibre détecté dans le grand livre !"}
                </div>
                <div className="text-[11px] opacity-80">
                  Total Débits = {totDebits.toLocaleString()} DZD | Total Crédits = {totCredits.toLocaleString()} DZD
                </div>
              </div>
            </div>
            <div className="text-xs font-mono font-semibold">
              {entriesCount} lignes d'écritures
            </div>
          </div>

          {/* Ledger Table */}
          <div className="bg-white rounded-lg border border-[#063D2E]/10 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">N° Écriture</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Compte SCF</th>
                    <th className="py-3 px-4">Libellé de l'Écriture</th>
                    <th className="py-3 px-4 text-right">Débit (DZD)</th>
                    <th className="py-3 px-4 text-right">Crédit (DZD)</th>
                    <th className="py-3 px-4 text-right">Réf Pièce</th>
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

