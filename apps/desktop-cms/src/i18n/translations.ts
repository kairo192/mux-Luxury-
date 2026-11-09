// ============================================================================
// CMS translations — flat snake_case keys.
//
// French is the authoritative source; English + Arabic were derived by hand
// so they match the shop's voice. When a value is missing for a language the
// hook falls back FR → EN → key, so a page using a key the dictionary does
// not have shows the key name (easy to grep: "pos.toolbar.hardware").
//
// Interpolation: use `{{name}}` in the value; pass values via t(key, {name}).
//
// Keys are organized by UI region:
//   sidebar.*   — left navigation labels
//   topbar.*    — top-bar / user chip / language toggle
//   common.*    — reused CTAs: save, cancel, delete, etc.
//   status.*    — loading, empty, error strings
//   dashboard.* — main dashboard shell + metric labels
//   pos.*       — POS page
//
// When adding a new page's strings, create a new section (ex: `orders.*`)
// and keep each language's block in the same order.
// ============================================================================

export type Lang = "fr" | "en" | "ar";

export const SUPPORTED_LANGS: Lang[] = ["fr", "en", "ar"];

export const RTL_LANGS: ReadonlySet<Lang> = new Set<Lang>(["ar"]);

export const LANG_LABELS: Record<Lang, string> = {
  fr: "Français",
  en: "English",
  ar: "العربية",
};

type Dict = Record<string, string>;

const fr: Dict = {
  // ----- sidebar
  "sidebar.dashboard": "Tableau de bord",
  "sidebar.pos": "Point de vente",
  "sidebar.products": "Produits",
  "sidebar.categories": "Catégories",
  "sidebar.inventory": "Stock",
  "sidebar.orders": "Commandes",
  "sidebar.customers": "Clients",
  "sidebar.suppliers": "Fournisseurs",
  "sidebar.purchases": "Achats",
  "sidebar.expenses": "Dépenses",
  "sidebar.treasury": "Trésorerie",
  "sidebar.accounting": "Comptabilité",
  "sidebar.reports": "Rapports",
  "sidebar.settings": "Paramètres",
  "sidebar.users_roles": "Utilisateurs & rôles",
  "sidebar.devices": "Appareils",
  "sidebar.fiscal_settings": "Paramètres fiscaux",
  "sidebar.audit_log": "Journal d'audit",

  // ----- topbar
  "topbar.hello": "Bonjour, {{name}}",
  "topbar.logout": "Se déconnecter",
  "topbar.language": "Langue",

  // ----- common
  "common.save": "Enregistrer",
  "common.cancel": "Annuler",
  "common.delete": "Supprimer",
  "common.edit": "Modifier",
  "common.create": "Créer",
  "common.add": "Ajouter",
  "common.close": "Fermer",
  "common.confirm": "Confirmer",
  "common.search": "Rechercher…",
  "common.filter": "Filtrer",
  "common.export": "Exporter",
  "common.import": "Importer",
  "common.refresh": "Actualiser",
  "common.view": "Voir",
  "common.print": "Imprimer",
  "common.required": "Obligatoire",
  "common.optional": "Facultatif",
  "common.yes": "Oui",
  "common.no": "Non",

  // ----- status
  "status.loading": "Chargement…",
  "status.saving": "Enregistrement…",
  "status.empty": "Aucun résultat.",
  "status.error_title": "Une erreur est survenue",
  "status.try_again": "Réessayer",
  "status.offline": "Hors ligne",
  "status.online": "En ligne",
  "status.unsaved_changes": "Modifications non enregistrées",

  // ----- dashboard
  "dashboard.title": "Tableau de bord",
  "dashboard.subtitle": "Vue d'ensemble de la boutique",
  "dashboard.revenue_today": "Chiffre d'affaires (aujourd'hui)",
  "dashboard.orders_today": "Commandes (aujourd'hui)",
  "dashboard.pending_orders": "Commandes à traiter",
  "dashboard.low_stock_items": "Articles en rupture",
  "dashboard.best_sellers": "Meilleures ventes",
  "dashboard.recent_orders": "Commandes récentes",
  "dashboard.cash_in_register": "Espèces en caisse",

  // ----- POS
  "pos.title": "Point de vente",
  "pos.scan_or_search": "Scanner ou chercher un produit",
  "pos.scan_placeholder": "Code-barres, SKU ou nom…",
  "pos.search": "Chercher",
  "pos.cart_empty": "Panier vide",
  "pos.total": "TOTAL",
  "pos.subtotal": "Sous-total",
  "pos.discount": "Remise",
  "pos.tax": "TVA",
  "pos.checkout": "Encaisser",
  "pos.open_drawer": "Ouvrir le tiroir",
  "pos.print_receipt": "Imprimer",
  "pos.hardware": "Matériel",
  "pos.history": "Historique",
  "pos.close_session": "Clôturer",
  "pos.open_session": "Ouvrir la caisse",
  "pos.opening_float": "Fonds de caisse",
  "pos.cashier": "Caissier",
  "pos.customer": "Client",
  "pos.offline_banner": "Hors ligne — les ventes seront synchronisées au retour du réseau.",
  "pos.sale_recorded": "Vente {{ref}} enregistrée — {{total}}",
  "pos.no_product_for": "Aucun produit pour « {{term}} »",
};

