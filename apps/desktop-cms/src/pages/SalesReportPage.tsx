import React, { useEffect, useState, useCallback } from "react";
import {
  FileSpreadsheet,
  Download,
  RefreshCw,
  AlertTriangle,
  CalendarRange,
  Store,
  Globe,
  Wallet,
  RotateCcw,
  Trophy,
  Banknote,
} from "lucide-react";
import { DesktopCmsApi, getAccessToken } from "../api/adminClient";
import { useT } from "../i18n";
import { localDateIso } from "../utils/serverDate";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

function todayIso(): string { return localDateIso(); }
function monthStartIso(): string { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; }

export const SalesReportPage: React.FC = () => {
  const t = useT();
  const [from, setFrom] = useState(monthStartIso());
  const [to, setTo] = useState(todayIso());
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: string, tDate: string) => {
    setLoading(true);
    setError(null);
    try {
      setData(await DesktopCmsApi.getSalesReport(f, tDate));
    } catch (e: any) {
      setError(e?.userMessage || t("sales_report.load_error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(from, to); /* initial */ }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const downloadCsv = async () => {
    try {
      const url = DesktopCmsApi.salesReportCsvUrl(from, to);
      const tok = getAccessToken();
      const resp = await fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `sales_${from}_${to}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e: any) {
      setError(t("sales_report.download_error"));
    }
  };

  const applyPreset = (preset: "today" | "7d" | "month" | "30d") => {
    const today = todayIso();
    let f = today;
    if (preset === "today") f = today;
    if (preset === "7d") { const d = new Date(); d.setDate(d.getDate() - 6); f = localDateIso(d); }
    if (preset === "month") f = monthStartIso();
    if (preset === "30d") { const d = new Date(); d.setDate(d.getDate() - 29); f = localDateIso(d); }
    setFrom(f); setTo(today); load(f, today);
  };

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5" /> {t("sales_report.title")}
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("sales_report.from")}</span>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("sales_report.to")}</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <button type="button" onClick={() => load(from, to)} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {t("sales_report.btn_generate")}
          </button>
          <button type="button" onClick={downloadCsv} disabled={!data} className="h-12 px-5 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-40">
            <Download className="w-4 h-4" /> {t("sales_report.btn_csv")}
          </button>
          <div className="flex gap-1 ml-auto">
            {[
              ["today", t("sales_report.preset_today")],
              ["7d", t("sales_report.preset_7d")],
              ["month", t("sales_report.preset_month")],
              ["30d", t("sales_report.preset_30d")],
            ].map(([p, lbl]) => (
              <button key={p} type="button" onClick={() => applyPreset(p as any)} className="h-10 px-3 rounded-xl border-2 border-gray-200 text-xs font-bold active:scale-95">{lbl}</button>
            ))}
          </div>
        </div>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("sales_report.loading")}
        </div>
      ) : data ? (
        <>
          {/* TOTALS */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Tile icon={Globe} label={t("sales_report.tile_online")} value={fmt(data.totals.online_revenue_dzd)} sub={t("sales_report.sub_orders", { count: data.totals.online_count })} />
            <Tile icon={Store} label={t("sales_report.tile_store")} value={fmt(data.totals.in_store_revenue_dzd)} sub={t("sales_report.sub_tickets", { count: data.totals.in_store_count })} />
            <Tile icon={RotateCcw} label={t("sales_report.tile_refunds")} value={fmt(data.totals.in_store_refunds_dzd)} sub={t("sales_report.sub_refunds", { count: data.totals.in_store_refunds_count })} />
            <Tile icon={CalendarRange} label={t("sales_report.tile_active_days")} value={String(data.by_day.length)} sub={t("sales_report.sub_days")} />
            <Tile icon={Wallet} label={t("sales_report.tile_net_revenue")} value={fmt(data.totals.net_revenue_dzd)} sub={t("sales_report.sub_total_period")} accent />
          </div>

          {/* PER DAY */}
          <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 bg-[#063D2E] text-[#E8D4A5] font-bold">{t("sales_report.by_day_title")}</div>
            <div className="max-h-[48vh] overflow-auto">
              <table className="w-full text-left">
                <thead className="bg-[#FCFBF8] text-[11px] uppercase text-gray-500">
                  <tr>
                    <th className="px-4 py-2">{t("sales_report.th_day")}</th>
                    <th className="px-4 py-2 text-right">{t("sales_report.th_online")}</th>
                    <th className="px-4 py-2 text-right">{t("sales_report.th_store")}</th>
                    <th className="px-4 py-2 text-right">{t("sales_report.th_refunds")}</th>
                    <th className="px-4 py-2 text-right">{t("sales_report.th_net")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_day.length === 0 && (
                    <tr><td colSpan={5} className="px-4 py-10 text-center text-gray-400">{t("sales_report.no_sales_period")}</td></tr>
                  )}
                  {data.by_day.map((d: any) => (
                    <tr key={d.day} className="border-t border-gray-100">
                      <td className="px-4 py-2 font-mono">{d.day}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(d.online_revenue_dzd)} <span className="text-gray-400 text-[11px]">({d.online_count})</span></td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(d.in_store_revenue_dzd)} <span className="text-gray-400 text-[11px]">({d.in_store_count})</span></td>
                      <td className="px-4 py-2 text-right font-mono text-amber-700">{d.in_store_refunds_dzd ? `-${fmt(d.in_store_refunds_dzd)}` : "—"}</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-[#063D2E]">{fmt(d.net_revenue_dzd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* TOP + PAYMENTS */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-2 flex items-center gap-2"><Trophy className="w-5 h-5" /> {t("sales_report.top_products_title")}</h4>
              {data.top_products.length === 0 && <div className="text-gray-400">{t("sales_report.no_sales")}</div>}
              {data.top_products.map((p: any, i: number) => (
                <div key={p.variant_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <span className="truncate pr-2"><span className="text-[#D4AF62] font-bold mr-1">{i + 1}.</span>{p.product_name} <span className="text-gray-400 font-mono">{p.sku}</span></span>
                  <span className="font-bold font-mono">{p.qty_sold} · {fmt(p.revenue_dzd)}</span>
                </div>
              ))}
            </div>
            <div className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-2 flex items-center gap-2"><Banknote className="w-5 h-5" /> {t("sales_report.payment_methods_title")}</h4>
              {data.payment_breakdown.length === 0 && <div className="text-gray-400">{t("sales_report.no_payments")}</div>}
              {data.payment_breakdown.map((p: any) => (
                <div key={p.method} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <span className="capitalize">{p.method}</span>
                  <span className="font-bold font-mono">{fmt(p.net_dzd)} <span className="text-gray-400 text-[11px]">({p.count})</span></span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-gray-400 text-center">
            {t("sales_report.footnote", { from: data.period.from, to: data.period.to })}
          </p>
        </>
      ) : null}
    </div>
  );
};

const Tile: React.FC<{ icon: any; label: string; value: string; sub: string; accent?: boolean }> = ({ icon: Icon, label, value, sub, accent }) => (
  <div className={`p-4 rounded-2xl border ${accent ? "border-[#D4AF62]/50 bg-[#FCFBF8]" : "border-gray-200 bg-white"}`}>
    <div className="flex items-center gap-2 text-gray-500 mb-1">
      <Icon className="w-4 h-4" /> <span className="text-[11px] font-bold uppercase tracking-wide">{label}</span>
    </div>
    <div className="text-xl font-extrabold text-[#063D2E] font-mono tabular-nums">{value}</div>
    <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>
  </div>
);
