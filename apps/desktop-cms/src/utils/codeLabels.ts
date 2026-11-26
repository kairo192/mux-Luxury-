// Readable names for the codes the server stores (treasury sources, accounts,
// payment methods/statuses, expense categories…), in the language of the CMS
// (i18n area "code"). The CSV exports use the server's own French names.
import { tr } from "../i18n/translations";

const KNOWN = new Set<string>(["cash", "card", "transfer", "bank", "bank_transfer", "check", "other", "paid", "pending", "unpaid", "partial", "cash_box", "bank_account", "inflow", "outflow", "deposit", "withdrawal", "pos_sale", "pos_refund", "cod_collection", "cod_refund", "expense_payment", "purchase_payment", "manual_adjustment", "expense_cancelled", "register_variance", "loyer", "rent", "salaires", "electricite_eau", "internet_tel", "internet_telephone", "packaging", "publicite_marketing", "marketing", "transport_logistique", "maintenance", "abonnements_logiciels", "autre", "cash_in", "capital_contribution", "other_inflow", "cash_out", "minor_expense", "cash_adjustment", "other_outflow", "bank_deposit", "bank_withdrawal", "courier_remittance"]);

export function codeLabel(code: string | null | undefined): string {
  const c = String(code ?? "");
  return KNOWN.has(c) ? tr(`code.${c}`) : c.replace(/_/g, " ");
}
