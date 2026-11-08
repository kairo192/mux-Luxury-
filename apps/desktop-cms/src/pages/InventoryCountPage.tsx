import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  ClipboardList,
  ScanLine,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Ban,
  Check,
  X,
  History,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

interface Count {
  id: number;
  reference: string;
  name: string;
  status: "open" | "applied" | "cancelled";
  total_lines: number;
  total_variance_abs: number;
  opened_at: string;
  applied_at?: string | null;
  opened_by_name?: string | null;
  applied_by_name?: string | null;
  items?: CountLine[];
}
interface CountLine {
  id: number;
  variant_id: number;
  sku: string;
  variant_title: string;
  product_name: string;
  expected_qty: number;
  counted_qty: number;
  current_stock_qty: number;
  variance: number;
}

const BADGE: Record<string, string> = {
  open: "bg-emerald-100 text-emerald-700",
  applied: "bg-gray-200 text-gray-700",
  cancelled: "bg-red-100 text-red-700",
};
const LBL: Record<string, string> = { open: "Ouvert", applied: "Appliqué", cancelled: "Annulé" };

export const InventoryCountPage: React.FC<{ onInventoryUpdated?: () => void }> = ({ onInventoryUpdated }) => {
  const [list, setList] = useState<Count[]>([]);
  const [active, setActive] = useState<Count | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [scanCode, setScanCode] = useState("");
  const [qtyEdit, setQtyEdit] = useState<{ lineId: number; value: string } | null>(null);
  const scanRef = useRef<HTMLInputElement>(null);

  const flash = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 3500);
  };
  const flashError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listInventoryCounts(30);
      setList(d.items || []);
      // auto-pick the currently open one
      const open = (d.items || []).find((c: Count) => c.status === "open");
      if (open) {
        const full = await DesktopCmsApi.getInventoryCount(open.id);
        setActive(full);
      } else {
        setActive(null);
      }
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (active && active.status === "open") scanRef.current?.focus();
  }, [active?.id, active?.status]);

  const openNew = async () => {
    setBusy(true);
    try {
      const c = await DesktopCmsApi.openInventoryCount({ name: `Inventaire ${new Date().toLocaleDateString("fr-DZ")}` });
      setActive(c);
      flash(`Inventaire ${c.reference} ouvert`);
      load();
    } catch (e: any) {
      flashError(e?.userMessage || "Ouverture refusée");
    } finally {
      setBusy(false);
    }
  };

  const reloadActive = async () => {
    if (!active) return;
    try {
      setActive(await DesktopCmsApi.getInventoryCount(active.id));
    } catch {
      /* ignore */
    }
  };

  const handleScan = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!active || active.status !== "open") return;
    const code = scanCode.trim();
    if (!code) return;
    try {
      const look = await DesktopCmsApi.posLookup(code);
      if (look.match_type !== "variant") {
        flashError(`Aucune variante pour « ${code} »`);
        return;
      }
      const vid = look.variant.variant_id;
      const updated = await DesktopCmsApi.upsertInventoryCountLine(active.id, vid, 1);
      setActive(updated);
      setScanCode("");
      scanRef.current?.focus();
    } catch (e: any) {
      flashError(e?.userMessage || "Scan refusé");
    }
  };

  const saveQty = async (line: CountLine) => {
    if (!active || !qtyEdit) return;
    const n = parseInt(qtyEdit.value || "0", 10);
    if (isNaN(n) || n < 0) return flashError("Quantité invalide");
    const delta = n - line.counted_qty;
    if (delta === 0) {
      setQtyEdit(null);
      return;
    }
    try {
      const updated = await DesktopCmsApi.upsertInventoryCountLine(active.id, line.variant_id, delta);
      setActive(updated);
      setQtyEdit(null);
    } catch (e: any) {
      flashError(e?.userMessage || "Mise à jour refusée");
    }
  };

  const removeLine = async (line: CountLine) => {
    if (!active) return;
    try {
      const updated = await DesktopCmsApi.deleteInventoryCountLine(active.id, line.id);
      setActive(updated);
    } catch (e: any) {
      flashError(e?.userMessage || "Suppression refusée");
    }
  };

  const apply = async () => {
    if (!active) return;
    if (!window.confirm(`Appliquer l'inventaire ${active.reference} ?\nLe stock sera ajusté aux quantités comptées.`)) return;
    setBusy(true);
    try {
      const applied = await DesktopCmsApi.applyInventoryCount(active.id);
      setActive(applied);
      flash("Inventaire appliqué — écritures générées");
      onInventoryUpdated?.();
      load();
    } catch (e: any) {
      flashError(e?.userMessage || "Application refusée");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!active) return;
    if (!window.confirm(`Annuler l'inventaire ${active.reference} ? Les quantités comptées seront perdues.`)) return;
    try {
      const upd = await DesktopCmsApi.cancelInventoryCount(active.id);
      setActive(upd);
      flash("Inventaire annulé");
      load();
    } catch (e: any) {
      flashError(e?.userMessage || "Annulation refusée");
    }
  };

  return (
    <div className="space-y-4 text-sm">
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

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <ClipboardList className="w-5 h-5" /> Inventaire physique & réconciliation
          </h3>
          <p className="text-gray-500 mt-1">Scannez les unités réellement présentes ; le stock s'ajuste à l'application.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setShowHistory(true)} className="h-12 px-4 rounded-2xl border-2 border-gray-200 font-bold flex items-center gap-2 active:scale-95">
            <History className="w-5 h-5" /> Historique
          </button>
          {!active || active.status !== "open" ? (
            <button type="button" disabled={busy} onClick={openNew} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-50">
              <Plus className="w-5 h-5" /> Nouvel inventaire
            </button>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
        </div>
      ) : !active ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          Aucun inventaire ouvert. Cliquez sur « Nouvel inventaire » pour commencer.
        </div>
      ) : (
        <>
          <div className="bg-white p-4 rounded-3xl border border-gray-200 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-bold text-[#063D2E] text-lg flex items-center gap-2">
                {active.reference}
                <span className={`px-2 py-0.5 rounded-lg text-xs font-bold ${BADGE[active.status]}`}>{LBL[active.status]}</span>
              </div>
              <div className="text-gray-500 text-[11px]">{active.name} · ouvert le {new Date(active.opened_at).toLocaleString("fr-DZ")}{active.opened_by_name ? ` par ${active.opened_by_name}` : ""}</div>
            </div>
            <div className="flex gap-4 text-sm">
              <Stat label="Lignes" value={String(active.total_lines)} />
              <Stat label="Écart absolu" value={String(active.total_variance_abs)} warn={active.total_variance_abs > 0} />
            </div>
          </div>

          {active.status === "open" && (
            <form onSubmit={handleScan} className="bg-white p-4 rounded-3xl border border-[#D4AF62]/40">
              <label className="flex items-center gap-2 font-bold text-[#063D2E] mb-2">
                <ScanLine className="w-5 h-5" /> Scanner / saisir un SKU ou code-barres
              </label>
              <div className="flex gap-2">
                <input
                  ref={scanRef}
                  value={scanCode}
                  onChange={(e) => setScanCode(e.target.value)}
                  placeholder="Un scan = +1 à la variante…"
                  className="flex-1 h-14 px-4 rounded-2xl border-2 border-gray-200 font-mono text-lg focus:border-[#063D2E] outline-none"
                  autoFocus
                />
                <button type="submit" className="h-14 px-6 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold active:scale-95">+1</button>
              </div>
            </form>
          )}

          <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
                <tr>
                  <th className="px-4 py-3">Produit</th>
                  <th className="px-4 py-3 text-right">Attendu</th>
                  <th className="px-4 py-3 text-right">Compté</th>
                  <th className="px-4 py-3 text-right">Écart</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {(active.items || []).length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-10 text-center text-gray-400">Aucune ligne. Scannez un produit pour l'ajouter.</td></tr>
                )}
                {(active.items || []).map((l) => {
                  const edit = qtyEdit?.lineId === l.id;
                  const vClass = l.variance === 0 ? "text-gray-500" : l.variance > 0 ? "text-emerald-600" : "text-red-600";
                  return (
                    <tr key={l.id} className="border-t border-gray-100">
                      <td className="px-4 py-3">
                        <div className="font-bold text-[#063D2E]">{l.product_name}</div>
                        <div className="text-gray-500 font-mono text-[11px]">{l.variant_title} · {l.sku}</div>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{l.expected_qty}</td>
                      <td className="px-4 py-3 text-right">
                        {edit ? (
                          <input
                            type="number"
                            autoFocus
                            value={qtyEdit!.value}
                            onChange={(e) => setQtyEdit({ lineId: l.id, value: e.target.value })}
                            onBlur={() => saveQty(l)}
                            onKeyDown={(e) => { if (e.key === "Enter") saveQty(l); if (e.key === "Escape") setQtyEdit(null); }}
                            className="w-20 h-10 px-2 rounded-xl border-2 border-[#063D2E] font-mono text-right"
                          />
                        ) : (
                          <button type="button" disabled={active.status !== "open"} onClick={() => setQtyEdit({ lineId: l.id, value: String(l.counted_qty) })} className="font-mono font-bold disabled:cursor-default">
                            {l.counted_qty}
                          </button>
                        )}
                      </td>
                      <td className={`px-4 py-3 text-right font-mono font-bold ${vClass}`}>{l.variance > 0 ? `+${l.variance}` : l.variance}</td>
                      <td className="px-4 py-3 text-right">
                        {active.status === "open" && (
                          <button type="button" onClick={() => removeLine(l)} className="h-9 w-9 rounded-xl border-2 border-red-200 inline-flex items-center justify-center text-red-500 active:scale-95">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {active.status === "open" && (active.total_lines || 0) > 0 && (
            <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={apply} className="flex-1 h-14 rounded-2xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold text-base flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50">
                <Check className="w-5 h-5" /> Appliquer l'inventaire
              </button>
              <button type="button" onClick={cancel} className="h-14 px-5 rounded-2xl border-2 border-red-200 text-red-600 font-bold flex items-center gap-2 active:scale-95">
                <Ban className="w-5 h-5" /> Annuler
              </button>
              <button type="button" onClick={reloadActive} className="h-14 w-14 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          )}
        </>
      )}

      {/* HISTORY SHEET */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4" onClick={() => setShowHistory(false)}>
          <div className="bg-white rounded-t-3xl sm:rounded-3xl p-5 w-full sm:max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">Historique des inventaires</h3>
              <button type="button" onClick={() => setShowHistory(false)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="space-y-2">
              {list.length === 0 && <div className="text-gray-400 py-6 text-center">Aucun inventaire.</div>}
              {list.map((c) => (
                <button key={c.id} type="button" onClick={async () => { setActive(await DesktopCmsApi.getInventoryCount(c.id)); setShowHistory(false); }}
                  className="w-full text-left p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8] hover:border-[#063D2E] active:scale-[0.99]">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#063D2E]">{c.reference}</span>
                    <span className={`px-2 py-0.5 rounded-lg text-xs font-bold ${BADGE[c.status]}`}>{LBL[c.status]}</span>
                  </div>
                  <div className="text-gray-500 text-[11px] mt-1">{c.name} · {c.total_lines} ligne(s) · écart {c.total_variance_abs}</div>
                  <div className="text-gray-400 text-[11px]">{new Date(c.opened_at).toLocaleString("fr-DZ")}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string; warn?: boolean }> = ({ label, value, warn }) => (
  <div className="text-center">
    <div className="text-[10px] uppercase tracking-wide text-gray-400 font-bold">{label}</div>
    <div className={`font-mono font-bold text-lg ${warn ? "text-amber-600" : "text-[#063D2E]"}`}>{value}</div>
  </div>
);
