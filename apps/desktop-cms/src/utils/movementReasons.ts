// Readable names for stock-movement reasons stored by the server
// (inventory_movements.reason), in the language of the CMS (i18n area "mv").
import { tr } from "../i18n/translations";

const KNOWN = new Set<string>(["order_reserved", "order_confirmed", "order_cancelled", "order_returned", "pos_sale", "pos_sale_offline", "pos_refund", "manual_in", "manual_out", "manual_adjustment", "cms_manual_adjustment", "variant_created", "variant_edit", "create_variant", "adjust_variant_stock", "stock_write_off", "purchase_received", "physical_count_reconcile", "cms_bulk_update", "writeoff_damaged", "writeoff_lost", "writeoff_return_to_supplier", "writeoff_promotional_giveaway", "writeoff_stocktake_correction"]);

export function movementReasonLabel(reason: string | null | undefined): string {
  const r = String(reason || "");
  if (KNOWN.has(r)) return tr(`mv.${r}`);
  if (r.startsWith("order_")) return tr("mv.order_other", { x: r.slice(6).replace(/_/g, " ") });
  if (r.startsWith("writeoff_")) return tr("mv.writeoff_other", { x: r.slice(9).replace(/_/g, " ") });
  // Written by the server for people, with a reference ("Réception fournisseur ACH-…").
  const purchase = r.match(/^Réception fournisseur (.+)$/);
  if (purchase) return tr("mv.purchase_ref", { ref: purchase[1] });
  const count = r.match(/^Inventaire (.+)$/);
  if (count) return tr("mv.count_ref", { ref: count[1] });
  return r.replace(/_/g, " ");
}
