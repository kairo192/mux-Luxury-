// Descriptions of treasury movements, written by the server in French when the
// movement is recorded, shown in the language of the CMS (i18n area "tdesc").
// Manual movements read "<kind> — <notes>": the kind is translated, the notes
// (typed by staff) stay as they are.
import { tr } from "../i18n/translations";
import { codeLabel } from "./codeLabels";

const KIND_FR: Record<string, string> = {
  "Fond de caisse / alimentation": "cash_in",
  "Apport du propriétaire": "capital_contribution",
  "Autre entrée": "other_inflow",
  "Retrait du propriétaire": "cash_out",
  "Petite dépense boutique": "minor_expense",
  "Régularisation d'écart de caisse": "cash_adjustment",
  "Autre sortie": "other_outflow",
  "Dépôt d'espèces à la banque": "bank_deposit",
  "Retrait à la banque vers la caisse": "bank_withdrawal",
  "Versement du livreur sur le compte": "courier_remittance",
};

const RULES: Array<[RegExp, (m: RegExpMatchArray) => string]> = [
  [/^Dépense: (.+)$/s, (m) => tr("tdesc.expense", { x: m[1] })],
  [/^Annulation dépense: (.+)$/s, (m) => tr("tdesc.expense_cancelled", { x: m[1] })],
  [/^Commande livrée (\S+) \(paiement à la livraison\)$/, (m) => tr("tdesc.cod_delivered", { ref: m[1] })],
  [/^Paiement fournisseur \((.+)\)$/, (m) => tr("tdesc.supplier_payment", { ref: m[1] })],
  [/^Vente magasin (\S+) \(hors ligne\)$/, (m) => tr("tdesc.pos_sale_offline", { ref: m[1] })],
  [/^Vente magasin (\S+)$/, (m) => tr("tdesc.pos_sale", { ref: m[1] })],
  [/^Remboursement (\S+) \(vente (\S+)\)$/, (m) => tr("tdesc.pos_refund", { ref: m[1], sale: m[2] })],
  [/^Retour après livraison (\S+)$/, (m) => tr("tdesc.cod_return", { ref: m[1] })],
  [/^Écart de caisse corrigé : vente (\S+) synchronisée après la clôture$/, (m) => tr("tdesc.variance_fixed", { ref: m[1] })],
  [/^Écart de caisse à la clôture \(excédent de (\d+) DA\)$/, (m) => tr("tdesc.variance_over", { n: m[1] })],
  [/^Écart de caisse à la clôture \(manque de (\d+) DA\)$/, (m) => tr("tdesc.variance_short", { n: m[1] })],
];

export function treasuryText(text: string | null | undefined): string {
  const s = String(text ?? "");
  for (const [re, fn] of RULES) {
    const m = s.match(re);
    if (m) return fn(m);
  }
  const dash = s.indexOf(" — ");
  const kind = dash >= 0 ? s.slice(0, dash) : s;
  if (KIND_FR[kind]) return codeLabel(KIND_FR[kind]) + (dash >= 0 ? s.slice(dash) : "");
  return s;
}
