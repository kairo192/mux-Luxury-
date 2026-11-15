// Ticket layout for the system print dialog (any Windows printer / PDF).
import { loadHardwareSettings } from "../../utils/posHardware";
import { serverDate } from "../../utils/serverDate";
import type { ReceiptBlock } from "../../utils/systemPrint";
import { fmt } from "./ui";

/** Lines of the receipt and the paper width (58 or 80 mm) for a sale. */
export function buildReceiptBlocks(receipt: any): { blocks: ReceiptBlock[]; paperWidthMm: number } {
  const b = receipt.boutique_info || {};
  const width = loadHardwareSettings().line_width ?? 32;
  const paperWidthMm = width >= 42 ? 80 : 58;
  const blocks: ReceiptBlock[] = [];
  blocks.push({ text: (b.name || "Mus Luxury"), align: "center", bold: true, size: "lg" });
  if (b.legal_name && b.legal_name !== b.name) blocks.push({ text: b.legal_name, align: "center", size: "sm" });
  if (b.address) blocks.push({ text: b.address, align: "center", size: "sm" });
  if (b.phone)   blocks.push({ text: `Tél: ${b.phone}`, align: "center", size: "sm" });
  for (const [label, v] of [["NIF", b.nif], ["NIS", b.nis], ["RC", b.rc], ["Art.", b.article]] as const) {
    if (v) blocks.push({ text: `${label}: ${v}`, align: "center", size: "sm" });
  }
  blocks.push({ rule: true });
  blocks.push({ left: "Ticket", right: receipt.sale_reference || "—", bold: true });
  blocks.push({ left: "Date", right: receipt.created_at ? serverDate(receipt.created_at).toLocaleString("fr-FR") : "—" });
  if (receipt.customer?.full_name) blocks.push({ left: "Client", right: receipt.customer.full_name });
  if (receipt.offline) blocks.push({ text: "** HORS LIGNE — à synchroniser **", align: "center", bold: true });
  if (receipt.sale_type === "refund") blocks.push({ text: "** REMBOURSEMENT **", align: "center", bold: true });
  blocks.push({ rule: true });
  for (const it of receipt.items ?? []) {
    const name = `${it.product_name ?? ""}${it.variant_title ? " · " + it.variant_title : ""}`.trim();
    const qty = Number(it.quantity ?? 0);
    const lineTotal = Number(it.line_total_dzd ?? (Number(it.unit_price_dzd ?? 0) * qty));
    blocks.push({ left: name, right: fmt(lineTotal) });
    // Unit price only when known: never print "2 × 0 DA" next to a real total.
    if (it.unit_price_dzd != null) blocks.push({ left: `  ${qty} × ${fmt(it.unit_price_dzd)}`, size: "sm" });
    else if (qty > 1) blocks.push({ left: `  Qté ${qty}`, size: "sm" });
  }
  blocks.push({ rule: true });
  if (receipt.subtotal_dzd != null) blocks.push({ left: "Sous-total", right: fmt(receipt.subtotal_dzd) });
  if ((receipt.discount_dzd ?? 0) > 0) blocks.push({ left: "Remise", right: `- ${fmt(receipt.discount_dzd)}` });
  if ((receipt.tax_dzd ?? 0) > 0) blocks.push({ left: "TVA", right: fmt(receipt.tax_dzd) });
  blocks.push({ left: "TOTAL", right: fmt(receipt.total_dzd), bold: true, size: "xl" });
  if ((receipt.payments ?? []).length) {
    blocks.push({ rule: true });
    for (const p of receipt.payments) {
      const label = p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : (p.method ?? "");
      blocks.push({ left: label, right: fmt(p.amount_dzd) });
      if ((p.change_dzd ?? 0) > 0) blocks.push({ left: "Monnaie", right: fmt(p.change_dzd) });
    }
  }
  blocks.push({ rule: true });
  blocks.push({ text: b.footer_line || `Merci de votre visite — ${b.name || "Mus Luxury"}`, align: "center", size: "sm" });
  return { blocks, paperWidthMm };
}
