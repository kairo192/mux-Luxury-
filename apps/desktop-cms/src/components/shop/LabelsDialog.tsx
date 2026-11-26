import { useMemo, useState } from "react";
import { X, Printer, Barcode } from "lucide-react";
import { DesktopCmsApi } from "../../api/adminClient";
import { useEscapeToClose } from "../../utils/useEscapeToClose";
import { renderBarcodeSvg } from "../../utils/barcode";
import { labelPrice, labelsCount, printLabelItems, type LabelItem } from "../../utils/labelPrint";
import { isLabelPrinterConfigured, isTauriRuntime } from "../../utils/posHardware";
import { pickLang, tr } from "../../i18n/translations";
import { SINGLE, variantName, type StoreItem } from "./QuickAddPanel";

/** Labels of an article: which colours / sizes, how many of each (by default
 *  one per piece in stock), printed on the label printer or the print dialog. */
export function LabelsDialog({ item, storeName, only, onClose, onChanged, onDone }: {
  item: StoreItem;
  storeName: string;
  only?: number | null;
  onClose: () => void;
  onChanged: (item: StoreItem) => void;
  onDone: (message: string, ok: boolean) => void;
}) {
  useEscapeToClose(onClose, true);
  const variants = item.variants.filter((v) => v.is_active);
  const [copies, setCopies] = useState<Record<number, string>>(() =>
    Object.fromEntries(variants.map((v) => [v.id, String(only && only !== v.id ? 0 : Math.max(v.stock_qty, only === v.id ? 1 : 0))])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toPrinter = isTauriRuntime() && isLabelPrinterConfigured();

  const items: LabelItem[] = useMemo(() => variants.filter((v) => v.barcode).map((v) => ({
    store_name: storeName,
    product_name: item.name_fr,
    variant_title: v.title === SINGLE ? "" : v.title,
    sku: v.sku,
    price_dzd: v.price_dzd,
    barcode: v.barcode!,
    symbology: v.symbology,
    copies: parseInt(copies[v.id] || "0", 10) || 0,
  })), [variants, copies, storeName, item.name_fr]);
  const total = labelsCount(items);
  const sample = items.find((i) => i.copies > 0) || items[0];
  const missing = variants.filter((v) => !v.barcode).length;

  const generate = async () => {
    setBusy(true);
    try {
      const r = await DesktopCmsApi.generateStoreBarcodes(item.id);
      onChanged(r.item);
    } catch (e: any) {
      setError(e?.userMessage || tr("status.error"));
    } finally {
      setBusy(false);
    }
  };

  const print = async () => {
    setBusy(true);
    setError(null);
    const r = await printLabelItems(items);
    setBusy(false);
    if (!r.ok) return setError(r.error || tr("hw.label_error"));
    onDone(r.via === "printer" ? tr("shop.printed_n", { n: total }) : tr("shop.print_dialog", { n: total }), true);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="labels-title" className="bg-white rounded-3xl w-full max-w-2xl max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 id="labels-title" className="font-serif font-bold text-[#063D2E] text-lg flex items-center gap-2"><Barcode className="w-5 h-5" /> {tr("shop.labels_for", { name: pickLang(item, "name") })}</h3>
          <button aria-label={tr("ui.close")} type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95"><X className="w-6 h-6" /></button>
        </div>
        <div className="p-5 space-y-4 text-sm">
          {error && <div role="alert" className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold">{error}</div>}
          {missing > 0 && (
            <div className="p-3 rounded-2xl bg-amber-50 border-2 border-amber-200 text-amber-900 flex items-center justify-between gap-3">
              <span>{tr("shop.missing_n", { n: missing })}</span>
              <button type="button" disabled={busy} onClick={generate} className="h-10 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold shrink-0 active:scale-95">{tr("shop.generate")}</button>
            </div>
          )}
          <table className="w-full">
            <thead className="text-[11px] uppercase text-gray-500"><tr>
              <th className="text-start py-1">{tr("shop.th_variant")}</th><th className="text-start py-1">{tr("shop.th_barcode")}</th>
              <th className="text-start py-1">{tr("shop.th_stock")}</th><th className="text-start py-1 w-28">{tr("shop.th_labels")}</th>
            </tr></thead>
            <tbody>
              {variants.map((v) => (
                <tr key={v.id} className="border-t border-gray-100">
                  <td className="py-2 font-bold text-[#063D2E]">{variantName(v.title)}</td>
                  <td className="py-2 font-mono text-xs">{v.barcode || <span className="text-amber-700">{tr("shop.no_barcode")}</span>}</td>
                  <td className="py-2 font-mono">{v.stock_qty}</td>
                  <td className="py-2">
                    <input aria-label={tr("shop.labels_of", { title: v.title })} disabled={!v.barcode} inputMode="numeric" value={copies[v.id] ?? "0"}
                      onChange={(e) => setCopies({ ...copies, [v.id]: e.target.value.replace(/[^\d]/g, "").slice(0, 3) })}
                      className="w-20 h-10 px-2 rounded-xl border-2 border-gray-200 font-mono disabled:opacity-40" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {sample && (
            <div className="rounded-2xl border-2 border-dashed border-gray-200 p-3 text-center bg-[#FCFBF8]" aria-label={tr("shop.preview")}>
              <div className="text-[11px] font-bold">{sample.store_name}</div>
              <div className="text-[11px] text-gray-600">{sample.product_name}{sample.variant_title ? ` — ${sample.variant_title}` : ""}</div>
              <div className="font-extrabold text-[#063D2E]" dir="ltr">{labelPrice(sample.price_dzd)}</div>
              <div className="flex justify-center mt-1" dangerouslySetInnerHTML={{ __html: renderBarcodeSvg(sample.barcode, (sample.symbology as any) || undefined, { moduleWidth: 2, height: 46 }) }} />
            </div>
          )}

          <p className="text-[11px] text-gray-500">{toPrinter ? tr("shop.to_label_printer") : tr("shop.to_dialog")}</p>
          <button type="button" disabled={busy || total === 0} onClick={print} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base flex items-center justify-center gap-2 disabled:opacity-40 active:scale-[0.99]">
            <Printer className="w-5 h-5" /> {tr("shop.print_n", { n: total })}
          </button>
        </div>
      </div>
    </div>
  );
}
