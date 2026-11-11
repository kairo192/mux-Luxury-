// Readable names for stock-movement reasons stored by the server
// (inventory_movements.reason). Shared by the Stock tab and the movements report.
export const MOVEMENT_REASON_LABEL: Record<string, string> = {
  order_reserved: "Commande en ligne",
  order_confirmed: "Commande confirmée",
  order_cancelled: "Commande annulée",
  order_returned: "Commande retournée",
  pos_sale: "Vente magasin",
  pos_sale_offline: "Vente hors-ligne synchronisée",
  pos_refund: "Remboursement magasin",
  manual_in: "Ajustement manuel (+)",
  manual_out: "Ajustement manuel (−)",
  manual_adjustment: "Ajustement manuel",
  cms_manual_adjustment: "Ajustement manuel (CMS)",
  variant_created: "Création de la variante",
  variant_edit: "Modification de la variante",
  create_variant: "Création de la variante",
  adjust_variant_stock: "Ajustement manuel",
  stock_write_off: "Sortie de stock",
  purchase_received: "Réception fournisseur",
  physical_count_reconcile: "Réconciliation inventaire",
  cms_bulk_update: "Mise à jour en masse",
  writeoff_damaged: "Démarque — endommagé",
  writeoff_lost: "Démarque — perte/vol",
  writeoff_return_to_supplier: "Retour fournisseur",
  writeoff_promotional_giveaway: "Cadeau/promo",
  writeoff_stocktake_correction: "Correction d'inventaire",
};

export function movementReasonLabel(reason: string | null | undefined): string {
  const r = String(reason || "");
  if (MOVEMENT_REASON_LABEL[r]) return MOVEMENT_REASON_LABEL[r];
  if (r.startsWith("order_")) return `Commande — ${r.slice(6).replace(/_/g, " ")}`;
  if (r.startsWith("writeoff_")) return `Démarque — ${r.slice(9).replace(/_/g, " ")}`;
  // Already written for people (e.g. "Réception fournisseur ACH-…").
  return r.replace(/_/g, " ");
}
