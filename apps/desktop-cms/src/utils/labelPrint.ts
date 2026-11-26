// Print barcode labels for several articles at once: on the label printer of
// this PC when one is set up (desktop app), otherwise through the system print
// dialog (any printer, or "Save as PDF").
import { isLabelPrinterConfigured, isTauriRuntime, loadLabelPrinterSettings, printLabels, type LabelPayload } from "./posHardware";
import { openSystemPrint, renderLabelsHtml } from "./systemPrint";
import { renderBarcodeSvg } from "./barcode";
import { tr } from "../i18n/translations";

export interface LabelItem {
  store_name: string;
  product_name: string;
  variant_title?: string;
  sku: string;
  price_dzd: number;
  barcode: string;
  symbology?: string | null;
  copies: number;
}

/** "12 500 DA" with plain spaces: label printers have no narrow space. */
export function labelPrice(dzd: number): string {
  return `${String(Math.round(dzd || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} DA`;
}

const MAX_COPIES = 100;

export function labelsCount(items: LabelItem[]): number {
  return items.reduce((n, i) => n + Math.max(0, Math.min(MAX_COPIES, Math.floor(i.copies || 0))), 0);
}

export async function printLabelItems(items: LabelItem[]): Promise<{ ok: boolean; error?: string; via: "printer" | "dialog" }> {
  const list = items
    .filter((i) => i.barcode && i.copies > 0)
    .map((i) => ({ ...i, copies: Math.min(MAX_COPIES, Math.floor(i.copies)) }));
  if (!list.length) return { ok: false, error: tr("hw.no_labels"), via: "dialog" };
  if (isTauriRuntime() && isLabelPrinterConfigured()) {
    const payloads: LabelPayload[] = list.map((i) => ({
      header: i.store_name,
      product_name: i.product_name,
      variant_title: i.variant_title || "",
      sku: i.sku,
      price_text: labelPrice(i.price_dzd),
      barcode_value: i.barcode,
      barcode_kind: i.symbology === "ean13" ? "ean13" : "code128",
      copies: i.copies,
    }));
    const r = await printLabels(loadLabelPrinterSettings(), payloads);
    return { ...r, via: "printer" };
  }
  const settings = loadLabelPrinterSettings();
  const html = list.map((i) => renderLabelsHtml([{
    header: i.store_name,
    product_name: i.product_name,
    variant_title: i.variant_title,
    sku: i.sku,
    price_text: labelPrice(i.price_dzd),
    barcode_svg: renderBarcodeSvg(i.barcode, (i.symbology as any) || undefined, { moduleWidth: 2, height: 50 }),
  }], i.copies)).join("");
  const r = openSystemPrint({
    title: tr("shop.labels_title"),
    paper: { kind: "mm", width: Number(settings.width_mm) || 50, height: Number(settings.height_mm) || 30 },
    marginMm: 1,
    html,
  });
  return { ...r, via: "dialog" };
}
