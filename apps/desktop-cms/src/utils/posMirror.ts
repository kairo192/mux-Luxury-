// ============================================================================
// Local catalog mirror — typed Tauri invoke wrappers.
// ============================================================================

export interface MirrorProduct {
  id: number;
  sku?: string | null;
  name_fr: string;
  name_ar?: string;
  name_en?: string;
  selling_price_dzd: number;
  purchase_cost_dzd?: number;
  main_image_url?: string | null;
  status: string;
  category_id?: number | null;
  updated_at?: string | null;
  deleted?: boolean;
}

export interface MirrorVariant {
  id: number;
  product_id: number;
  sku?: string | null;
  title: string;
  barcode?: string | null;
  price_override_dzd?: number | null;
  stock_qty: number;
  is_active?: boolean;
  updated_at?: string | null;
  deleted?: boolean;
}

export interface MirrorLookupVariant {
  variant_id: number;
  product_id: number;
  sku: string;
  barcode: string | null;
  variant_title: string;
  product_name: string;
  main_image_url: string | null;
  unit_price_dzd: number;
  stock_qty: number;
}

export interface MirrorLookupProduct {
  id: number;
  name_fr: string;
  selling_price_dzd: number;
  main_image_url: string | null;
  status: string;
  variants: MirrorLookupVariant[];
}

export interface MirrorLookupResponse {
  match_type: "variant" | "product" | "search" | "none";
  variant?: MirrorLookupVariant;
  results: MirrorLookupProduct[];
  source: "mirror";
}

export interface MirrorStatus {
  initialized: boolean;
  product_count: number;
  variant_count: number;
  variants_with_barcode: number;
  last_cursor: string | null;
  last_synced_at: string | null;
  db_path: string;
}

function invoke(): ((cmd: string, args?: Record<string, unknown>) => Promise<any>) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  if (w.__TAURI_INTERNALS__?.invoke) return w.__TAURI_INTERNALS__.invoke.bind(w.__TAURI_INTERNALS__);
  if (w.__TAURI__?.core?.invoke) return w.__TAURI__.core.invoke.bind(w.__TAURI__.core);
  return null;
}

export const isMirrorAvailable = () => invoke() !== null;

export async function mirrorInit(): Promise<MirrorStatus | null> {
  const i = invoke(); if (!i) return null;
  try { return (await i("mirror_init")) as MirrorStatus; } catch { return null; }
}

export async function mirrorStatus(): Promise<MirrorStatus | null> {
  const i = invoke(); if (!i) return null;
  try { return (await i("mirror_status")) as MirrorStatus; } catch { return null; }
}

export async function mirrorClear(): Promise<boolean> {
  const i = invoke(); if (!i) return false;
  try { await i("mirror_clear"); return true; } catch { return false; }
}

export async function mirrorUpsertProducts(rows: MirrorProduct[]): Promise<number> {
  const i = invoke(); if (!i || !rows.length) return 0;
  try { return Number(await i("mirror_upsert_products", { rows })) || 0; } catch { return 0; }
}

export async function mirrorUpsertVariants(rows: MirrorVariant[]): Promise<number> {
  const i = invoke(); if (!i || !rows.length) return 0;
  try { return Number(await i("mirror_upsert_variants", { rows })) || 0; } catch { return 0; }
}

export async function mirrorMarkSynced(cursor: string): Promise<void> {
  const i = invoke(); if (!i) return;
  try { await i("mirror_mark_synced", { cursor }); } catch { /* ignore */ }
}

export async function mirrorLookup(term: string): Promise<MirrorLookupResponse | null> {
  const i = invoke(); if (!i) return null;
  try { return (await i("mirror_lookup", { term })) as MirrorLookupResponse; } catch { return null; }
}