const en: Dict = {
  "sidebar.dashboard": "Dashboard",
  "sidebar.pos": "Point of sale",
  "sidebar.products": "Products",
  "sidebar.categories": "Categories",
  "sidebar.inventory": "Inventory",
  "sidebar.orders": "Orders",
  "sidebar.customers": "Customers",
  "sidebar.suppliers": "Suppliers",
  "sidebar.purchases": "Purchases",
  "sidebar.expenses": "Expenses",
  "sidebar.treasury": "Treasury",
  "sidebar.accounting": "Accounting",
  "sidebar.reports": "Reports",
  "sidebar.settings": "Settings",
  "sidebar.users_roles": "Users & roles",
  "sidebar.devices": "Devices",
  "sidebar.fiscal_settings": "Fiscal settings",
  "sidebar.audit_log": "Audit log",

  "topbar.hello": "Hello, {{name}}",
  "topbar.logout": "Sign out",
  "topbar.language": "Language",

  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.create": "Create",
  "common.add": "Add",
  "common.close": "Close",
  "common.confirm": "Confirm",
  "common.search": "Search…",
  "common.filter": "Filter",
  "common.export": "Export",
  "common.import": "Import",
  "common.refresh": "Refresh",
  "common.view": "View",
  "common.print": "Print",
  "common.required": "Required",
  "common.optional": "Optional",
  "common.yes": "Yes",
  "common.no": "No",

  "status.loading": "Loading…",
  "status.saving": "Saving…",
  "status.empty": "No results.",
  "status.error_title": "Something went wrong",
  "status.try_again": "Try again",
  "status.offline": "Offline",
  "status.online": "Online",
  "status.unsaved_changes": "Unsaved changes",

  "dashboard.title": "Dashboard",
  "dashboard.subtitle": "Store at a glance",
  "dashboard.revenue_today": "Revenue (today)",
  "dashboard.orders_today": "Orders (today)",
  "dashboard.pending_orders": "Pending orders",
  "dashboard.low_stock_items": "Low-stock items",
  "dashboard.best_sellers": "Best sellers",
  "dashboard.recent_orders": "Recent orders",
  "dashboard.cash_in_register": "Cash in register",

  "pos.title": "Point of sale",
  "pos.scan_or_search": "Scan or search for a product",
  "pos.scan_placeholder": "Barcode, SKU or name…",
  "pos.search": "Search",
  "pos.cart_empty": "Empty cart",
  "pos.total": "TOTAL",
  "pos.subtotal": "Subtotal",
  "pos.discount": "Discount",
  "pos.tax": "Tax",
  "pos.checkout": "Checkout",
  "pos.open_drawer": "Open drawer",
  "pos.print_receipt": "Print",
  "pos.hardware": "Hardware",
  "pos.history": "History",
  "pos.close_session": "Close register",
  "pos.open_session": "Open register",
  "pos.opening_float": "Opening float",
  "pos.cashier": "Cashier",
  "pos.customer": "Customer",
  "pos.offline_banner": "Offline — sales will sync when the network returns.",
  "pos.sale_recorded": "Sale {{ref}} recorded — {{total}}",
  "pos.no_product_for": "No product for « {{term}} »",
};

