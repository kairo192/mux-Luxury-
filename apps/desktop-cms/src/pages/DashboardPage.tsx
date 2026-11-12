import {
  AlertCircle, AlertTriangle, ArrowUpRight, Boxes, Clock, DollarSign, Download, Landmark,
  Plus, RefreshCw, ShieldCheck, ShoppingBag, Sparkles, Tags, TrendingUp,
} from "lucide-react";
import { useT } from "../i18n";
import { RevenueTrendChart, OrderStatusDistributionChart, InventoryHealthWidget } from "../components/CmsCharts";
import { orderStatusLabel } from "../utils/orderStatus";

/** The Tableau de bord screen: today's figures, charts, stock alerts and
 *  shortcuts. Data comes from App (loaded once for the whole workspace). */
export interface DashboardPageProps {
  dashboard: any;
  categories: any[];
  onOpenTab: (tab: any) => void;
  onNewProduct: () => void;
  onRefresh: () => void;
  onExportOrdersCsv: () => void;
}

export function DashboardPage({ dashboard, categories, onOpenTab, onNewProduct, onRefresh, onExportOrdersCsv }: DashboardPageProps) {
  const t = useT();
  const setActiveTab = onOpenTab;
  const handleExportOrdersCsv = onExportOrdersCsv;
  const loadAllWorkspaceData = onRefresh;
  const openProductEditor = (_product: null) => onNewProduct();

  return (
    <div className="space-y-6">
      {/* Pro Action & Quick Launch Bar */}
      <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center text-[#D4AF62] shadow-sm">
            <Sparkles className="w-5 h-5 text-[#D4AF62]" />
          </div>
          <div>
            <h3 className="font-serif font-bold text-sm text-[#063D2E]">Panneau de Pilotage — Direction Générale</h3>
            <p className="text-[11px] text-gray-500">Maison Mus Luxury • Gestion en direct du catalogue, commandes et finances</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => { setActiveTab("products"); if (categories.length > 0) openProductEditor(null); }}
            className="px-3.5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] transition-all font-bold text-xs flex items-center gap-1.5 shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nouveau Produit</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("categories")}
            className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-[#063D2E] font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Tags className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>Catégories</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("treasury")}
            className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-[#063D2E] font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Landmark className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>Trésorerie</span>
          </button>
          <button
            type="button"
            onClick={handleExportOrdersCsv}
            className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-gray-700 font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-gray-500" />
            <span>Export CSV</span>
          </button>
          <button
            type="button"
            onClick={loadAllWorkspaceData}
            className="p-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-gray-700 font-bold transition-all shadow-sm"
            title="Actualiser les données"
          >
            <RefreshCw className="w-4 h-4 text-[#063D2E]" />
          </button>
        </div>
      </div>

      {/* 6 Key Pro KPI Cards with Lucide Icons */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-xs">
        {/* Revenue */}
        <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
          <div className="flex items-center justify-between text-gray-500">
            <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.revenue_title")}</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-800 flex items-center justify-center">
              <DollarSign className="w-4 h-4 text-emerald-700" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-[#063D2E] mt-2 tracking-tight">
            {dashboard.finance_visible === false ? "—" : Number(dashboard.total_revenue_dzd || 0).toLocaleString()} <span className="text-xs font-sans text-[#D4AF62]">{dashboard.finance_visible === false ? "" : "DA"}</span>
          </p>
          <div className="text-[10px] text-gray-400 mt-1 flex items-center gap-1">
            <TrendingUp className="w-3 h-3 text-emerald-600" />
            <span>{dashboard.finance_visible === false ? "Réservé à la direction" : `Panier moy: ${Math.round(Number(dashboard.total_revenue_dzd || 0) / Math.max(dashboard.total_orders, 1)).toLocaleString()} DA`}</span>
          </div>
        </div>

        {/* Total Orders */}
        <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
          <div className="flex items-center justify-between text-gray-500">
            <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.orders_title")}</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
              <ShoppingBag className="w-4 h-4 text-blue-600" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_orders}</p>
          <div className="text-[10px] text-blue-600 font-semibold mt-1">
            {t("dashboard_tab.orders_delivered", { count: dashboard.orders_by_status?.delivered || 0 })}
          </div>
        </div>

        {/* Active Products */}
        <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
          <div className="flex items-center justify-between text-gray-500">
            <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.active_products")}</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
              <Boxes className="w-4 h-4 text-purple-600" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_active_products ?? dashboard.published_products}</p>
          <div className="text-[10px] text-purple-600 font-semibold mt-1">
            {t("dashboard_tab.active_products_desc")}
          </div>
        </div>

        {/* Categories */}
        <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
          <div className="flex items-center justify-between text-gray-500">
            <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.categories_title")}</span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center">
              <Tags className="w-4 h-4 text-amber-700" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_categories}</p>
          <div className="text-[10px] text-gray-400 mt-1">
            {t("dashboard_tab.categories_desc")}
          </div>
        </div>

        {/* Low Stock Alert */}
        <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
          (dashboard.low_stock_only_variants ?? 0) > 0 ? "border-amber-300 bg-amber-50/30" : "border-[#063D2E]/10"
        }`}>
          <div className="flex items-center justify-between text-amber-800">
            <span className="font-bold text-[10px] uppercase tracking-wider text-amber-800">{t("dashboard_tab.low_stock_title")}</span>
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-amber-700 mt-2">{dashboard.low_stock_only_variants ?? 0}</p>
          <div className="text-[10px] text-amber-700 font-semibold mt-1">
            {t("dashboard_tab.low_stock_desc")}
          </div>
        </div>

        {/* Out of Stock Alert */}
        <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
          dashboard.out_of_stock_variants > 0 ? "border-red-300 bg-red-50/30" : "border-[#063D2E]/10"
        }`}>
          <div className="flex items-center justify-between text-red-800">
            <span className="font-bold text-[10px] uppercase tracking-wider text-red-800">{t("dashboard_tab.out_of_stock_title")}</span>
            <div className="w-8 h-8 rounded-lg bg-red-100 text-red-800 flex items-center justify-center">
              <AlertCircle className="w-4 h-4 text-red-700" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-red-700 mt-2">{dashboard.out_of_stock_variants}</p>
          <div className="text-[10px] text-red-700 font-semibold mt-1">
            {t("dashboard_tab.out_of_stock_desc")}
          </div>
        </div>
      </div>

      {/* Interactive Charts Row: Revenue Area Chart (8 cols) & Orders Donut (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7">
          {dashboard.finance_visible === false ? (
            <div className="bg-white rounded-2xl border border-[#063D2E]/10 p-5 text-xs text-gray-500">
              Les chiffres d'affaires sont réservés à la direction.
            </div>
          ) : (
            <RevenueTrendChart byDay={dashboard.revenue_by_day || []} />
          )}
        </div>
        <div className="lg:col-span-5">
          <OrderStatusDistributionChart ordersByStatus={dashboard.orders_by_status || {}} />
        </div>
      </div>

      {/* Second Visuals Row: Inventory Health (5 cols) & Recent Activity Stream (7 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 text-xs">
        <div className="lg:col-span-5">
          <InventoryHealthWidget
            totalVariants={dashboard.active_variants ?? 0}
            lowStock={dashboard.low_stock_only_variants ?? 0}
            outOfStock={dashboard.out_of_stock_variants ?? 0}
            onNavigateToProducts={() => setActiveTab("products")}
          />
        </div>

        {/* Recent Orders Stream */}
        <div className="lg:col-span-7 bg-white p-5 rounded-2xl border border-[#063D2E]/10 shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-gray-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center font-bold">
                <Clock className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-serif font-bold text-sm text-[#063D2E]">{t("dashboard_tab.recent_orders_title")}</h3>
                <p className="text-[11px] text-gray-500">{t("dashboard_tab.recent_orders_desc")}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab("orders")}
              className="text-[11px] font-bold text-[#063D2E] hover:text-[#0A5C45] flex items-center gap-1 transition"
            >
              <span>{t("dashboard_tab.view_all_orders", { count: dashboard.all_orders_count ?? dashboard.total_orders })}</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {(dashboard.recent_orders || []).length === 0 ? (
            <div className="p-8 text-center bg-[#F8F6F0] rounded-xl border border-dashed border-[#D4AF62]/40 text-gray-400">
              <p className="font-serif italic text-gray-600">{t("dashboard_tab.empty_orders")}</p>
              <p className="text-[10px] text-gray-400 mt-1">{t("dashboard_tab.empty_orders_desc")}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {(dashboard.recent_orders || []).slice(0, 5).map((ro: any) => (
                <div
                  key={ro.id}
                  className="p-3 rounded-xl bg-[#F8F6F0]/70 hover:bg-[#F8F6F0] border border-[#D4AF62]/20 flex items-center justify-between transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-0.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-mono text-[11px] font-bold">
                      #{ro.order_reference}
                    </span>
                    <div>
                      <span className="font-bold text-gray-800">{ro.customer_name}</span>
                      <span className="text-gray-400 text-[11px] ml-1.5">({ro.wilaya_name})</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-[#063D2E]">{ro.total_dzd?.toLocaleString()} DA</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
                      {orderStatusLabel(ro.status)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* System Security & Backup Status Card */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] text-white border border-[#D4AF62]/30 shadow-md flex flex-col md:flex-row items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-[#D4AF62] shrink-0 border border-[#D4AF62]/40">
            <ShieldCheck className="w-5 h-5 text-[#D4AF62]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-[#E8D4A5]">{t("dashboard_tab.security_title")}</span>
              <span className={`w-2 h-2 rounded-full ${Number(dashboard.failed_backups_count || 0) > 0 ? "bg-red-400" : "bg-emerald-400"}`} />
            </div>
            <p className="text-[11px] text-gray-300 mt-0.5">
              {dashboard.database_engine === "postgres" ? t("dashboard_tab.security_desc_pg") : t("dashboard_tab.security_desc_sqlite")}
              {Number(dashboard.failed_backups_count || 0) > 0 && (
                <span className="text-red-300 font-bold"> • {t("dashboard_tab.failed_backups", { count: dashboard.failed_backups_count })}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[11px]">
          {dashboard.last_backup ? (
            <div className="px-3 py-1.5 rounded-xl bg-white/10 border border-white/10 font-mono text-gray-300">
              {t("dashboard_tab.last_backup", { filename: dashboard.last_backup.filename })}
            </div>
          ) : (
            <span className="text-gray-400 font-mono">{t("dashboard_tab.backups_ready")}</span>
          )}
          <button
            type="button"
            onClick={() => setActiveTab("backups")}
            className="px-3.5 py-1.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold hover:brightness-105 transition"
          >
            {t("dashboard_tab.btn_manage")}
          </button>
        </div>
      </div>
    </div>
  );
}
