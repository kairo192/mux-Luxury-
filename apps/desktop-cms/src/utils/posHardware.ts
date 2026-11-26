// ============================================================================
import { serverDate } from "./serverDate";
import { tr } from "../i18n/translations";
// POS hardware bridge — thin typed wrapper around the Tauri 2 invoke commands
// defined in `apps/desktop-cms/src-tauri/src/pos_hardware/`.
//
// The three real commands:
//   pos_list_printers()               → PrinterInfo[]
//   pos_print_receipt(opts, lines)    → void
//   pos_open_cash_drawer(opts)        → void
//   pos_test_print(opts)              → void (short diagnostic slip)
//
// Printer selection is persisted in localStorage under POS_HW_SETTINGS_KEY.
// This module never throws — every action returns an `OkResult | ErrResult`
// so the caller (POS screen) can show a friendly toast without wrapping each
// call in a try/catch.
// ============================================================================

export const POS_HW_SETTINGS_KEY = "luxe_pos_hardware_settings";
export const POS_LABEL_SETTINGS_KEY = "luxe_pos_label_printer_settings";

export interface PrinterInfo {
  name: string;
  system_name: string;
  is_default: boolean;
  state: string;
}

export interface PrinterTarget {
  printer_name?: string | null;
  device_path?: string | null;
  /** Network printer (raw printing, port 9100 by default). */
  host?: string | null;
  port?: number | null;
  line_width?: number;  // 32 (58mm) or 42 (80mm) typical
  drawer_pin?: 2 | 5;
}

export interface ReceiptOptions extends PrinterTarget {
  open_drawer?: boolean;
  cut?: boolean;
  feed_before_cut?: number;
}

export interface ReceiptLine {
  text?: string;
  align?: "left" | "center" | "right";
  bold?: boolean;
  double_height?: boolean;
  double_width?: boolean;
  underline?: boolean;
  feed?: number;
  left?: string;
  right?: string;
  rule?: boolean;
  barcode?: string;
}

// A plain record, not a discriminated union — the project's tsconfig runs
// with strict: false, which doesn't narrow unions through `if (r.ok)`. An
// optional `error` on every result sidesteps that.
export interface HardwareResult {
  ok: boolean;
  error?: string;
}

// -------------------------------------------------- Tauri bridge --------

export function getTauriInvoke(): ((cmd: string, args?: Record<string, unknown>) => Promise<any>) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  if (w.__TAURI_INTERNALS__ && typeof w.__TAURI_INTERNALS__.invoke === "function") {
    return w.__TAURI_INTERNALS__.invoke.bind(w.__TAURI_INTERNALS__);
  }
  if (w.__TAURI__ && w.__TAURI__.core && typeof w.__TAURI__.core.invoke === "function") {
    return w.__TAURI__.core.invoke.bind(w.__TAURI__.core);
  }
  return null;
}

export function isTauriRuntime(): boolean {
  return getTauriInvoke() !== null;
}

// -------------------------------------------------- Settings ------------

export function loadHardwareSettings(): PrinterTarget {
  try {
    const raw = localStorage.getItem(POS_HW_SETTINGS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as PrinterTarget;
    return {
      printer_name: parsed.printer_name ?? null,
      device_path: parsed.device_path ?? null,
      line_width: parsed.line_width ?? 32,
      drawer_pin: (parsed.drawer_pin === 5 ? 5 : 2) as 2 | 5,
    };
  } catch {
    return {};
  }
}

export function saveHardwareSettings(s: PrinterTarget): void {
  try {
    localStorage.setItem(POS_HW_SETTINGS_KEY, JSON.stringify({
      printer_name: s.printer_name ?? null,
      device_path: s.device_path ?? null,
      line_width: s.line_width ?? 32,
      drawer_pin: s.drawer_pin ?? 2,
    }));
  } catch {
    // quota / private mode: harmless — the setting will reset next launch
  }
}

export function isHardwareConfigured(s?: PrinterTarget): boolean {
  const cfg = s ?? loadHardwareSettings();
  return Boolean((cfg.printer_name && cfg.printer_name.trim()) || (cfg.device_path && cfg.device_path.trim()));
}

// -------------------------------------------------- Commands ------------

export async function listPrinters(): Promise<PrinterInfo[]> {
  const invoke = getTauriInvoke();
  if (!invoke) return [];
  try {
    return (await invoke("pos_list_printers")) as PrinterInfo[];
  } catch {
    return [];
  }
}

export async function printReceipt(
  opts: ReceiptOptions,
  lines: ReceiptLine[],
): Promise<HardwareResult> {
  const invoke = getTauriInvoke();
  if (!invoke) return { ok: false, error: tr("hw.no_tauri_print") };
  try {
    await invoke("pos_print_receipt", { opts, lines });
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("hw.printer_error")) };
  }
}

