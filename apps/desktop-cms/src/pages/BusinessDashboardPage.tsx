import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Store,
  Globe,
  TrendingUp,
  Boxes,
  Landmark,
  HardDrive,
  AlertTriangle,
  Package,
  Wallet,
  Trophy,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

const GREEN = "#063D2E";

export const BusinessDashboardPage: React.FC = () => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await DesktopCmsApi.getBusinessDashboard());
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

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-20 text-base text-gray-500">
        <RefreshCw className="w-6 h-6 animate-spin mr-3" /> Chargement de la synthèse…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
        <AlertTriangle className="w-5 h-5" /> {error}
      </div>
    );
  }
  if (!data) return null;

  const s = data.sales;
  const m = data.margin_month;
  const inv = data.inventory;
  const reg = data.cash_register;
  const dev = data.devices;
  const ops = data.operations;

  return (
    <div className="space-y-5 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <TrendingUp className="w-5 h-5" /> Synthèse du magasin (physique + en ligne)
        </h3>
        <button type="button" onClick={load} className="h-11 px-4 rounded-2xl border-2 border-gray-200 font-bold flex items-center gap-2 active:scale-95">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Actualiser
        </button>
      </div>

      {/* TODAY */}
      <Section title="Aujourd'hui">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile icon={Store} label="Ventes magasin" value={fmt(s.in_store.today.revenue_dzd)} sub={`${s.in_store.today.count} ticket(s)`} accent />
          <Tile icon={Globe} label="Ventes en ligne" value={fmt(s.online.today.revenue_dzd)} sub={`${s.online.today.count} commande(s)`} />
          <Tile icon={Wallet} label="Total du jour" value={fmt(s.combined.today_revenue_dzd)} sub="net des remb." />
          <Tile icon={RefreshCw} label="Remb. magasin" value={fmt(s.in_store_refunds.today_dzd)} sub="aujourd'hui" />
        </div>
      </Section>

      {/* MONTH + MARGIN */}
      <Section title="Ce mois-ci">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile icon={Store} label="Magasin (mois)" value={fmt(s.in_store.month.revenue_dzd)} sub={`ticket moyen ${fmt(data.averages.in_store_ticket_dzd)}`} accent />
          <Tile icon={Globe} label="En ligne (mois)" value={fmt(s.online.month.revenue_dzd)} sub={`panier moyen ${fmt(data.averages.online_aov_dzd)}`} />
          <Tile icon={Wallet} label="Chiffre d'affaires" value={fmt(m.revenue_dzd)} sub="net des remboursements" />
          <Tile icon={Package} label="Coût des ventes" value={fmt(m.cogs_dzd)} sub="COGS du mois" />
        </div>
        {/* Clearly distinguished: revenue vs gross margin vs net profit */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
          <BigStat label="Chiffre d'affaires" value={fmt(m.revenue_dzd)} tone="neutral" />
          <BigStat label={`Marge brute (${m.gross_margin_percent}%)`} value={fmt(m.gross_margin_dzd)} tone="gold" />
          <BigStat label="Bénéfice net (après charges)" value={fmt(m.net_profit_dzd)} tone={m.net_profit_dzd >= 0 ? "green" : "red"} />
        </div>
        <p className="text-[11px] text-gray-400 mt-1">
          Charges d'exploitation du mois : {fmt(m.operating_expenses_dzd)}. Chiffre d'affaires, marge brute et bénéfice net sont des mesures distinctes.
        </p>
      </Section>

      {/* OPERATIONS GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="Caisse" icon={Landmark}>
          {reg.open ? (
            <div className="space-y-1">
              <StatusDot ok label="Caisse ouverte" />
              <Row label="Fond" value={fmt(reg.session.opening_float_dzd)} />
              <Row label="Ventes" value={`${fmt(reg.session.sales_total_dzd || 0)} (${reg.session.sales_count || 0})`} />
              <Row label="Caisse attendue" value={fmt(reg.session.expected_cash_dzd || 0)} strong />
            </div>
          ) : (
            <StatusDot label="Caisse fermée" />
          )}
        </Panel>

        <Panel title="Stock" icon={Boxes}>
          <Row label="Valorisation (coût)" value={fmt(inv.valuation_cost_dzd)} strong />
          <Row label="Valorisation (vente)" value={fmt(inv.valuation_retail_dzd)} />
          <Row label="Stock faible" value={String(inv.low_stock_count)} warn={inv.low_stock_count > 0} />
          <Row label="Ruptures" value={String(inv.out_of_stock_count)} warn={inv.out_of_stock_count > 0} />
        </Panel>

        <Panel title="Appareils & Opérations" icon={HardDrive}>
          <Row label="Appareils OK" value={`${dev.ok}/${dev.total}`} />
          {dev.error > 0 && <Row label="Appareils en erreur" value={String(dev.error)} warn />}
          <Row label="Commandes à traiter" value={String(ops.pending_orders)} />
          <Row label="Livraisons en cours" value={String(ops.pending_deliveries)} />
          <Row label="Dû aux fournisseurs" value={fmt(ops.supplier_outstanding_dzd)} warn={ops.supplier_outstanding_dzd > 0} />
        </Panel>
      </div>

      {/* BEST SELLERS + LOW STOCK */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Meilleures ventes" icon={Trophy}>
          {data.best_sellers.length === 0 && <div className="text-gray-400">Aucune vente enregistrée.</div>}
          {data.best_sellers.map((b: any, i: number) => (
            <div key={b.variant_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
              <span className="truncate pr-2"><span className="text-[#D4AF62] font-bold mr-1">{i + 1}.</span>{b.product_name} <span className="text-gray-400 font-mono">{b.sku}</span></span>
              <span className="font-bold font-mono">{b.qty_sold}</span>
            </div>
          ))}
        </Panel>

        <Panel title="Stock faible" icon={AlertTriangle}>
          {data.low_stock.length === 0 && <div className="text-gray-400">Aucune alerte stock.</div>}
          {data.low_stock.map((v: any) => (
            <div key={v.variant_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
              <span className="truncate pr-2">{v.product_name} — {v.variant_title} <span className="text-gray-400 font-mono">{v.sku}</span></span>
              <span className={`font-bold font-mono ${v.stock_qty === 0 ? "text-red-600" : "text-amber-600"}`}>{v.stock_qty}</span>
            </div>
          ))}
        </Panel>
      </div>

      <p className="text-[11px] text-gray-400 text-center">
        Généré le {new Date(data.generated_at).toLocaleString("fr-DZ")} · toutes les valeurs proviennent d'enregistrements réels.
      </p>
    </div>
  );
};

// --------------------------------------------------------------------- bits
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div>
    <h4 className="text-xs uppercase tracking-wide font-bold text-gray-400 mb-2">{title}</h4>
    {children}
  </div>
);

const Tile: React.FC<{ icon: any; label: string; value: string; sub?: string; accent?: boolean }> = ({ icon: Icon, label, value, sub, accent }) => (
  <div className={`p-4 rounded-2xl border ${accent ? "border-[#D4AF62]/50 bg-[#FCFBF8]" : "border-gray-200 bg-white"}`}>
    <div className="flex items-center gap-2 text-gray-500 mb-1">
      <Icon className="w-4 h-4" /> <span className="text-[11px] font-bold uppercase tracking-wide">{label}</span>
    </div>
    <div className="text-xl font-extrabold text-[#063D2E] font-mono tabular-nums">{value}</div>
    {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
  </div>
);

const BigStat: React.FC<{ label: string; value: string; tone: "neutral" | "gold" | "green" | "red" }> = ({ label, value, tone }) => {
  const tones: Record<string, string> = {
    neutral: "bg-white border-gray-200 text-[#063D2E]",
    gold: "bg-[#D4AF62]/10 border-[#D4AF62]/40 text-[#7a5c16]",
    green: "bg-emerald-50 border-emerald-200 text-emerald-700",
    red: "bg-red-50 border-red-200 text-red-700",
  };
  return (
    <div className={`p-4 rounded-2xl border-2 ${tones[tone]}`}>
      <div className="text-[11px] font-bold uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-2xl font-extrabold font-mono tabular-nums mt-1">{value}</div>
    </div>
  );
};

const Panel: React.FC<{ title: string; icon: any; children: React.ReactNode }> = ({ title, icon: Icon, children }) => (
  <div className="bg-white p-4 rounded-2xl border border-gray-200">
    <h4 className="font-bold text-[#063D2E] mb-2 flex items-center gap-2" style={{ color: GREEN }}>
      <Icon className="w-5 h-5" /> {title}
    </h4>
    <div className="space-y-0.5">{children}</div>
  </div>
);

const Row: React.FC<{ label: string; value: string; strong?: boolean; warn?: boolean }> = ({ label, value, strong, warn }) => (
  <div className="flex items-center justify-between py-1">
    <span className="text-gray-500">{label}</span>
    <span className={`font-mono ${strong ? "font-extrabold text-[#063D2E]" : "font-bold"} ${warn ? "text-amber-600" : ""}`}>{value}</span>
  </div>
);

const StatusDot: React.FC<{ ok?: boolean; label: string }> = ({ ok, label }) => (
  <div className="flex items-center gap-2 font-bold mb-1">
    <span className={`w-3 h-3 rounded-full ${ok ? "bg-emerald-500" : "bg-gray-300"}`} />
    {label}
  </div>
);
