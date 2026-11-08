import React, { useEffect, useState, useCallback } from "react";
import {
  Receipt,
  Download,
  RefreshCw,
  AlertTriangle,
  CalendarRange,
  Wallet,
  Clock,
  Layers,
} from "lucide-react";
import { DesktopCmsApi, getAccessToken } from "../api/adminClient";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

function todayIso(): string { return new Date().toISOString().slice(0, 10); }
function monthStartIso(): string { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; }

export const ExpenseReportPage: React.FC = () => {
  const [from, setFrom] = useState(monthStartIso());
  const [to, setTo] = useState(todayIso());
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: string, t: string) => {
    setLoading(true);
    setError(null);
    try {
      setData(await DesktopCmsApi.getExpenseReport(f, t));
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(from, to); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const downloadCsv = async () => {
    try {
      const url = DesktopCmsApi.expenseReportCsvUrl(from, to);
      const tok = getAccessToken();
      const resp = await fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `expenses_${from}_${to}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError("Téléchargement CSV échoué");
    }
  };

  const applyPreset = (preset: "today" | "7d" | "month" | "30d" | "year") => {
    const t = todayIso();
    let f = t;
    if (preset === "7d") { const d = new Date(); d.setDate(d.getDate() - 6); f = d.toISOString().slice(0, 10); }
    if (preset === "month") f = monthStartIso();
    if (preset === "30d") { const d = new Date(); d.setDate(d.getDate() - 29); f = d.toISOString().slice(0, 10); }
    if (preset === "year") f = `${new Date().getFullYear()}-01-01`;
    setFrom(f); setTo(t); load(f, t);
  };

  const topCatTotal = data?.by_category?.[0]?.total_dzd || 0;

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <Receipt className="w-5 h-5" /> Rapport de dépenses
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Du</span>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Au</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <button type="button" onClick={() => load(from, to)} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Générer
          </button>
          <button type="button" onClick={downloadCsv} disabled={!data} className="h-12 px-5 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-40">
            <Download className="w-4 h-4" /> CSV
          </button>
          <div className="flex gap-1 ml-auto flex-wrap">
            {[["7d", "7 jours"], ["month", "Ce mois"], ["30d", "30 jours"], ["year", "Année"]].map(([p, lbl]) => (
              <button key={p} type="button" onClick={() => applyPreset(p as any)} className="h-10 px-3 rounded-xl border-2 border-gray-200 text-xs font-bold active:scale-95">{lbl}</button>
            ))}
          </div>
        </div>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile icon={Wallet} label="Total dépenses" value={fmt(data.totals.total_dzd)} sub={`${data.totals.count} entrée(s)`} accent />
            <Tile icon={Layers} label="Catégories" value={String(data.totals.categories_count)} sub="distinctes" />
            <Tile icon={Clock} label="En attente" value={fmt(data.totals.pending_dzd)} sub="à régler" tone={data.totals.pending_dzd > 0 ? "warn" : undefined} />
            <Tile icon={CalendarRange} label="Jours actifs" value={String(data.by_day.length)} sub="jour(s)" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-2">Par catégorie</h4>
              <div className="space-y-2">
                {data.by_category.length === 0 && <div className="text-gray-400">Aucune dépense.</div>}
                {data.by_category.map((c: any) => {
                  const pct = data.totals.total_dzd > 0 ? Math.round((c.total_dzd / data.totals.total_dzd) * 100) : 0;
                  const barPct = topCatTotal > 0 ? Math.round((c.total_dzd / topCatTotal) * 100) : 0;
                  return (
                    <div key={c.category}>
                      <div className="flex items-center justify-between text-[12px]">
                        <span className="font-bold text-[#063D2E] truncate">{c.category}</span>
                        <span className="font-mono font-bold whitespace-nowrap ml-2">{fmt(c.total_dzd)} <span className="text-gray-400 text-[10px]">({pct}%)</span></span>
                      </div>
                      <div className="h-2 rounded bg-gray-100 mt-1 overflow-hidden">
                        <div className="h-full bg-[#D4AF62]" style={{ width: `${barPct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 bg-[#063D2E] text-[#E8D4A5] font-bold">Entrées récentes</div>
              <div className="max-h-[50vh] overflow-auto">
                <table className="w-full text-left">
                  <thead className="bg-[#FCFBF8] text-[11px] uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Description</th>
                      <th className="px-3 py-2 text-right">Montant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.length === 0 && <tr><td colSpan={3} className="px-3 py-6 text-center text-gray-400">Aucune entrée.</td></tr>}
                    {data.items.map((it: any) => (
                      <tr key={it.id} className="border-t border-gray-100">
                        <td className="px-3 py-2 font-mono text-[11px] whitespace-nowrap">{it.expense_date}</td>
                        <td className="px-3 py-2">
                          <div className="truncate">{it.description}</div>
                          <div className="text-gray-400 text-[11px]">{it.category} · {it.payment_method}{it.payment_status === "pending" ? <span className="text-amber-700 font-bold ml-1">· en attente</span> : ""}</div>
                        </td>
                        <td className="px-3 py-2 text-right font-mono font-bold">{fmt(it.amount_dzd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <p className="text-[11px] text-gray-400 text-center">
            Période : {data.period.from} → {data.period.to}. Les dépenses « en attente » ne sont pas encore réglées.
          </p>
        </>
      ) : null}
    </div>
  );
};

const Tile: React.FC<{ icon: any; label: string; value: string; sub: string; accent?: boolean; tone?: "warn" }> = ({ icon: Icon, label, value, sub, accent, tone }) => {
  const base = tone === "warn" ? "border-amber-300 bg-amber-50 text-amber-700" : accent ? "border-[#D4AF62]/50 bg-[#FCFBF8] text-[#063D2E]" : "border-gray-200 bg-white text-[#063D2E]";
  return (
    <div className={`p-4 rounded-2xl border ${base}`}>
      <div className="flex items-center gap-2 opacity-70 mb-1">
        <Icon className="w-4 h-4" /> <span className="text-[11px] font-bold uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-xl font-extrabold font-mono tabular-nums">{value}</div>
      <div className="text-[11px] opacity-60 mt-0.5">{sub}</div>
    </div>
  );
};
