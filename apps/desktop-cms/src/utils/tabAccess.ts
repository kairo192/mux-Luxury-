// Which screens a role may open: the same permissions the server checks for
// that screen's data. The menu hides the rest, so a cashier sees the till,
// not the accounts. (The server refuses those calls anyway.)
const TAB_PERMS: Record<string, string[]> = {
  dashboard: ["dashboard:read"],
  business: ["finance:read"],
  pos: ["pos:sell", "pos:read"],
  orders: ["orders:write"],
  customers: ["orders:write", "pos:sell"],
  products: ["products:write"],
  categories: ["categories:write"],
  inventory: ["inventory:write"],
  inventory_count: ["inventory:write"],
  low_stock: ["inventory:write"],
  stock_movements: ["inventory:write"],
  purchases: ["finance:read"],
  suppliers: ["finance:read"],
  expenses: ["finance:read"],
  treasury: ["finance:read"],
  accounting: ["finance:read"],
  sales_report: ["finance:read"],
  expense_report: ["finance:read"],
  treasury_report: ["finance:read"],
  content: ["content:write"],
  delivery_wilayas: ["content:write"],
  users: ["settings:write"],
  devices: ["devices:read"],
  fiscal: ["settings:write"],
  audit: ["settings:write"],
  backups: ["backups:write"],
};

export function canOpenTab(tab: string, permissions: string[] | undefined | null): boolean {
  const need = TAB_PERMS[tab];
  if (!need) return true;
  const have = permissions || [];
  return need.some((p) => have.includes(p));
}
