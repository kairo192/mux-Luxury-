import { defineArea } from "./define";

export const dbx = defineArea("dbx", {
  "loc_sqlite": ["Fichier local sur ce poste", "Local file on this PC", "ملف محلي على هذا الجهاز"],
  "loc_pg": ["Serveur (VPS) — conteneur luxe_postgres", "Server (VPS) — luxe_postgres container", "الخادم (VPS) — حاوية luxe_postgres"],
  "c_categories": ["Catégories", "Categories", "الفئات"],
  "c_products": ["Produits", "Products", "المنتجات"],
  "c_product_variants": ["Variantes", "Variants", "المتغيرات"],
  "c_customers": ["Clients", "Customers", "العملاء"],
  "c_orders": ["Commandes en ligne", "Online orders", "الطلبات الإلكترونية"],
  "c_pos_sales": ["Ventes caisse", "Till sales", "مبيعات الصندوق"],
  "c_inventory_movements": ["Mouvements de stock", "Stock movements", "حركات المخزون"],
  "c_expenses": ["Dépenses", "Expenses", "المصاريف"],
  "c_suppliers": ["Fournisseurs", "Suppliers", "الموردون"],
  "c_admin_users": ["Comptes staff", "Staff accounts", "حسابات الموظفين"],
});
