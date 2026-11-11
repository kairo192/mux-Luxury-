// ============================================================================
// Catalog sync orchestration.
//
// On first run (or when the mirror is empty) pull the full snapshot; after
// that, pull /catalog/deltas with the cursor returned by the previous sync.
// Writes are batched into the Rust mirror in 500-row chunks to keep the IPC
// payload small and let the UI remain responsive.
//
// Nothing here throws — callers care only whether the sync was successful.
// ============================================================================

import { DesktopCmsApi } from "../api/adminClient";
import {
  isMirrorAvailable,
  mirrorInit,
  mirrorStatus,
  mirrorUpsertProducts,
  mirrorUpsertVariants,
  mirrorMarkSynced,
  mirrorClear,
  type MirrorProduct,
  type MirrorVariant,
  type MirrorStatus,
} from "./posMirror";

const BATCH = 500;

// The server changes its "catalog epoch" when the database is reset or
// restored. Deltas cannot describe rows that were physically deleted, so a new
// epoch means: wipe this PC's offline catalog and download it again.
const EPOCH_KEY = "luxe_pos_catalog_epoch";

function readEpoch(): string | null {
  try {
    return localStorage.getItem(EPOCH_KEY);
  } catch {
    return null;
  }
}

function writeEpoch(epoch: unknown): void {
  if (typeof epoch !== "string" || !epoch) return;
  try {
    localStorage.setItem(EPOCH_KEY, epoch);
  } catch {
    /* ignore */
  }
}

export interface SyncReport {
  ok: boolean;
  mode: "snapshot" | "delta" | "skip";
  products_upserted: number;
  variants_upserted: number;
  cursor: string | null;
  error?: string;
  elapsed_ms: number;
}

async function chunkedUpsert<T>(
  rows: T[],
  fn: (batch: T[]) => Promise<number>,
): Promise<number> {
  let total = 0;
  for (let i = 0; i < rows.length; i += BATCH) {
    total += await fn(rows.slice(i, i + BATCH));
  }
  return total;
}

export async function syncCatalog(force = false): Promise<SyncReport> {
  const start = Date.now();
  const report = (p: Partial<SyncReport>): SyncReport => ({
    ok: false, mode: "skip", products_upserted: 0, variants_upserted: 0,
    cursor: null, elapsed_ms: Date.now() - start, ...p,
  });
  if (!isMirrorAvailable()) return report({ error: "Miroir indisponible (hors Tauri)" });

  // Ensure the mirror is initialised (schema in place).
  const initStatus = await mirrorInit();
  if (!initStatus) return report({ error: "Initialisation du miroir échouée" });

  // Decide: snapshot or delta?
  const status = await mirrorStatus();
  const useDelta = !force && status && status.last_cursor && status.variant_count > 0;

  try {
    let payload: any;
    let mode: "snapshot" | "delta" = useDelta ? "delta" : "snapshot";
    if (useDelta && status?.last_cursor) {
      payload = await DesktopCmsApi.catalogDeltas(status.last_cursor);
      const known = readEpoch();
      if (typeof payload?.catalog_epoch === "string" && known && payload.catalog_epoch !== known) {
        // Database was reset / restored on the server: start over.
        await mirrorClear();
        await mirrorInit();
        payload = await DesktopCmsApi.catalogSnapshot();
        mode = "snapshot";
      }
    } else {
      if (force) {
        await mirrorClear();
        await mirrorInit();
      }
      payload = await DesktopCmsApi.catalogSnapshot();
    }
    writeEpoch(payload?.catalog_epoch);

    const products: MirrorProduct[] = Array.isArray(payload?.products) ? payload.products : [];
    const variants: MirrorVariant[] = Array.isArray(payload?.variants) ? payload.variants : [];
    const pCount = await chunkedUpsert(products, mirrorUpsertProducts);
    const vCount = await chunkedUpsert(variants, mirrorUpsertVariants);
    const cursor = typeof payload?.cursor === "string" ? payload.cursor : null;
    if (cursor) await mirrorMarkSynced(cursor);

    return report({
      ok: true,
      mode,
      products_upserted: pCount,
      variants_upserted: vCount,
      cursor,
    });
  } catch (e: any) {
    return report({ error: e?.userMessage || String(e?.message ?? e ?? "sync failed") });
  }
}

// Convenience: ensure mirror ready AND return its current status.
export async function ensureMirrorReady(): Promise<MirrorStatus | null> {
  if (!isMirrorAvailable()) return null;
  const s = await mirrorInit();
  return s;
}
