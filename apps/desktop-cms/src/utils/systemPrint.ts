// ============================================================================
// Universal "system printer" print path.
//
// Not every boutique has a thermal receipt printer or a Zebra label printer —
// some will print receipts on an office inkjet, keep a PDF for accounting,
// or hand a laser-printed sheet of labels to the back-office. For those
// cases we open a self-contained HTML page, size it to the requested paper,
// and invoke `window.print()`. The Tauri WebView (Chromium-based) shows its
// standard PDF print preview — the operator picks ANY installed Windows
// printer, can zoom, scale, and change the paper size right there.
//
// This also doubles as the "preview" the user asked for: the preview IS the
// print dialog's PDF view, and the dialog's Save-as-PDF button yields a
// shareable PDF file.
// ============================================================================

import { tr } from "../i18n/translations";

export interface SystemPrintOptions {
  /** Visible <title> of the preview window; also what Windows shows as
   * the job name in the queue. */
  title?: string;
  /** Page size for the @page CSS rule. */
  paper?:
    | { kind: "mm"; width: number; height: number }
    | { kind: "a4" }
    | { kind: "letter" };
  /** Margin for the @page rule, in millimetres (0 for edge-to-edge thermal). */
  marginMm?: number;
  /** Extra CSS appended after the defaults. */
  extraCss?: string;
  /** Page body HTML. Each top-level `<div class="page">…</div>` becomes a new
   * paper page via `page-break-after: always`. */
  html: string;
  /** Automatically open the print dialog once the window loads. Default true. */
  autoPrint?: boolean;
}

export interface SystemPrintResult {
  ok: boolean;
  error?: string;
}

function buildPageSizeCss(opts: SystemPrintOptions): string {
  const margin = `${Math.max(0, opts.marginMm ?? 0)}mm`;
  const p = opts.paper ?? { kind: "a4" } as const;
  switch (p.kind) {
    case "mm":
      return `@page { size: ${p.width}mm ${p.height}mm; margin: ${margin}; }`;
    case "letter":
      return `@page { size: letter; margin: ${margin}; }`;
    case "a4":
    default:
      return `@page { size: A4; margin: ${margin}; }`;
  }
}

/**
 * Print an HTML page with the system print dialog (any installed printer,
 * or "Save as PDF").
 *
 * The page is written into a hidden frame of the CMS itself, not into a new
 * window: the desktop app's web view does not open pop-up windows, so
 * `window.open` returned nothing there and the button did nothing. A frame
 * works the same in the desktop app and in a browser.
 * Returns an ok/error result instead of throwing.
 */
export function openSystemPrint(opts: SystemPrintOptions): SystemPrintResult {
  try {
    if (typeof window === "undefined" || typeof document === "undefined") {
      return { ok: false, error: tr("misc.no_gui") };
    }
    const css = `
      ${buildPageSizeCss(opts)}
      * { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; }
      body {
        font-family: system-ui, -apple-system, "Segoe UI", Helvetica, sans-serif;
        color: #111;
      }
      .page { page-break-after: always; }
      .page:last-child { page-break-after: auto; }
      ${opts.extraCss ?? ""}
    `;
    const title = (opts.title ?? "Impression").replace(/</g, "&lt;");
    document.querySelectorAll("iframe[data-luxe-print]").forEach((f) => f.remove());
    const frame = document.createElement("iframe");
    frame.setAttribute("data-luxe-print", "1");
    frame.setAttribute("aria-hidden", "true");
    frame.title = title;
    frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;";
    document.body.appendChild(frame);
    const doc = frame.contentDocument;
    const win = frame.contentWindow;
    if (!doc || !win) {
      frame.remove();
      return { ok: false, error: tr("misc.sys_print_failed") };
    }
    doc.open();
    doc.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
      <style>${css}</style></head><body>${opts.html}</body></html>`);
    doc.close();
    if (opts.autoPrint !== false) {
      // Let images / barcodes lay out, then open the print dialog of the frame.
      setTimeout(() => {
        try {
          win.focus();
          win.print();
        } catch {
          /* the dialog could not open: nothing printed, nothing to undo */
        }
      }, 200);
    }
    // Remove the frame once the dialog is closed (or after a minute anyway).
    const cleanup = () => setTimeout(() => frame.remove(), 500);
    win.addEventListener("afterprint", cleanup, { once: true });
    setTimeout(() => frame.isConnected && frame.remove(), 60_000);
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message ?? e ?? tr("misc.sys_print_failed")) };
  }
}

// ----------------------------------------------------------------------------
// Opinionated builders for the two shapes we print most: the thermal receipt
// and the sticky product label. Both take a flexible options bag so the
// caller can override paper size, text, logo, etc. — nothing is baked in.
// ----------------------------------------------------------------------------

export interface ReceiptBlock {
  text?: string;
  align?: "left" | "center" | "right";
  bold?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
  left?: string;
  right?: string;
  rule?: boolean;
}

export function renderReceiptHtml(blocks: ReceiptBlock[]): string {
  const sizeClass = (s?: string) =>
    s === "xl" ? "font-size:18px;line-height:1.25;" :
    s === "lg" ? "font-size:15px;line-height:1.3;" :
    s === "sm" ? "font-size:10px;line-height:1.2;" :
                 "font-size:12px;line-height:1.3;";
  const rows = blocks.map((b) => {
    if (b.rule) return `<div style="border-top:1px dashed #000;margin:4px 0;"></div>`;
    if (b.left !== undefined || b.right !== undefined) {
      const bold = b.bold ? "font-weight:800;" : "";
      return `<div style="display:flex;justify-content:space-between;gap:8px;${bold}${sizeClass(b.size)}">
        <span>${escapeHtml(b.left ?? "")}</span><span>${escapeHtml(b.right ?? "")}</span>
      </div>`;
    }
    const style = `text-align:${b.align ?? "left"};${b.bold ? "font-weight:800;" : ""}${sizeClass(b.size)}`;
    return `<div style="${style}">${escapeHtml(b.text ?? "")}</div>`;
  }).join("");
  return `<div class="page" style="padding:4mm 3mm;">${rows}</div>`;
}

export interface LabelHtmlBlock {
  header: string;
  product_name: string;
  variant_title?: string;
  sku: string;
  price_text: string;
  barcode_svg?: string;   // caller passes SVG markup (reuses existing renderer)
}

export function renderLabelsHtml(labels: LabelHtmlBlock[], copies = 1): string {
  const n = Math.max(1, Math.min(100, copies));
  const perLabel = (l: LabelHtmlBlock) => `
    <div class="page" style="padding:2mm;text-align:center;">
      <div style="font-size:11px;font-weight:700;">${escapeHtml(l.header)}</div>
      <div style="font-size:10px;color:#333;">
        ${escapeHtml(l.product_name)}${l.variant_title ? " — " + escapeHtml(l.variant_title) : ""}
      </div>
      <div style="font-size:10px;color:#333;">SKU: ${escapeHtml(l.sku)}</div>
      <div style="font-size:14px;font-weight:800;margin-top:2px;">${escapeHtml(l.price_text)}</div>
      <div style="margin-top:4px;">${l.barcode_svg ?? ""}</div>
    </div>`;
  return labels.map((l) => Array.from({ length: n }, () => perLabel(l)).join("")).join("");
}

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c] as string
  ));
}
