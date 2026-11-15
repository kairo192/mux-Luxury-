import {
  Archive, CheckCircle2, CheckSquare, Clock, Edit3, PackagePlus, Plus, RefreshCw, RotateCcw,
  Search, ShoppingBag, Sparkles, Tags, Trash2, X,
} from "lucide-react";
import { useT } from "../i18n";
import { notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";

export type ProductFilterTab = "all" | "published" | "draft" | "archived" | "low_stock";

/** The Produits screen: catalogue list, search, status tabs, selection and
 *  bulk actions. The catalogue and the actions live in App (the product
 *  editor, the stock screen and the dashboard use them too). */
export interface ProductsPageProps {
  products: any[];
  categories: any[];
  search: string;
  onSearchChange: (text: string) => void;
  filterTab: ProductFilterTab;
  onFilterTabChange: (tab: ProductFilterTab) => void;
  selectedIds: number[];
  onSelectedIdsChange: (ids: number[] | ((prev: number[]) => number[])) => void;
  onOpenEditor: (product: any | null, categoryId?: number) => void;
  onArchive: (productId: number) => void;
  onRestore: (productId: number) => void;
  onBulkStatus: (status: "published" | "draft" | "archived") => void;
  onAskDelete: (product: any) => void;
  onOpenTab: (tab: any) => void;
  onRefresh: () => Promise<void>;
}

export function ProductsPage(props: ProductsPageProps) {
  const t = useT();
  const {
    products,
    categories,
    search: prodSearch,
    onSearchChange: setProdSearch,
    filterTab: productFilterTab,
    onFilterTabChange: setProductFilterTab,
    selectedIds: selectedProductIds,
    onSelectedIdsChange: setSelectedProductIds,
    onOpenEditor: openProductEditor,
    onArchive: handleArchiveProduct,
    onRestore: handleRestoreProduct,
    onBulkStatus: handleBulkStatus,
    onAskDelete: setProductToDelete,
    onOpenTab: setActiveTab,
    onRefresh: loadAllWorkspaceData,
  } = props;

  const productCounts = {
    all: products.length,
    published: products.filter((p) => p.status === "published").length,
    draft: products.filter((p) => p.status === "draft").length,
    archived: products.filter((p) => p.status === "archived").length,
    low_stock: products.filter((p) => (p.total_stock ?? 0) <= 3 && p.status !== "archived").length,
  };

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      !prodSearch ||
      (p?.name_fr && p.name_fr.toLowerCase().includes(prodSearch.toLowerCase())) ||
      (p?.sku && p.sku.toLowerCase().includes(prodSearch.toLowerCase()));
    if (!matchesSearch) return false;
    if (productFilterTab === "all") return true;
    if (productFilterTab === "low_stock") return (p.total_stock ?? 0) <= 3 && p.status !== "archived";
    return p.status === productFilterTab;
  });

  return (
    <div className="space-y-6">
      {/* Pro Sub-Header Launch Bar */}
      <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center text-[#D4AF62] shadow-xs shrink-0">
            <ShoppingBag className="w-5 h-5 text-[#D4AF62]" />
          </div>
          <div>
            <h2 className="text-base font-serif font-bold text-[#063D2E]">{t("catalog.title")}</h2>
            <p className="text-xs text-gray-500">{t("catalog.subtitle")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("categories")}
            className="px-3 py-1.5 rounded-xl bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold text-xs hover:bg-[#D4AF62]/20 transition flex items-center gap-1.5"
          >
            <Tags className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>{t("catalog.btn_categories")}</span>
          </button>
          <button
            type="button"
            onClick={async () => {
              await loadAllWorkspaceData();
              notifyClientSuccess(t("catalog.sync_success_title"), t("catalog.sync_success_desc"));
            }}
            className="px-3 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition flex items-center gap-1.5 shadow-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#D4AF62]" />
            <span>{t("catalog.btn_refresh")}</span>
          </button>
        </div>
      </div>

      {/* Product Editor Launch Pad */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-[#D4AF62]/40 shadow-xs space-y-5">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center shrink-0 shadow-sm">
              <PackagePlus className="w-6 h-6 text-[#D4AF62]" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-serif font-bold text-[#063D2E]">{t("catalog.create_piece_title")}</h2>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                {t("catalog.create_piece_desc")}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { label: t("catalog.stat_products"), value: products.length, tone: "text-[#063D2E]" },
              { label: t("catalog.stat_published"), value: productCounts.published, tone: "text-emerald-700" },
              { label: t("catalog.stat_draft"), value: productCounts.draft, tone: "text-gray-600" },
              { label: t("catalog.stat_low_stock"), value: productCounts.low_stock, tone: "text-amber-700" },
            ].map((stat) => (
              <div key={stat.label} className="p-3 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30">
                <p className="text-[10px] uppercase tracking-wide text-gray-500 font-bold">{stat.label}</p>
                <p className={`text-xl font-bold font-mono ${stat.tone}`}>{stat.value}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => openProductEditor(null)}
              disabled={categories.length === 0}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-xs hover:brightness-105 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-4 h-4" />
              <span>{t("catalog.btn_new_product")}</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("categories")}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-[#D4AF62]/60 text-[#063D2E] font-bold hover:bg-[#F8F6F0] transition"
            >
              <Tags className="w-4 h-4" />
              <span>{t("catalog.btn_attributes_cats")}</span>
            </button>
          </div>
          {categories.length === 0 && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              {t("catalog.category_required_banner")}
            </p>
          )}
        </div>

        <div className="bg-[#063D2E] p-6 rounded-2xl border border-[#D4AF62]/40 text-[#E8D4A5] space-y-3">
          <p className="font-serif font-bold text-base flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#D4AF62]" />
            <span>{t("catalog.best_practices_title")}</span>
          </p>
          <ul className="space-y-2 text-[11px] leading-relaxed text-white/80">
            <li className="flex gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
              <span>{t("catalog.best_practices_1")}</span>
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
              <span>{t("catalog.best_practices_2")}</span>
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
              <span>{t("catalog.best_practices_3")}</span>
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
              <span>{t("catalog.best_practices_4")}</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Product Catalogue Table & Tools */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-base font-serif font-bold text-[#063D2E]">
              {t("catalog.title_list")} ({filteredProducts.length})
            </h3>
            <div className="flex flex-wrap rounded-xl bg-[#F8F6F0] p-1 border border-[#D4AF62]/40 text-[11px]">
              {[
                { key: "all", label: `${t("catalog.filter_all")} (${productCounts.all})` },
                { key: "published", label: `${t("catalog.filter_published")} (${productCounts.published})` },
                { key: "draft", label: `${t("catalog.filter_draft")} (${productCounts.draft})` },
                { key: "archived", label: `${t("catalog.filter_archived")} (${productCounts.archived})` },
                { key: "low_stock", label: `${t("catalog.filter_low_stock")} (${productCounts.low_stock})` },
              ].map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setProductFilterTab(tab.key as any)}
                  className={`px-3 py-1 rounded-lg font-bold transition ${
                    productFilterTab === tab.key
                      ? "bg-[#063D2E] text-[#D4AF62] shadow-xs"
                      : "text-gray-600 hover:text-black"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
              <input
                data-products-search
                value={prodSearch}
                onChange={(e) => setProdSearch(e.target.value)}
                placeholder={t("catalog.search_placeholder")}
                className="pl-8 pr-3 py-1.5 border rounded-xl w-60 bg-[#F8F6F0] focus:bg-white focus:border-[#063D2E] outline-none transition"
              />
              {prodSearch && (
                <button aria-label="Effacer la recherche"
                  type="button"
                  onClick={() => setProdSearch("")}
                  className="absolute right-2.5 top-2 text-gray-400 hover:text-gray-700 text-xs font-bold"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Table or Empty State */}
        {filteredProducts.length === 0 ? (
          products.length === 0 ? (
            /* Empty State: Zero Products in DB */
            <div className="p-12 text-center bg-[#F8F6F0]/60 rounded-2xl border-2 border-dashed border-[#D4AF62]/40 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center mx-auto text-[#D4AF62] shadow-md">
                <PackagePlus className="w-8 h-8 text-[#D4AF62]" />
              </div>
              <div className="max-w-md mx-auto space-y-1">
                <h4 className="text-lg font-serif font-bold text-[#063D2E]">{t("catalog.empty_title")}</h4>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {t("catalog.empty_desc")}
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    if (categories.length === 0) {
                      setActiveTab("categories");
                      notifyClientWarning(
                        t("catalog.category_required_title"),
                        t("catalog.category_required_desc")
                      );
                    } else {
                      openProductEditor(null);
                    }
                  }}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xs shadow-xs hover:bg-[#084e3b] transition"
                >
                  <Plus className="w-4 h-4 text-[#D4AF62]" />
                  <span>{t("catalog.create_first_product")}</span>
                </button>
                {categories.length === 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveTab("categories")}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-[#D4AF62] text-[#063D2E] font-bold text-xs hover:bg-[#F8F6F0] transition"
                  >
                    <Tags className="w-4 h-4 text-[#063D2E]" />
                    <span>{t("catalog.configure_categories")}</span>
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* Empty State: Filter Returned No Products */
            <div className="p-10 text-center bg-gray-50 rounded-2xl border border-gray-200 space-y-3">
              <Search className="w-10 h-10 text-gray-300 mx-auto" />
              <div>
                <p className="font-bold text-gray-700 text-sm">{t("catalog.no_match_title")}</p>
                {prodSearch && <p className="text-xs text-gray-500 mt-0.5">{t("catalog.no_match_desc", { query: prodSearch })}</p>}
              </div>
              <button
                type="button"
                onClick={() => {
                  setProdSearch("");
                  setProductFilterTab("all");
                }}
                className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition"
              >
                {t("catalog.reset_filter")}
              </button>
            </div>
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#063D2E] text-[#E8D4A5]">
                  <th className="p-2.5 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={filteredProducts.length > 0 && selectedProductIds.length === filteredProducts.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedProductIds(filteredProducts.map((p) => p.id));
                        } else {
                          setSelectedProductIds([]);
                        }
                      }}
                      className="rounded text-[#063D2E] w-4 h-4 cursor-pointer"
                    />
                  </th>
                  <th className="p-2.5">ID / SKU</th>
                  <th className="p-2.5">{t("catalog.th_product")}</th>
                  <th className="p-2.5 text-right">Prix Achat</th>
                  <th className="p-2.5 text-right">{t("catalog.th_selling_price")}</th>
                  <th className="p-2.5 text-right">Marge</th>
                  <th className="p-2.5 text-center">Taux</th>
                  <th className="p-2.5 text-center">{t("catalog.th_stock_variants")}</th>
                  <th className="p-2.5 text-center">{t("catalog.th_status")}</th>
                  <th className="p-2.5 text-right">{t("catalog.th_actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredProducts.map((p) => {
                  const cost = p.purchase_cost_dzd || 0;
                  const sell = p.selling_price_dzd || 0;
                  const profit = sell - cost;
                  const marginPct = sell > 0 ? ((profit / sell) * 100).toFixed(1) : "0.0";
                  const stock = p.total_stock ?? 0;
                  const isSelected = selectedProductIds.includes(p.id);
                  const cat = categories.find((c) => c.id === p.category_id);
                  return (
                    <tr
                      key={p.id}
                      className={`transition-colors ${isSelected ? "bg-amber-50/60" : "hover:bg-gray-50/80"}`}
                    >
                      <td className="p-2.5 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedProductIds([...selectedProductIds, p.id]);
                            } else {
                              setSelectedProductIds(selectedProductIds.filter((id) => id !== p.id));
                            }
                          }}
                          className="rounded text-[#063D2E] w-4 h-4 cursor-pointer"
                        />
                      </td>
                      <td className="p-2.5 font-mono">
                        <span className="font-bold text-[#063D2E]">#{p.id}</span>
                        <div className="text-[11px] text-gray-500 font-bold">{p.sku}</div>
                      </td>
                      <td className="p-2.5">
                        <div className="font-bold text-[#063D2E] text-sm">{p.name_fr}</div>
                        {cat && (
                          <span className="inline-block mt-0.5 px-2 py-0.5 rounded-full bg-[#F8F6F0] text-gray-600 border border-[#D4AF62]/30 text-[10px] font-semibold">
                            {cat.name_fr}
                          </span>
                        )}
                      </td>
                      <td className="p-2.5 text-right font-mono text-gray-500">{cost.toLocaleString()} DA</td>
                      <td className="p-2.5 text-right font-extrabold text-[#063D2E] font-mono text-sm">{sell.toLocaleString()} DA</td>
                      <td className="p-2.5 text-right font-bold text-emerald-700 font-mono">+{profit.toLocaleString()} DA</td>
                      <td className="p-2.5 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                            Number(marginPct) >= 40
                              ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                              : Number(marginPct) >= 20
                              ? "bg-blue-100 text-blue-900 border border-blue-300"
                              : "bg-amber-100 text-amber-900 border border-amber-300"
                          }`}
                        >
                          {marginPct}%
                        </span>
                      </td>
                      <td className="p-2.5 text-center font-bold">
                        {stock > 3 ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px]">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            <span>{stock} en stock</span>
                          </span>
                        ) : stock > 0 ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 text-[11px]">
                            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                            <span>Faible ({stock})</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-800 border border-rose-300 text-[11px]">
                            <span className="w-2 h-2 rounded-full bg-rose-500" />
                            <span>{t("preview.out_of_stock")}</span>
                          </span>
                        )}
                      </td>
                      <td className="p-2.5 text-center">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
                            p.status === "published"
                              ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                              : p.status === "archived"
                              ? "bg-amber-100 text-amber-900 border border-amber-300"
                              : "bg-gray-100 text-gray-800 border border-gray-300"
                          }`}
                        >
                          {p.status === "published" ? (
                            <>
                              <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                              <span>{t("catalog.badge_published")}</span>
                            </>
                          ) : p.status === "archived" ? (
                            <>
                              <Archive className="w-3 h-3 text-amber-700" />
                              <span>{t("catalog.badge_archived")}</span>
                            </>
                          ) : (
                            <>
                              <Clock className="w-3 h-3 text-gray-600" />
                              <span>{t("catalog.badge_draft")}</span>
                            </>
                          )}
                        </span>
                      </td>
                      <td className="p-2.5 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openProductEditor(p)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold hover:bg-[#D4AF62]/20 transition"
                          title={t("catalog.btn_edit")}
                        >
                          <Edit3 className="w-3 h-3 text-[#063D2E]" />
                          <span>{t("catalog.btn_edit")}</span>
                        </button>
                        {p.status !== "archived" ? (
                          <button
                            type="button"
                            onClick={() => handleArchiveProduct(p.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 font-bold hover:bg-amber-100 transition"
                            title={t("catalog.btn_archive")}
                          >
                            <Archive className="w-3 h-3 text-amber-800" />
                            <span>{t("catalog.btn_archive")}</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleRestoreProduct(p.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold hover:bg-emerald-100 transition"
                            title={t("catalog.btn_restore")}
                          >
                            <RotateCcw className="w-3 h-3 text-emerald-800" />
                            <span>{t("catalog.btn_restore")}</span>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setProductToDelete(p);
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 font-bold hover:bg-red-100 transition shadow-xs"
                          title={t("catalog.btn_delete")}
                        >
                          <Trash2 className="w-3 h-3 text-red-700" />
                          <span>{t("catalog.btn_delete")}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Floating Batch Action Dock */}
        {selectedProductIds.length > 0 && (
          <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40 bg-[#063D2E] text-white px-5 py-3 rounded-2xl shadow-2xl border-2 border-[#D4AF62] flex items-center gap-4 animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-[#D4AF62]" />
              <span className="font-bold text-xs text-[#E8D4A5]">
                {t("catalog.bulk_selected", { count: selectedProductIds.length })}
              </span>
            </div>
            <div className="h-4 w-px bg-white/20" />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleBulkStatus("published")}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-xs transition"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{t("catalog.bulk_publish")}</span>
              </button>
              <button
                type="button"
                onClick={() => handleBulkStatus("archived")}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition"
              >
                <Archive className="w-3.5 h-3.5" />
                <span>{t("catalog.bulk_archive")}</span>
              </button>
              <button aria-label="Tout désélectionner"
                type="button"
                onClick={() => setSelectedProductIds([])}
                className="p-1.5 rounded-lg text-white/60 hover:text-white transition"
                title="Désélectionner tout"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