export async function openCashDrawer(opts: PrinterTarget = loadHardwareSettings()): Promise<HardwareResult> {
  const invoke = getTauriInvoke();
  if (!invoke) return { ok: false, error: tr("hw.no_tauri_drawer") };
  try {
    await invoke("pos_open_cash_drawer", { opts });
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("hw.drawer_failed")) };
  }
}

export async function testPrint(opts: PrinterTarget = loadHardwareSettings()): Promise<HardwareResult> {
  const invoke = getTauriInvoke();
  if (!invoke) return { ok: false, error: tr("hw.no_tauri_test") };
  try {
    await invoke("pos_test_print", { opts });
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("hw.test_failed")) };
  }
}

// -------------------------------------------------- Receipt builder -----

/** Shape the backend returns for a POS sale (subset used here). */
export interface PosSalePayload {
  sale_reference?: string;
  created_at?: string;
  sale_type?: string;
  subtotal_dzd?: number;
  discount_dzd?: number;
  tax_dzd?: number;
  total_dzd?: number;
  items?: Array<{
    product_name?: string;
    variant_title?: string;
    quantity?: number;
    unit_price_dzd?: number;
    line_total_dzd?: number;
  }>;
  payments?: Array<{
    method?: string;
    amount_dzd?: number;
    change_dzd?: number;
  }>;
  customer?: { full_name?: string; phone?: string } | null;
  boutique_info?: {
    name?: string;
    tax_id?: string;
    address?: string;
    phone?: string;
  } | null;
  offline?: boolean;
}

const fmtDzd = (n: number | undefined | null) => {
  const v = Math.round(Number(n ?? 0));
  return `${v.toLocaleString("fr-FR")} DA`;
};

/** Build the standard Mus Luxury thermal receipt from a POS sale response. */
export function buildReceiptLines(sale: PosSalePayload, width = 32): ReceiptLine[] {
  const out: ReceiptLine[] = [];
  const b = sale.boutique_info || {};
  out.push({ text: (b.name || "Mus Luxury").toUpperCase(), align: "center", bold: true, double_height: true, double_width: true });
  if (b.address) out.push({ text: b.address, align: "center" });
  if (b.phone)   out.push({ text: b.phone, align: "center" });
  if (b.tax_id)  out.push({ text: `NIF ${b.tax_id}`, align: "center" });
  out.push({ rule: true });

  const ref = sale.sale_reference || "—";
  const date = sale.created_at ? serverDate(sale.created_at).toLocaleString("fr-FR") : "—";
  out.push({ left: "Ticket", right: ref, bold: true });
  out.push({ left: "Date",   right: date });
  if (sale.customer?.full_name) out.push({ left: "Client", right: sale.customer.full_name });
  out.push({ rule: true });

  for (const it of sale.items ?? []) {
    const name = `${it.product_name ?? ""}${it.variant_title ? ` · ${it.variant_title}` : ""}`.trim();
    const qty = Number(it.quantity ?? 0);
    const total = Number(it.line_total_dzd ?? (Number(it.unit_price_dzd ?? 0) * qty));
    out.push({ left: name.slice(0, Math.max(1, width - 10)), right: fmtDzd(total) });
    if (qty > 1 || it.unit_price_dzd) {
      out.push({ left: `  ${qty} × ${fmtDzd(it.unit_price_dzd)}`, right: "" });
    }
  }
  out.push({ rule: true });

  const sub = Number(sale.subtotal_dzd ?? 0);
  const disc = Number(sale.discount_dzd ?? 0);
  out.push({ left: "Sous-total", right: fmtDzd(sub) });
  if (disc > 0) out.push({ left: "Remise", right: `- ${fmtDzd(disc)}` });
  if ((sale.tax_dzd ?? 0) > 0) out.push({ left: "TVA", right: fmtDzd(sale.tax_dzd) });
  out.push({ left: "TOTAL", right: fmtDzd(sale.total_dzd), bold: true, double_height: true });

  if (sale.payments?.length) {
    out.push({ rule: true });
    for (const p of sale.payments) {
      const label = (p.method || "espèces").toString().toUpperCase();
      out.push({ left: `Paiement (${label})`, right: fmtDzd(p.amount_dzd) });
      if ((p.change_dzd ?? 0) > 0) out.push({ left: "Rendu", right: fmtDzd(p.change_dzd) });
    }
  }

  if (sale.offline) {
    out.push({ rule: true });
    out.push({ text: "VENTE HORS LIGNE", align: "center", bold: true });
    out.push({ text: "À synchroniser au retour du réseau.", align: "center" });
  }

  out.push({ rule: true });
  out.push({ text: "Merci de votre visite", align: "center" });
  if (ref !== "—") out.push({ barcode: ref });
  return out;
}

