import { defineArea } from "./define";

export const tdesc = defineArea("tdesc", {
  "expense": ["Dépense : {{x}}", "Expense: {{x}}", "مصروف: {{x}}"],
  "expense_cancelled": ["Annulation dépense : {{x}}", "Expense cancelled: {{x}}", "إلغاء مصروف: {{x}}"],
  "cod_delivered": ["Commande livrée {{ref}} (paiement à la livraison)", "Order delivered {{ref}} (cash on delivery)", "طلبية مُسلّمة {{ref}} (الدفع عند الاستلام)"],
  "supplier_payment": ["Paiement fournisseur ({{ref}})", "Supplier payment ({{ref}})", "دفع للمورد ({{ref}})"],
  "pos_sale_offline": ["Vente magasin {{ref}} (hors ligne)", "Shop sale {{ref}} (offline)", "بيع في المحل {{ref}} (دون اتصال)"],
  "pos_sale": ["Vente magasin {{ref}}", "Shop sale {{ref}}", "بيع في المحل {{ref}}"],
  "pos_refund": ["Remboursement {{ref}} (vente {{sale}})", "Refund {{ref}} (sale {{sale}})", "استرجاع {{ref}} (البيع {{sale}})"],
  "cod_return": ["Retour après livraison {{ref}}", "Return after delivery {{ref}}", "إرجاع بعد التسليم {{ref}}"],
  "variance_fixed": ["Écart de caisse corrigé : vente {{ref}} synchronisée après la clôture", "Cash difference corrected: sale {{ref}} synced after closing", "تصحيح فارق الصندوق: مزامنة البيع {{ref}} بعد الإقفال"],
  "variance_over": ["Écart de caisse à la clôture (excédent de {{n}} DA)", "Cash difference at closing ({{n}} DA over)", "فارق الصندوق عند الإقفال (زيادة {{n}} DA)"],
  "variance_short": ["Écart de caisse à la clôture (manque de {{n}} DA)", "Cash difference at closing ({{n}} DA short)", "فارق الصندوق عند الإقفال (نقص {{n}} DA)"],
});
