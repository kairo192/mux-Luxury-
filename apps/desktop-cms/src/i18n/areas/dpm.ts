import { defineArea } from "./define";

export const dpm = defineArea("dpm", {
  "title": ["Suppression / Archivage du Produit", "Delete / archive the product", "حذف / أرشفة المنتج"],
  "sub": ["Gestion du catalogue — Maison Mus Luxury", "Catalogue management — Maison Mus Luxury", "إدارة الكتالوج — Maison Mus Luxury"],
  "close": ["Fermer", "Close", "إغلاق"],
  "price": ["Prix de vente : ", "Selling price: ", "سعر البيع: "],
  "stock": ["Stock : ", "Stock: ", "المخزون: "],
  "units": ["{{n}} unités", "{{n}} units", "{{n}} وحدة"],
  "status": ["Statut : ", "Status: ", "الحالة: "],
  "st_archived": ["Archivé (hors vitrine)", "Archived (not in the shop)", "مؤرشف (خارج المتجر)"],
  "st_published": ["Publié (en vente)", "Published (on sale)", "منشور (معروض للبيع)"],
  "st_draft": ["Brouillon", "Draft", "مسودة"],
  "choose": ["Veuillez sélectionner l'action à exécuter pour cet article :", "Choose what to do with this item:", "اختر الإجراء لهذا المنتج:"],
  "opt1": ["Option 1 : Suppression définitive de la base", "Option 1: Delete permanently from the database", "الخيار 1: الحذف النهائي من قاعدة البيانات"],
  "opt1_body": ["Seulement pour un article jamais vendu ni acheté (créé par erreur). S'il a déjà été vendu (en ligne ou en magasin) ou acheté à un fournisseur, il est archivé à la place : les factures, rapports et comptes fournisseurs restent exacts. Aucune commande n'est jamais effacée.", "Only for an item never sold nor bought (created by mistake). If it was already sold (online or in the shop) or bought from a supplier, it is archived instead: invoices, reports and supplier accounts stay correct. No order is ever erased.", "فقط لمنتج لم يُبع ولم يُشترَ قط (أُنشئ خطأً). إذا سبق بيعه (عبر الإنترنت أو في المحل) أو شراؤه من مورد، يُؤرشف بدلاً من ذلك: تبقى الفواتير والتقارير وحسابات الموردين صحيحة. لا تُحذف أي طلبية أبداً."],
  "deleting": ["Suppression...", "Deleting…", "جارٍ الحذف…"],
  "delete": ["Supprimer Définitivement", "Delete permanently", "حذف نهائي"],
  "opt2": ["Option 2 : Archivage sécurisé (recommandé)", "Option 2: Safe archive (recommended)", "الخيار 2: أرشفة آمنة (موصى به)"],
  "opt2_body": ["Masque le produit de la vitrine tout en préservant l'intégrité des factures et de la comptabilité. Vous pouvez le réactiver à tout moment.", "Hides the product from the shop while keeping invoices and accounts intact. You can reactivate it at any time.", "يخفي المنتج من المتجر مع الحفاظ على سلامة الفواتير والمحاسبة. يمكنك إعادة تفعيله في أي وقت."],
  "archiving": ["Archivage...", "Archiving…", "جارٍ الأرشفة…"],
  "archive": ["Archiver la pièce", "Archive the item", "أرشفة المنتج"],
});