// ============================================================================
// LABEL PRINTER
// Separate device, separate settings. ZPL is the default (Zebra & compatibles);
// ESC/POS text is a fallback for shops that bought a label printer that only
// speaks ESC/POS.
// ============================================================================

export interface LabelPrinterTarget {
  printer_name?: string | null;
  device_path?: string | null;
  host?: string | null;
  port?: number | null;
  format?: "zpl" | "escpos-text";
  width_mm?: number;
  height_mm?: number;
  dpi?: 203 | 300 | 600;
}

export interface LabelPayload {
  header: string;
  product_name: string;
  variant_title?: string;
  sku: string;
  price_text: string;
  barcode_value: string;
  barcode_kind?: "code128" | "ean13";
  copies?: number;
}

const DEFAULT_LABEL_SETTINGS: LabelPrinterTarget = {
  printer_name: null,
  device_path: null,
  format: "zpl",
  width_mm: 50,
  height_mm: 30,
  dpi: 203,
};

export function loadLabelPrinterSettings(): LabelPrinterTarget {
  try {
    const raw = localStorage.getItem(POS_LABEL_SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_LABEL_SETTINGS };
    const parsed = JSON.parse(raw) as LabelPrinterTarget;
    return {
      printer_name: parsed.printer_name ?? null,
      device_path: parsed.device_path ?? null,
      format: parsed.format === "escpos-text" ? "escpos-text" : "zpl",
      width_mm: Number(parsed.width_mm) || 50,
      height_mm: Number(parsed.height_mm) || 30,
      dpi: (parsed.dpi === 300 || parsed.dpi === 600 ? parsed.dpi : 203),
    };
  } catch {
    return { ...DEFAULT_LABEL_SETTINGS };
  }
}

export function saveLabelPrinterSettings(s: LabelPrinterTarget): void {
  try {
    localStorage.setItem(POS_LABEL_SETTINGS_KEY, JSON.stringify({
      printer_name: s.printer_name ?? null,
      device_path: s.device_path ?? null,
      format: s.format === "escpos-text" ? "escpos-text" : "zpl",
      width_mm: Number(s.width_mm) || 50,
      height_mm: Number(s.height_mm) || 30,
      dpi: (s.dpi === 300 || s.dpi === 600 ? s.dpi : 203),
    }));
  } catch {
    // quota / private mode — reverts to defaults next launch
  }
}

export function isLabelPrinterConfigured(s?: LabelPrinterTarget): boolean {
  const cfg = s ?? loadLabelPrinterSettings();
  return Boolean((cfg.printer_name && cfg.printer_name.trim()) || (cfg.device_path && cfg.device_path.trim()));
}

export async function printLabels(opts: LabelPrinterTarget, labels: LabelPayload[]): Promise<HardwareResult> {
  const invoke = getTauriInvoke();
  if (!invoke) return { ok: false, error: tr("hw.no_tauri_label") };
  if (!labels.length) return { ok: false, error: tr("hw.no_labels") };
  try {
    await invoke("pos_print_labels", { opts, labels });
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("hw.label_error")) };
  }
}

export async function testPrintLabel(opts: LabelPrinterTarget = loadLabelPrinterSettings()): Promise<HardwareResult> {
  const invoke = getTauriInvoke();
  if (!invoke) return { ok: false, error: tr("hw.no_tauri_test") };
  try {
    await invoke("pos_test_print_label", { opts });
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("hw.label_test_failed")) };
  }
}

/**
 * Print a receipt using the saved hardware settings. Decides whether to kick
 * the cash drawer based on whether any payment was in cash.
 */
export async function printSaleReceipt(sale: PosSalePayload): Promise<HardwareResult> {
  const target = loadHardwareSettings();
  if (!isHardwareConfigured(target)) {
    return { ok: false, error: tr("hw.no_printer") };
  }
  const openDrawer = (sale.payments ?? []).some(p => (p.method || "").toLowerCase().includes("cash") || (p.method || "").toLowerCase().includes("espec"));
  const lines = buildReceiptLines(sale, target.line_width ?? 32);
  return printReceipt(
    { ...target, open_drawer: openDrawer, cut: true, feed_before_cut: 3 },
    lines,
  );
}
