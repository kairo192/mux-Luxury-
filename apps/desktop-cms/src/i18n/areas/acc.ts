import { defineArea } from "./define";

export const acc = defineArea("acc", {
  "hide": ["Masquer le message", "Hide the message", "إخفاء الرسالة"],
  "rev_split": ["Articles {{goods}} + livraison {{delivery}} DZD", "Items {{goods}} + delivery {{delivery}} DZD", "القطع {{goods}} + التوصيل {{delivery}} DZD"],
  "rev_counts": ["{{orders}} commande(s) en ligne • {{sales}} vente(s) magasin • {{units}} pièce(s)", "{{orders}} online order(s) • {{sales}} shop sale(s) • {{units}} piece(s)", "{{orders}} طلبية إلكترونية • {{sales}} بيع في المحل • {{units}} قطعة"],
  "margin_def": ["Chiffre d'affaires − coût d'achat", "Revenue − purchase cost", "رقم الأعمال − تكلفة الشراء"],
  "cogs": ["Coût des ventes", "COGS", "تكلفة المبيعات"],
  "charges": ["Charges", "Expenses", "المصاريف"],
  "unpaid_part": [", dont {{amount}} DZD à régler", ", of which {{amount}} DZD still to pay", "، منها {{amount}} DZD للدفع"],
  "stock_losses": ["Pertes de stock", "Stock losses", "خسائر المخزون"],
  "product_n": ["Produit #{{id}}", "Product #{{id}}", "المنتج #{{id}}"],
  "balanced": ["Journal équilibré (débits = crédits)", "Journal balanced (debits = credits)", "الدفتر متوازن (المدين = الدائن)"],
  "unbalanced": ["Déséquilibre détecté !", "Imbalance found!", "تم اكتشاف عدم توازن!"],
  "journal_note": ["Débits = {{debits}} DZD | Crédits = {{credits}} DZD — écritures des achats fournisseurs et des dépenses. Les ventes sont dans le compte de résultat et la trésorerie.", "Debits = {{debits}} DZD | Credits = {{credits}} DZD — supplier purchase and expense entries. Sales are in the income statement and the treasury.", "المدين = {{debits}} DZD | الدائن = {{credits}} DZD — قيود مشتريات الموردين والمصاريف. المبيعات في حساب النتائج والخزينة."],
  "entries_n": ["{{n}} écritures", "{{n}} entries", "{{n}} قيد"],
  "no": ["N°", "No.", "رقم"],
  "account": ["Compte", "Account", "الحساب"],
  "debit": ["Débit", "Debit", "مدين"],
  "credit": ["Crédit", "Credit", "دائن"],
  "ref": ["Réf", "Ref", "المرجع"],
});
