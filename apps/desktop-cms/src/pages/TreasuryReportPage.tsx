import React, { useEffect, useState, useCallback } from "react";
import { Landmark, Download, RefreshCw, AlertTriangle, ArrowUp, ArrowDown, Wallet, Banknote, Building2 } from "lucide-react";
import { DesktopCmsApi, getAccessToken } from "../api/adminClient";
import { useT } from "../i18n";
import { codeLabel } from "../utils/codeLabels";
import { serverDate, localDateIso } from "../utils/serverDate";
import { treasuryText } from "../utils/treasuryText";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

function todayIso(): string { return localDateIso(); }
function monthStartIso(): string { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; }

const SOURCES = new Set(["manual", "pos_cash_in", "pos_cash_out", "cod_delivery", "supplier_payment", "expense", "purchase_order"]);

export const TreasuryReportPage: React.FC = () => {
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
      setData(await DesktopCmsApi.getTreasuryReport(f, tDate));
    } catch (e: any) {
      setError(e?.userMessage || t("treasury_report.load_error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(from, to); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const downloadCsv = async () => {
    try {
      const url = DesktopCmsApi.treasuryReportCsvUrl(from, to);
      const tok = getAccessToken();
      const resp = await fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} });
      if (!resp.ok) throw new Error();
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `treasury_${from}_${to}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError(t("treasury_report.download_error"));
    }
  };

  const applyPreset = (p: "7d" | "month" | "30d" | "year") => {
    const today = todayIso();
    let f = today;
    if (p === "7d") { const d = new Date(); d.setDate(d.getDate() - 6); f = localDateIso(d); }
    if (p === "month") f = monthStartIso();
    if (p === "30d") { const d = new Date(); d.setDate(d.getDate() - 29); f = localDateIso(d); }
    if (p === "year") f = `${new Date().getFullYear()}-01-01`;
    setFrom(f); setTo(today); load(f, today);
  };

  const accountIcon = (acc: string) => (acc === "bank_account" ? Building2 : Banknote);
  const accountLabel = (acc: string) => (acc === "bank_account" ? t("treasury_report.acc_bank") : acc === "cash_box" ? t("treasury_report.acc_cash") : acc);
  const sourceLabel = (s: string) => (SOURCES.has(s) ? t(`misc.src_${s}`) : codeLabel(s));

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <Landmark className="w-5 h-5" /> {t("treasury_report.title")}
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("treasury_report.from")}</span>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("treasury_report.to")}</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <button type="button" onClick={() => load(from, to)} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {t("treasury_report.btn_generate")}
          </button>
          <button type="button" onClick={downloadCsv} disabled={!data} className="h-12 px-5 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-40">
            <Download className="w-4 h-4" /> {t("treasury_report.btn_csv")}
          </button>
          <div className="flex gap-1 ml-auto flex-wrap">
            {[
              ["7d", t("treasury_report.preset_7d")],
              ["month", t("treasury_report.preset_month")],
              ["30d", t("treasury_report.preset_30d")],
              ["year", t("treasury_report.preset_year")],
            ].map(([p, lbl]) => (
              <button key={p} type="button" onClick={() => applyPreset(p as any)} className="h-10 px-3 rounded-xl border-2 border-gray-200 text-xs font-bold active:scale-95">{lbl}</button>
            ))}
          </div>
        </div>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("treasury_report.loading")}
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile icon={ArrowUp} label={t("treasury_report.tile_inflow")} value={fmt(data.totals.inflow_dzd)} tone="green" />
            <Tile icon={ArrowDown} label={t("treasury_report.tile_outflow")} value={fmt(data.totals.outflow_dzd)} tone="red" />
            <Tile icon={Wallet} label={t("treasury_report.tile_net_flow")} value={fmt(data.totals.net_dzd)} tone={data.totals.net_dzd >= 0 ? "green" : "red"} accent />
            <Tile icon={Landmark} label={t("treasury_report.tile_count")} value={String(data.totals.count)} tone="gold" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-2">{t("treasury_report.by_account_title")}</h4>
              <div className="space-y-2">
                {data.by_account.length === 0 && <div className="text-gray-400">{t("treasury_report.no_flows")}</div>}
                {data.by_account.map((a: any) => {
                  const Icon = accountIcon(a.account_type);
                  return (
                    <div key={a.account_type} className="p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                      <div className="flex items-center gap-2 font-bold text-[#063D2E] mb-1">
                        <Icon className="w-4 h-4" /> {accountLabel(a.account_type)}
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
                        <div><div className="text-gray-400 font-bold uppercase">{t("treasury_report.sub_inflow")}</div><div className="font-mono text-emerald-600 font-bold">{fmt(a.inflow_dzd)}</div></div>
                        <div><div className="text-gray-400 font-bold uppercase">{t("treasury_report.sub_outflow")}</div><div className="font-mono text-red-600 font-bold">{fmt(a.outflow_dzd)}</div></div>
                        <div><div className="text-gray-400 font-bold uppercase">{t("treasury_report.sub_net")}</div><div className={`font-mono font-bold ${a.net_dzd >= 0 ? "text-[#063D2E]" : "text-red-600"}`}>{fmt(a.net_dzd)}</div></div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <h4 className="font-bold text-[#063D2E] mt-4 mb-2">{t("treasury_report.by_source_title")}</h4>
              <div className="space-y-1">
                {data.by_source.length === 0 && <div className="text-gray-400">{t("treasury_report.no_sources")}</div>}
                {data.by_source.map((s: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0 text-[11px]">
                    <span>
                      {sourceLabel(s.source_type)} <span className="text-gray-400">· {codeLabel(s.movement_type)} · {accountLabel(s.account_type)}</span>
                    </span>
                    <span className="font-mono font-bold">{fmt(s.total)} <span className="text-gray-400 text-[10px]">({s.c})</span></span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 bg-[#063D2E] text-[#E8D4A5] font-bold">{t("treasury_report.movements_title", { count: data.items.length })}</div>
              <div className="max-h-[55vh] overflow-auto">
                <table className="w-full text-left">
                  <thead className="bg-[#FCFBF8] text-[11px] uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">{t("treasury_report.th_date")}</th>
                      <th className="px-3 py-2">{t("treasury_report.th_desc")}</th>
                      <th className="px-3 py-2 text-right">{t("treasury_report.th_amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.length === 0 && <tr><td colSpan={3} className="px-3 py-6 text-center text-gray-400">{t("treasury_report.no_movements")}</td></tr>}
                    {data.items.map((it: any) => {
                      const outgoing = it.movement_type === "outflow" || it.movement_type === "withdrawal";
                      return (
                        <tr key={it.id} className="border-t border-gray-100">
                          <td className="px-3 py-2 font-mono text-[10px] whitespace-nowrap">{serverDate(it.created_at).toLocaleString("fr-FR")}</td>
                          <td className="px-3 py-2">
                            <div className="truncate">{treasuryText(it.description)}</div>
                            <div className="text-gray-400 text-[10px]">{accountLabel(it.account_type)} · {sourceLabel(it.source_type)}</div>
                          </td>
                          <td className={`px-3 py-2 text-right font-mono font-bold ${outgoing ? "text-red-600" : "text-emerald-600"}`}>
                            {outgoing ? "−" : "+"}{fmt(it.amount_dzd)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

const Tile: React.FC<{ icon: any; label: string; value: string; tone: "red" | "amber" | "gold" | "green"; accent?: boolean }> = ({ icon: Icon, label, value, tone, accent }) => {
  const tones: Record<string, string> = {
    red: "border-red-200 bg-red-50 text-red-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    gold: "border-[#D4AF62]/40 bg-[#FCFBF8] text-[#7a5c16]",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className={`p-4 rounded-2xl border-2 ${tones[tone]} ${accent ? "ring-2 ring-[#D4AF62]/40" : ""}`}>
      <div className="flex items-center gap-2 opacity-70 mb-1">
        <Icon className="w-4 h-4" /> <span className="text-[11px] font-bold uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-xl font-extrabold font-mono tabular-nums">{value}</div>
    </div>
  );
};
