import { ScanLine } from "lucide-react";
import { useT } from "../i18n";
import { movementReasonLabel } from "../utils/movementReasons";

export interface WriteOffTarget {
  variantId: number;
  sku: string;
  productName: string;
  variantTitle: string;
  currentStock: number;
}

/** The Stock screen: stock per product/variant and the latest movements.
 *  Data and actions come from App (shared with the catalogue screens). */
export interface InventoryPageProps {
  products: any[];
  movements: any[];
  onAdjustStock: (variantId: number, delta: number) => void;
  onPrintLabel: (variantId: number) => void;
  onWriteOff: (target: WriteOffTarget) => void;
}

export function InventoryPage({ products, movements, onAdjustStock, onPrintLabel, onWriteOff }: InventoryPageProps) {
  const t = useT();
  const handleAdjustStock = onAdjustStock;
  const setBarcodeVariantId = onPrintLabel;
  const setWriteOffTarget = onWriteOff;

  return (
    <div className="space-y-6 text-xs">
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("sidebar.inventory")}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {products.flatMap((p) =>
            (p.variants || []).map((v: any) => (
              <div key={v.id} className="p-3 rounded-xl border flex items-center justify-between">
                <div>
                  <div className="font-bold text-[#063D2E]">{p.name_fr} — {v.title}</div>
                  <div className="font-mono text-gray-500">SKU: {v.sku} • {t("stock_writeoff.current_stock_lbl")}: <strong>{v.stock_qty}</strong></div>
                  <div className="font-mono text-gray-400 text-[11px]">
                    {v.barcode ? `⌗ ${v.barcode}` : "⌗ —"}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button type="button" aria-label="Retirer une unité" disabled={Number(v.stock_qty) <= 0} title={Number(v.stock_qty) <= 0 ? "Stock déjà à 0" : undefined} onClick={() => handleAdjustStock(v.id, -1)} className="px-2.5 py-1 rounded bg-gray-100 font-bold disabled:opacity-40">-1</button>
                  <button type="button" onClick={() => handleAdjustStock(v.id, 1)} className="px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 font-bold">+1</button>
                  <button type="button" onClick={() => handleAdjustStock(v.id, 5)} className="px-2.5 py-1 rounded bg-[#063D2E] text-[#D4AF62] font-bold">+5</button>
                  <button type="button" onClick={() => setBarcodeVariantId(v.id)} title="Code-barres & étiquette" className="px-2.5 py-1 rounded bg-[#D4AF62]/20 text-[#7a5c16] font-bold flex items-center gap-1">
                    <ScanLine className="w-3.5 h-3.5" /> {t("devices.label_printer")}
                  </button>
                  <button
                    type="button"
                    disabled={v.stock_qty <= 0}
                    onClick={() => setWriteOffTarget({ variantId: v.id, sku: v.sku, productName: p.name_fr, variantTitle: v.title, currentStock: v.stock_qty })}
                    title="Sortie de stock"
                    className="px-2.5 py-1 rounded bg-red-100 text-red-700 font-bold disabled:opacity-40"
                  >
                    {t("stock_writeoff.title")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("inventory_report.title")} ({movements.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#063D2E] text-[#E8D4A5]">
                <th className="p-2">ID</th>
                <th className="p-2">{t("low_stock.th_product")}</th>
                <th className="p-2">{t("inventory_count.th_gap")}</th>
                <th className="p-2">{t("inventory_report.th_before_after")}</th>
                <th className="p-2">{t("inventory_report.th_reason")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {movements.map((m) => (
                <tr key={m.id}>
                  <td className="p-2 font-mono">#{m.id}</td>
                  <td className="p-2 font-bold">{m.product_name} ({m.variant_title})</td>
                  <td className="p-2 font-extrabold">{m.change_qty > 0 ? `+${m.change_qty}` : m.change_qty}</td>
                  <td className="p-2 font-mono">{m.previous_qty} → {m.new_qty}</td>
                  <td className="p-2">{movementReasonLabel(m.reason)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
