import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  LayoutDashboard,
  BarChart3,
  ScanLine,
  ShoppingCart,
  Users,
  ShoppingBag,
  Tags,
  Boxes,
  ClipboardCheck,
  AlertTriangle,
  ArrowLeftRight,
  PackageCheck,
  Truck,
  Receipt,
  Wallet,
  Calculator,
  FileBarChart,
  FileSpreadsheet,
  PieChart,
  Palette,
  MapPin,
  UserCog,
  HardDrive,
  Scale,
  History,
  ShieldCheck,
  ChevronDown,
  ChevronsLeft,
  Search,
  X,
  type LucideIcon,
  Store,
} from "lucide-react";
import { useT } from "../i18n";

// ---------------------------------------------------------------------------
// Grouped, collapsible sidebar for the 26 CMS modules. Ids are the same
// CmsTab values App.tsx already uses, so selecting an item only calls the
// existing setActiveTab — no module behaviour changes.
// ---------------------------------------------------------------------------

interface NavItem {
  id: string;
  labelKey: string;
  icon: LucideIcon;
}

interface NavGroup {
  id: string;
  labelKey: string;
  items: NavItem[];
}

export const CMS_NAV_GROUPS: NavGroup[] = [
  {
    id: "overview",
    labelKey: "nav.group.overview",
    items: [
      { id: "dashboard", labelKey: "sidebar.dashboard", icon: LayoutDashboard },
      { id: "business", labelKey: "sidebar.business_intelligence", icon: BarChart3 },
    ],
  },
  {
    id: "sales",
    labelKey: "nav.group.sales",
    items: [
      { id: "pos", labelKey: "sidebar.pos", icon: ScanLine },
      { id: "orders", labelKey: "sidebar.orders", icon: ShoppingCart },
      { id: "customers", labelKey: "sidebar.customers", icon: Users },
    ],
  },
  {
    id: "catalog",
    labelKey: "nav.group.catalog",
    items: [
      { id: "products", labelKey: "sidebar.products", icon: ShoppingBag },
      { id: "shop_items", labelKey: "shop.menu", icon: Store },
      { id: "categories", labelKey: "sidebar.categories", icon: Tags },
    ],
  },
  {
    id: "stock",
    labelKey: "nav.group.stock",
    items: [
      { id: "inventory", labelKey: "sidebar.inventory", icon: Boxes },
      { id: "inventory_count", labelKey: "sidebar.inventory_count", icon: ClipboardCheck },
      { id: "low_stock", labelKey: "sidebar.low_stock", icon: AlertTriangle },
      { id: "stock_movements", labelKey: "sidebar.stock_movements", icon: ArrowLeftRight },
      { id: "purchases", labelKey: "sidebar.purchases", icon: PackageCheck },
      { id: "suppliers", labelKey: "sidebar.suppliers", icon: Truck },
    ],
  },
  {
    id: "finance",
    labelKey: "nav.group.finance",
    items: [
      { id: "expenses", labelKey: "sidebar.expenses", icon: Receipt },
      { id: "treasury", labelKey: "sidebar.treasury", icon: Wallet },
      { id: "accounting", labelKey: "sidebar.accounting", icon: Calculator },
    ],
  },
  {
    id: "reports",
    labelKey: "nav.group.reports",
    items: [
      { id: "sales_report", labelKey: "sidebar.sales_report", icon: FileBarChart },
      { id: "expense_report", labelKey: "sidebar.expense_report", icon: FileSpreadsheet },
      { id: "treasury_report", labelKey: "sidebar.treasury_report", icon: PieChart },
    ],
  },
  {
    id: "store",
    labelKey: "nav.group.store",
    items: [
      { id: "content", labelKey: "sidebar.content", icon: Palette },
      { id: "delivery_wilayas", labelKey: "sidebar.delivery_wilayas", icon: MapPin },
    ],
  },
  {
    id: "admin",
    labelKey: "nav.group.admin",
    items: [
      { id: "users", labelKey: "sidebar.users_roles", icon: UserCog },
      { id: "devices", labelKey: "sidebar.devices", icon: HardDrive },
      { id: "fiscal", labelKey: "sidebar.fiscal_settings", icon: Scale },
      { id: "audit", labelKey: "sidebar.audit_log", icon: History },
      { id: "backups", labelKey: "sidebar.backups", icon: ShieldCheck },
    ],
  },
];

