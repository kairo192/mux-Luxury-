import React, { useEffect, useState } from "react";
import { X, AlertTriangle, CheckCircle2, PackageMinus } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

export const StockWriteOffModal: React.FC<{
  variantId: number;
  sku: string;
  productName: string;
  variantTitle: string;
  currentStock: number;
  onClose: () => void;
  onDone?: () => void;
}> = ({ variantId, sku, productName, variantTitle, currentStock, onClose, onDone }) => {
  const [reasons, setReasons] = useState<Array<{ code: string; label: string }>>([]);
  const [reason, setReason] = useState("damaged");
  const [qty, setQty] = useState("1");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    DesktopCmsApi.listWriteOffReasons().then((d) => setReasons(d.items || [])).catch(() => {});
  }, []);

  const submit = async () => {
    const n = parseInt(qty || "0", 10);
    if (isNaN(n) || n <= 0) return setError("Quantité invalide");
    if (n > currentStock) return setError(`Stock insuffisant (${currentStock} dispo)`);
    setBusy(true);
    setError(null);
    try {
      const r = await DesktopCmsApi.stockWriteOff(variantId, n, reason, notes.trim() || undefined);
      setDone(`Nouveau stock : ${r.new_qty}`);
      onDone?.();
      setTimeout(onClose, 1200);
    } catch (e: any) {
      setError(e?.userMessage || "Opération refusée");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="font-serif font-bold text-[#063D2E] text-lg flex items-center gap-2">
            <PackageMinus className="w-5 h-5" /> Sortie de stock
          </h3>
          <button type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="p-5 space-y-3 text-sm">
          <div className="p-3 rounded-2xl bg-[#FCFBF8] border border-gray-100">
            <div className="font-bold text-[#063D2E]">{productName}</div>
            <div className="text-gray-500 font-mono text-[11px]">{variantTitle} · {sku} · stock actuel <strong>{currentStock}</strong></div>
          </div>
          {error && <div className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</div>}
          {done && <div className="p-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> {done}</div>}

          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Motif</span>
            <select value={reason} onChange={(e) => setReason(e.target.value)} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white">
              {reasons.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Quantité</span>
            <input type="number" min={1} max={currentStock} value={qty} onChange={(e) => setQty(e.target.value)} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Note (optionnel)</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="w-full px-3 py-2 rounded-2xl border-2 border-gray-200" />
          </label>
          <button type="button" disabled={busy || currentStock === 0} onClick={submit} className="w-full h-14 rounded-2xl bg-red-600 text-white font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
            Confirmer la sortie
          </button>
        </div>
      </div>
    </div>
  );
};
