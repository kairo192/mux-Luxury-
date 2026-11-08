import React, { useEffect, useState, useCallback } from "react";
import { X, RefreshCw, Printer, Trash2, Wand2, CheckCircle2, AlertTriangle } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { renderBarcodeSvg } from "../utils/barcode";

interface LabelData {
  store_name: string;
  product_name: string;
  variant_title: string;
  sku: string;
  barcode: string | null;
  symbology: "ean13" | "code128" | null;
  price_dzd: number;
  currency: string;
}

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

export const BarcodeLabelModal: React.FC<{
  variantId: number;
  onClose: () => void;
  onChanged?: () => void;
}> = ({ variantId, onClose, onChanged }) => {
  const [label, setLabel] = useState<LabelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [customCode, setCustomCode] = useState("");
  const [codeCheck, setCodeCheck] = useState<{ valid: boolean; symbology: string | null; reason: string | null } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.getVariantLabel(variantId);
      setLabel(d);
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, [variantId]);

  useEffect(() => {
    load();
  }, [load]);

  // Live-validate the custom barcode as the user types (debounced).
  useEffect(() => {
    const code = customCode.trim();
    if (!code) {
      setCodeCheck(null);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await DesktopCmsApi.validateBarcode(code);
        setCodeCheck(r);
      } catch {
        setCodeCheck(null);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [customCode]);

  const flash = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 3500);
  };

  const assign = async (code?: string) => {
    setBusy(true);
    setError(null);
    try {
      await DesktopCmsApi.assignVariantBarcode(variantId, code);
      await load();
      setCustomCode("");
      flash(code ? "Code-barres assigné" : "Code-barres interne généré");
      onChanged?.();
    } catch (e: any) {
      setError(e?.userMessage || "Assignation refusée");
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    setBusy(true);
    try {
      await DesktopCmsApi.clearVariantBarcode(variantId);
      await load();
      flash("Code-barres effacé");
      onChanged?.();
    } catch (e: any) {
      setError(e?.userMessage || "Suppression refusée");
    } finally {
      setBusy(false);
    }
  };

  const printLabel = () => {
    if (!label?.barcode) return;
    const svg = renderBarcodeSvg(label.barcode, label.symbology || undefined, { moduleWidth: 2, height: 56 });
    const w = window.open("", "_blank", "width=420,height=320");
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><title>Étiquette ${label.sku}</title>
      <style>
        @page { size: 50mm 30mm; margin: 2mm; }
        body { font-family: system-ui, sans-serif; margin: 0; padding: 6px; text-align: center; }
        .name { font-size: 11px; font-weight: 700; }
        .meta { font-size: 10px; color: #333; }
        .price { font-size: 14px; font-weight: 800; margin-top: 2px; }
        svg { margin-top: 4px; }
      </style></head><body>
      <div class="name">${label.store_name}</div>
      <div class="meta">${label.product_name} — ${label.variant_title}</div>
      <div class="meta">SKU: ${label.sku}</div>
      <div class="price">${fmt(label.price_dzd)}</div>
      ${svg}
      <script>window.onload=function(){window.print();setTimeout(function(){window.close();},300);};<\/script>
      </body></html>`);
    w.document.close();
  };

  const barcodeSvg = label?.barcode
    ? renderBarcodeSvg(label.barcode, label.symbology || undefined, { moduleWidth: 2, height: 60 })
    : null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="font-serif font-bold text-[#063D2E] text-lg">Code-barres & Étiquette</h3>
          <button type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 active:scale-95">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-5 space-y-4 text-sm">
          {error && (
            <div className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
            </div>
          )}
          {success && (
            <div className="p-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-10 text-gray-500">
              <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Chargement…
            </div>
          ) : label ? (
            <>
              {/* Label preview */}
              <div className="rounded-2xl border-2 border-dashed border-gray-200 p-4 text-center bg-[#FCFBF8]">
                <div className="font-bold text-[#063D2E]">{label.store_name}</div>
                <div className="text-gray-500">{label.product_name} — {label.variant_title}</div>
                <div className="text-gray-500 font-mono">SKU: {label.sku}</div>
                <div className="text-xl font-extrabold text-[#063D2E] mt-1">{fmt(label.price_dzd)}</div>
                <div className="mt-3 flex justify-center">
                  {barcodeSvg ? (
                    <div dangerouslySetInnerHTML={{ __html: barcodeSvg }} />
                  ) : (
                    <div className="text-gray-400 py-4">Aucun code-barres assigné</div>
                  )}
                </div>
                {label.barcode && (
                  <div className="text-xs text-gray-400 mt-1">
                    {label.symbology === "ean13" ? "EAN-13" : "Code 128"}
                    {label.barcode.startsWith("20") && label.symbology === "ean13" ? " · interne" : ""}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => assign()}
                  className="h-12 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 disabled:opacity-50 active:scale-95"
                >
                  <Wand2 className="w-5 h-5" /> Générer
                </button>
                <button
                  type="button"
                  disabled={busy || !label.barcode}
                  onClick={printLabel}
                  className="h-12 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
                >
                  <Printer className="w-5 h-5" /> Imprimer
                </button>
              </div>

              {/* Custom barcode */}
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Code-barres personnalisé</label>
                <div className="flex gap-2">
                  <input
                    value={customCode}
                    onChange={(e) => setCustomCode(e.target.value)}
                    placeholder="EAN-13 ou SKU (Code 128)"
                    className="flex-1 h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono focus:border-[#063D2E] outline-none"
                  />
                  <button
                    type="button"
                    disabled={busy || !customCode.trim() || (codeCheck !== null && !codeCheck.valid)}
                    onClick={() => assign(customCode.trim())}
                    className="h-12 px-4 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-40 active:scale-95"
                  >
                    Assigner
                  </button>
                </div>
                {codeCheck && (
                  <div className={`mt-1.5 text-xs font-bold ${codeCheck.valid ? "text-emerald-600" : "text-red-600"}`}>
                    {codeCheck.valid
                      ? `✓ Valide (${codeCheck.symbology === "ean13" ? "EAN-13" : codeCheck.symbology === "ean8" ? "EAN-8" : codeCheck.symbology === "upca" ? "UPC-A" : "Code 128"})`
                      : `✗ ${codeCheck.reason || "Code-barres invalide"}`}
                  </div>
                )}
              </div>

              {label.barcode && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={clear}
                  className="w-full h-11 rounded-2xl border-2 border-red-200 text-red-600 font-bold flex items-center justify-center gap-2 disabled:opacity-50 active:scale-95"
                >
                  <Trash2 className="w-4 h-4" /> Effacer le code-barres
                </button>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};
