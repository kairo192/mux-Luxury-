// Readable names for the codes the server stores (treasury sources,
// accounts, payment methods/statuses, expense categories…). Kept in step
// with _FR_CODES in backend/app/main.py, which the CSV exports use.
export const CODE_LABEL: Record<string, string> = {
  cash: "Espèces", card: "Carte", transfer: "Virement", bank: "Virement", bank_transfer: "Virement",
  check: "Chèque", other: "Autre", paid: "Payée", pending: "À régler", unpaid: "À régler", partial: "Partiellement payée",
  cash_box: "Caisse", bank_account: "Banque / CCP", inflow: "Entrée", outflow: "Sortie", deposit: "Dépôt", withdrawal: "Retrait",
  pos_sale: "Vente magasin", pos_refund: "Remboursement magasin", cod_collection: "Commande livrée (COD)",
  cod_refund: "Retour après livraison", expense_payment: "Paiement dépense", purchase_payment: "Paiement fournisseur",
  manual_adjustment: "Mouvement manuel", expense_cancelled: "Annulation dépense", register_variance: "Écart de caisse",
  loyer: "Loyer & local", rent: "Loyer & local", salaires: "Salaires", electricite_eau: "Électricité, gaz & eau",
  internet_tel: "Internet & télécoms", packaging: "Emballages", publicite_marketing: "Publicité",
  transport_logistique: "Transport & coursiers", maintenance: "Maintenance", abonnements_logiciels: "Logiciels",
  autre: "Autres charges",
};

export function codeLabel(code: string | null | undefined): string {
  const c = String(code ?? "");
  return CODE_LABEL[c] || c.replace(/_/g, " ");
}
