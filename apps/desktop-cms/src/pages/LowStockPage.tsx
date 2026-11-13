import React, { useEffect, useState, useCallback } from "react";
import { AlertTriangle, RefreshCw, PackageMinus, Wallet } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

interface LowStockItem {
  variant_id: number;
  product_id: number;
  product_name: string;
  variant_title: string;
  sku: string;
  stock_qty: number;
  low_stock_threshold: number;
  on_order_qty: number;
  velocity_30d: number;
  suggested_reorder_qty: number;
  unit_cost_dzd: number;
}

export const LowStockPage: React.FC = () => {
  const t = useT();
  const [data, setData] = useState<{ items: LowStockItem[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeOut, setIncludeOut] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await DesktopCmsApi.getLowStockReport(includeOut));
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || t("status.error"));
    } finally {
      setLoading(false);
    }
  }, [includeOut, t]);

  useEffect(() => {
    load();
  }, [load]);

  const items = data?.items || [];
  const summary = data?.summary || { out_of_stock_count: 0, low_stock_count: 0, total_suggested_reorder_value_dzd: 0 };

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <PackageMinus className="w-5 h-5" /> {t("low_stock.title")}
          </h3>
          <p className="text-gray-500 mt-1">{t("low_stock.subtitle")}</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-gray-600 font-bold">
            <input type="checkbox" checked={includeOut} onChange={(e) => setIncludeOut(e.target.checked)} className="w-5 h-5" />
            {t("low_stock.include_out")}
          </label>
          <button aria-label="Actualiser" type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
            <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tile icon={AlertTriangle} label={t("low_stock.tile_out")} value={String(summary.out_of_stock_count)} tone="red" />
        <Tile icon={PackageMinus} label={t("low_stock.tile_low")} value={String(summary.low_stock_count)} tone="amber" />
        <Tile icon={Wallet} label={t("low_stock.tile_suggested")} value={fmt(summary.total_suggested_reorder_value_dzd)} tone="gold" />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("status.loading")}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          {t("low_stock.empty")}
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3">{t("low_stock.th_product")}</th>
                <th className="px-4 py-3 text-right">{t("low_stock.th_stock")}</th>
                <th className="px-4 py-3 text-right">{t("low_stock.th_threshold")}</th>
                <th className="px-4 py-3 text-right">{t("low_stock.th_on_order")}</th>
                <th className="px-4 py-3 text-right hidden md:table-cell">{t("low_stock.th_velocity")}</th>
                <th className="px-4 py-3 text-right">{t("low_stock.th_suggested")}</th>
                <th className="px-4 py-3 text-right hidden md:table-cell">{t("low_stock.th_cost")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const out = it.stock_qty === 0;
                return (
                  <tr key={it.variant_id} className="border-t border-gray-100">
                    <td className="px-4 py-3">
                      <div className="font-bold text-[#063D2E]">{it.product_name}</div>
                      <div className="text-gray-500 font-mono text-[11px]">{it.variant_title} · {it.sku}</div>
                    </td>
                    <td className={`px-4 py-3 text-right font-mono font-bold ${out ? "text-red-600" : "text-amber-700"}`}>{it.stock_qty}</td>
                    <td className="px-4 py-3 text-right font-mono text-gray-500">{it.low_stock_threshold}</td>
                    <td className="px-4 py-3 text-right font-mono">{it.on_order_qty > 0 ? <span className="text-emerald-600 font-bold">+{it.on_order_qty}</span> : <span className="text-gray-400">—</span>}</td>
                    <td className="px-4 py-3 text-right font-mono hidden md:table-cell">{it.velocity_30d > 0 ? <span className="text-gray-700">{it.velocity_30d}</span> : <span className="text-gray-400">—</span>}</td>
                    <td className="px-4 py-3 text-right">
                      {it.suggested_reorder_qty > 0 ? (
                        <span className="inline-block font-mono font-extrabold bg-[#D4AF62]/20 text-[#7a5c16] px-2 py-0.5 rounded">+{it.suggested_reorder_qty}</span>
                      ) : (
                        <span className="text-gray-400 font-mono">0</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-500 hidden md:table-cell">
                      {it.suggested_reorder_qty > 0 ? fmt(it.suggested_reorder_qty * it.unit_cost_dzd) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] text-gray-400 text-center">
        {t("low_stock.formula_hint")}
      </p>
    </div>
  );
};

const Tile: React.FC<{ icon: any; label: string; value: string; tone: "red" | "amber" | "gold" }> = ({ icon: Icon, label, value, tone }) => {
  const tones: Record<string, string> = {
    red: "bg-red-50 border-red-200 text-red-700",
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    gold: "bg-[#FCFBF8] border-[#D4AF62]/40 text-[#7a5c16]",
  };
  return (
    <div className={`p-4 rounded-2xl border-2 ${tones[tone]}`}>
      <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide opacity-80">
        <Icon className="w-4 h-4" /> {label}
      </div>
      <div className="text-xl font-extrabold font-mono tabular-nums mt-1">{value}</div>
    </div>
  );
};