const ar: Dict = {
  "sidebar.dashboard": "لوحة التحكم",
  "sidebar.pos": "نقطة البيع",
  "sidebar.products": "المنتجات",
  "sidebar.categories": "الفئات",
  "sidebar.inventory": "المخزون",
  "sidebar.orders": "الطلبات",
  "sidebar.customers": "العملاء",
  "sidebar.suppliers": "الموردون",
  "sidebar.purchases": "المشتريات",
  "sidebar.expenses": "المصاريف",
  "sidebar.treasury": "الخزينة",
  "sidebar.accounting": "المحاسبة",
  "sidebar.reports": "التقارير",
  "sidebar.settings": "الإعدادات",
  "sidebar.users_roles": "المستخدمون والأدوار",
  "sidebar.devices": "الأجهزة",
  "sidebar.fiscal_settings": "الإعدادات الضريبية",
  "sidebar.audit_log": "سجل التدقيق",

  "topbar.hello": "مرحبا، {{name}}",
  "topbar.logout": "تسجيل الخروج",
  "topbar.language": "اللغة",

  "common.save": "حفظ",
  "common.cancel": "إلغاء",
  "common.delete": "حذف",
  "common.edit": "تعديل",
  "common.create": "إنشاء",
  "common.add": "إضافة",
  "common.close": "إغلاق",
  "common.confirm": "تأكيد",
  "common.search": "بحث…",
  "common.filter": "تصفية",
  "common.export": "تصدير",
  "common.import": "استيراد",
  "common.refresh": "تحديث",
  "common.view": "عرض",
  "common.print": "طباعة",
  "common.required": "مطلوب",
  "common.optional": "اختياري",
  "common.yes": "نعم",
  "common.no": "لا",

  "status.loading": "جاري التحميل…",
  "status.saving": "جاري الحفظ…",
  "status.empty": "لا توجد نتائج.",
  "status.error_title": "حدث خطأ",
  "status.try_again": "إعادة المحاولة",
  "status.offline": "غير متصل",
  "status.online": "متصل",
  "status.unsaved_changes": "تغييرات غير محفوظة",

  "dashboard.title": "لوحة التحكم",
  "dashboard.subtitle": "نظرة عامة على المتجر",
  "dashboard.revenue_today": "الإيرادات (اليوم)",
  "dashboard.orders_today": "الطلبات (اليوم)",
  "dashboard.pending_orders": "طلبات قيد المعالجة",
  "dashboard.low_stock_items": "أصناف قاربت على النفاد",
  "dashboard.best_sellers": "الأكثر مبيعاً",
  "dashboard.recent_orders": "أحدث الطلبات",
  "dashboard.cash_in_register": "النقد في الصندوق",

  "pos.title": "نقطة البيع",
  "pos.scan_or_search": "امسح أو ابحث عن منتج",
  "pos.scan_placeholder": "الرمز الشريطي أو رمز المنتج أو الاسم…",
  "pos.search": "بحث",
  "pos.cart_empty": "السلة فارغة",
  "pos.total": "الإجمالي",
  "pos.subtotal": "المجموع الفرعي",
  "pos.discount": "خصم",
  "pos.tax": "ضريبة",
  "pos.checkout": "الدفع",
  "pos.open_drawer": "فتح الدرج",
  "pos.print_receipt": "طباعة",
  "pos.hardware": "الأجهزة",
  "pos.history": "السجل",
  "pos.close_session": "إقفال الصندوق",
  "pos.open_session": "فتح الصندوق",
  "pos.opening_float": "رصيد افتتاح الصندوق",
  "pos.cashier": "أمين الصندوق",
  "pos.customer": "العميل",
  "pos.offline_banner": "غير متصل — ستتم مزامنة المبيعات عند عودة الشبكة.",
  "pos.sale_recorded": "تم تسجيل البيع {{ref}} — {{total}}",
  "pos.no_product_for": "لا يوجد منتج لـ « {{term}} »",
};

export const DICTS: Record<Lang, Dict> = { fr, en, ar };

export function translateRaw(lang: Lang, key: string): string {
  // FR is the canonical fallback so an untranslated string is at least
  // readable to the shop owner; if FR also lacks the key, the key name
  // surfaces, which is exactly what we want in dev (easy to grep).
  return DICTS[lang]?.[key] ?? DICTS.fr?.[key] ?? key;
}

export function interpolate(value: string, vars?: Record<string, string | number>): string {
  if (!vars) return value;
  return value.replace(/\{\{(\w+)\}\}/g, (_, k) => {
    const v = vars[k];
    return v === undefined || v === null ? `{{${k}}}` : String(v);
  });
}
