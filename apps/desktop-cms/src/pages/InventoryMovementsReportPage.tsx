import React, { useEffect, useState, useCallback } from "react";
import { Boxes, Download, RefreshCw, AlertTriangle, ArrowUp, ArrowDown, CalendarRange } from "lucide-react";
import { DesktopCmsApi, getAccessToken } from "../api/adminClient";

function todayIso(): string { return new Date().toISOString().slice(0, 10); }
function monthStartIso(): string { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; }

const REASON_LABEL: Record<string, string> = {
  order_reserved: "Commande en ligne",
  order_confirmed: "Commande confirmée",
  order_cancelled: "Commande annulée",
  order_returned: "Commande retournée",
  pos_sale: "Vente magasin",
  pos_sale_offline: "Vente hors-ligne synchronisée",
  pos_refund: "Remboursement magasin",
  manual_in: "Ajustement manuel (+)",
  manual_out: "Ajustement manuel (−)",
  manual_adjustment: "Ajustement manuel",
  purchase_received: "Réception fournisseur",
  physical_count_reconcile: "Réconciliation inventaire",
  cms_bulk_update: "Mise à jour en masse",
  writeoff_damaged: "Démarque — endommagé",
  writeoff_lost: "Démarque — perte/vol",
  writeoff_return_to_supplier: "Retour fournisseur",
  writeoff_promotional_giveaway: "Cadeau/promo",
  writeoff_stocktake_correction: "Correction d'inventaire",
};

export const InventoryMovementsReportPage: React.FC = () => {
  const [from, setFrom] = useState(monthStartIso());
  const [to, setTo] = useState(todayIso());
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: string, t: string) => {
    setLoading(true);
    setError(null);
    try {
      setData(await DesktopCmsApi.getInventoryMovementsReport(f, t));
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(from, to); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const downloadCsv = async () => {
    try {
      const url = DesktopCmsApi.inventoryMovementsCsvUrl(from, to);
      const tok = getAccessToken();
      const resp = await fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} });
      if (!resp.ok) throw new Error();
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `inventory_${from}_${to}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError("Téléchargement CSV échoué");
    }
  };

  const applyPreset = (preset: "7d" | "month" | "30d" | "year") => {
    const t = todayIso();
    let f = t;
    if (preset === "7d") { const d = new Date(); d.setDate(d.getDate() - 6); f = d.toISOString().slice(0, 10); }
    if (preset === "month") f = monthStartIso();
    if (preset === "30d") { const d = new Date(); d.setDate(d.getDate() - 29); f = d.toISOString().slice(0, 10); }
    if (preset === "year") f = `${new Date().getFullYear()}-01-01`;
    setFrom(f); setTo(t); load(f, t);
  };

  const label = (reason: string) => REASON_LABEL[reason] || reason;

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <Boxes className="w-5 h-5" /> Rapport des mouvements de stock
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
            <Tile icon={ArrowUp} label="Entrées" value={String(data.totals.units_in)} tone="green" />
            <Tile icon={ArrowDown} label="Sorties" value={String(data.totals.units_out)} tone="red" />
            <Tile icon={Boxes} label="Variation nette" value={data.totals.net_change >= 0 ? `+${data.totals.net_change}` : String(data.totals.net_change)} tone={data.totals.net_change >= 0 ? "green" : "red"} />
            <Tile icon={CalendarRange} label="Écritures" value={String(data.totals.count)} tone="gold" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-2">Par motif</h4>
              <div className="space-y-1">
                {data.by_reason.length === 0 && <div className="text-gray-400">Aucun mouvement.</div>}
                {data.by_reason.map((br: any) => (
                  <div key={br.reason} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                    <span className="truncate pr-2">{label(br.reason)}<span className="text-gray-400 font-mono text-[10px] ml-2">{br.reason}</span></span>
                    <div className="text-right">
                      <div className={`font-mono font-bold ${br.net_change >= 0 ? "text-emerald-600" : "text-red-600"}`}>{br.net_change >= 0 ? `+${br.net_change}` : br.net_change}</div>
                      <div className="text-[10px] text-gray-400">{br.count} écriture(s) · {br.gross_units} unités</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 bg-[#063D2E] text-[#E8D4A5] font-bold">Écritures ({data.items.length})</div>
              <div className="max-h-[50vh] overflow-auto">
                <table className="w-full text-left">
                  <thead className="bg-[#FCFBF8] text-[11px] uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Variante</th>
                      <th className="px-3 py-2">Motif</th>
                      <th className="px-3 py-2 text-right">Δ</th>
                      <th className="px-3 py-2 text-right">Nouveau</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Aucune écriture.</td></tr>}
                    {data.items.map((it: any) => (
                      <tr key={it.id} className="border-t border-gray-100">
                        <td className="px-3 py-2 font-mono text-[10px] whitespace-nowrap">{new Date(it.created_at).toLocaleString("fr-DZ")}</td>
                        <td className="px-3 py-2">
                          <div className="truncate font-bold">{it.product_name}</div>
                          <div className="text-gray-400 font-mono text-[10px]">{it.sku}</div>
                        </td>
                        <td className="px-3 py-2 text-[11px]">{label(it.reason)}</td>
                        <td className={`px-3 py-2 text-right font-mono font-bold ${it.change_qty >= 0 ? "text-emerald-600" : "text-red-600"}`}>{it.change_qty >= 0 ? `+${it.change_qty}` : it.change_qty}</td>
                        <td className="px-3 py-2 text-right font-mono">{it.new_qty}</td>
                      </tr>
                    ))}
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

const Tile: React.FC<{ icon: any; label: string; value: string; tone: "red" | "amber" | "gold" | "green" }> = ({ icon: Icon, label, value, tone }) => {
  const tones: Record<string, string> = {
    red: "border-red-200 bg-red-50 text-red-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    gold: "border-[#D4AF62]/40 bg-[#FCFBF8] text-[#7a5c16]",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className={`p-4 rounded-2xl border-2 ${tones[tone]}`}>
      <div className="flex items-center gap-2 opacity-70 mb-1">
        <Icon className="w-4 h-4" /> <span className="text-[11px] font-bold uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-xl font-extrabold font-mono tabular-nums">{value}</div>
    </div>
  );
};