const COLLAPSED_KEY = "luxe_cms_sidebar_collapsed";
const FOLDED_GROUPS_KEY = "luxe_cms_sidebar_folded_groups";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode / quota — UI preference only */
  }
}

// Accent- and case-insensitive match so "depense" finds "Dépenses".
function normalize(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

interface CmsSidebarProps {
  activeTab: string;
  onSelect: (id: string) => void;
  badges?: Partial<Record<string, number>>;
  /** Screens this person's role may open (others are not shown). */
  canOpen?: (id: string) => boolean;
}

export const CmsSidebar: React.FC<CmsSidebarProps> = ({ activeTab, onSelect, badges = {}, canOpen }) => {
  const t = useT();
  const [collapsed, setCollapsed] = useState<boolean>(() => readJson(COLLAPSED_KEY, false));
  const [folded, setFolded] = useState<string[]>(() => readJson(FOLDED_GROUPS_KEY, []));
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => writeJson(COLLAPSED_KEY, collapsed), [collapsed]);
  useEffect(() => writeJson(FOLDED_GROUPS_KEY, folded), [folded]);

  // Ctrl/Cmd+K jumps to the module finder from anywhere in the CMS.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setCollapsed(false);
        requestAnimationFrame(() => searchRef.current?.focus());
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Keep the active module visible when it changes from outside the sidebar
  // (dashboard shortcuts, Alt+number) or when the panel is collapsed.
  const navRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = navRef.current?.querySelector('[aria-current="page"]') as HTMLElement | null;
    el?.scrollIntoView({ block: "nearest" });
  }, [activeTab, collapsed]);

  const q = normalize(query.trim());
  const allowedGroups = useMemo(
    () =>
      CMS_NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((it) => !canOpen || canOpen(it.id)) })).filter(
        (g) => g.items.length > 0
      ),
    [canOpen]
  );
  const visibleGroups = useMemo(() => {
    if (!q) return allowedGroups;
    return allowedGroups.map((g) => ({
      ...g,
      items: g.items.filter((it) => normalize(t(it.labelKey)).includes(q) || normalize(t(g.labelKey)).includes(q)),
    })).filter((g) => g.items.length > 0);
  }, [q, t, allowedGroups]);

  const flatMatches = visibleGroups.flatMap((g) => g.items);

  const select = (id: string) => {
    onSelect(id);
    if (query) setQuery("");
  };

  const toggleGroup = (id: string) =>
    setFolded((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));

  return (
    <aside
      aria-label={t("misc.navigation")}
      className={`relative shrink-0 flex flex-col bg-gradient-to-b from-[#02291F] via-[#063D2E] to-[#011C15] text-[#E8D4A5] border-e border-[#D4AF62]/20 transition-[width] duration-200 motion-reduce:transition-none ${
        collapsed ? "w-[76px]" : "w-[264px]"
      }`}
    >
      {/* Soft gold glow so the panel doesn't read as a flat block */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(ellipse_at_top,rgba(212,175,98,0.16),transparent_70%)]" />

      {/* Finder */}
      <div className={`relative px-3 pt-4 pb-3 ${collapsed ? "flex justify-center" : ""}`}>
        {collapsed ? (
          <button
            type="button"
            onClick={() => {
              setCollapsed(false);
              requestAnimationFrame(() => searchRef.current?.focus());
            }}
            title={t("nav.search_placeholder")}
            className="w-11 h-11 rounded-xl bg-white/5 hover:bg-white/10 border border-[#D4AF62]/20 flex items-center justify-center text-[#D4AF62] transition"
          >
            <Search className="w-4 h-4" />
          </button>
        ) : (
          <div className="relative">
            <Search className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#D4AF62]/80" />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && flatMatches[0]) select(flatMatches[0].id);
                if (e.key === "Escape") {
                  setQuery("");
                  (e.target as HTMLInputElement).blur();
                }
              }}
              placeholder={t("nav.search_placeholder")}
              className="w-full h-10 ps-9 pe-14 rounded-xl bg-white/[0.06] border border-[#D4AF62]/20 text-sm text-white placeholder:text-[#E8D4A5]/50 outline-none focus:border-[#D4AF62]/70 focus:bg-white/10 transition"
            />
            {query ? (
              <button aria-label={t("misc.clear_search")}
                type="button"
                onClick={() => setQuery("")}
                className="absolute end-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-md flex items-center justify-center text-[#E8D4A5]/70 hover:text-white hover:bg-white/10"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            ) : (
              <kbd className="absolute end-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded-md border border-[#D4AF62]/25 text-[10px] font-mono text-[#E8D4A5]/60">
                Ctrl K
              </kbd>
            )}
          </div>
        )}
      </div>

      {/* Groups */}
      <nav ref={navRef} className="relative flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4 space-y-1 [scrollbar-width:thin] [scrollbar-color:rgba(212,175,98,0.3)_transparent]">
        {visibleGroups.length === 0 && (
          <p className="px-3 py-6 text-center text-xs text-[#E8D4A5]/60">{t("nav.no_match")}</p>
        )}

        {visibleGroups.map((group) => {
          const containsActive = group.items.some((it) => it.id === activeTab);
          // While searching, or when collapsed to icons, every group is open.
          const isOpen = collapsed || !!q || containsActive || !folded.includes(group.id);
          return (
            <div key={group.id} className="pt-2 first:pt-0">
              {collapsed ? (
                <div className="mx-auto my-2 h-px w-8 bg-[#D4AF62]/20 first:hidden" />
              ) : (
                <button
                  type="button"
                  onClick={() => toggleGroup(group.id)}
                  className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-[0.14em] text-[#D4AF62]/75 hover:text-[#D4AF62] transition"
                  aria-expanded={isOpen}
                >
                  <span>{t(group.labelKey)}</span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-transform duration-200 motion-reduce:transition-none ${isOpen ? "" : "-rotate-90 rtl:rotate-90"}`}
                  />
                </button>
              )}

              {isOpen && (
                <ul className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = item.id === activeTab;
                    const badge = badges[item.id] || 0;
                    const label = t(item.labelKey);
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          onClick={() => select(item.id)}
                          title={collapsed ? label : undefined}
                          aria-current={active ? "page" : undefined}
                          className={`group relative w-full flex items-center gap-3 rounded-xl text-start text-[13px] transition-colors duration-150 ${
                            collapsed ? "justify-center h-11" : "px-2.5 h-10"
                          } ${
                            active
                              ? "bg-gradient-to-r rtl:bg-gradient-to-l from-[#D4AF62]/25 to-[#D4AF62]/5 text-white font-semibold"
                              : "text-[#E8D4A5]/85 hover:bg-white/[0.06] hover:text-white"
                          }`}
                        >
                          {active && (
                            <span className="absolute inset-y-2 start-0 w-1 rounded-full bg-[#D4AF62] shadow-[0_0_10px_rgba(212,175,98,0.7)]" />
                          )}
                          <span
                            className={`relative shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                              active
                                ? "bg-gradient-to-br from-[#E8D4A5] to-[#D4AF62] text-[#02291F] shadow-luxe-gold"
                                : "bg-white/[0.05] text-[#D4AF62] group-hover:bg-white/10"
                            }`}
                          >
                            <Icon className="w-4 h-4" />
                            {collapsed && badge > 0 && (
                              <span className="absolute -top-1 -end-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
                                {badge > 99 ? "99+" : badge}
                              </span>
                            )}
                          </span>
                          {!collapsed && (
                            <>
                              <span className="flex-1 truncate">{label}</span>
                              {badge > 0 && (
                                <span
                                  className={`min-w-[22px] h-5 px-1.5 rounded-full text-[10px] font-bold flex items-center justify-center ${
                                    active ? "bg-[#D4AF62] text-[#02291F]" : "bg-red-500/90 text-white"
                                  }`}
                                >
                                  {badge > 99 ? "99+" : badge}
                                </span>
                              )}
                            </>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="relative border-t border-[#D4AF62]/15 p-3">
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? t("nav.expand") : t("nav.collapse")}
          className={`w-full h-10 rounded-xl flex items-center gap-2 text-xs font-semibold text-[#E8D4A5]/75 hover:text-white hover:bg-white/[0.06] transition ${
            collapsed ? "justify-center" : "px-3"
          }`}
        >
          <ChevronsLeft
            className={`w-4 h-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none ${
              collapsed ? "rotate-180 rtl:rotate-0" : "rtl:rotate-180"
            }`}
          />
          {!collapsed && <span>{t("nav.collapse")}</span>}
        </button>
      </div>
    </aside>
  );
};
