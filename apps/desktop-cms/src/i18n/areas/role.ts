import { defineArea } from "./define";

export const role = defineArea("role", {
  "super_admin": ["Propriétaire / Super Admin", "Owner / Super admin", "المالك / المدير العام"],
  "admin": ["Administrateur", "Administrator", "المدير"],
  "product_manager": ["Gestion produits", "Product manager", "مسؤول المنتجات"],
  "order_manager": ["Gestion commandes", "Order manager", "مسؤول الطلبات"],
  "inventory_manager": ["Gestion stock", "Inventory manager", "مسؤول المخزون"],
  "cashier": ["Caissier", "Cashier", "أمين الصندوق"],
  "readonly": ["Lecture seule", "Read-only", "قراءة فقط"],
  "desc_super_admin": ["Propriétaire — toute la plateforme et la sécurité", "Owner — the whole platform and security", "المالك — المنصة كلها والأمان"],
  "desc_admin": ["Administrateur — catalogue, commandes, contenu et rapports", "Administrator — catalogue, orders, content and reports", "المدير — الكتالوج والطلبات والمحتوى والتقارير"],
  "desc_product_manager": ["Gestion produits — catégories, caractéristiques, produits et photos", "Product manager — categories, characteristics, products and photos", "مسؤول المنتجات — الفئات والخصائص والمنتجات والصور"],
  "desc_order_manager": ["Gestion commandes — commandes, contacts clients et statuts de livraison", "Order manager — orders, customer contacts and delivery statuses", "مسؤول الطلبات — الطلبات ومعلومات الزبائن وحالات التوصيل"],
  "desc_inventory_manager": ["Gestion stock — niveaux de stock et mouvements", "Inventory manager — stock levels and movements", "مسؤول المخزون — مستويات المخزون وحركاته"],
  "desc_cashier": ["Caissier — vendre et gérer la caisse", "Cashier — sell and run the cash register", "أمين الصندوق — البيع وإدارة الصندوق"],
  "desc_readonly": ["Lecture seule — tableau de bord, catalogue et résumés des commandes", "Read-only — dashboard, catalogue and order summaries", "قراءة فقط — لوحة التحكم والكتالوج وملخصات الطلبات"],
});
