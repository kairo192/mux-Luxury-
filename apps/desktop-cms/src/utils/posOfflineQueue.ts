// ===========================================================================
// DURABLE OFFLINE POS SALE QUEUE
// Survives app/computer restarts (localStorage, not sessionStorage). Each sale
// carries a unique client_txn_id so the backend /admin/pos/sync endpoint is
// idempotent — a sale is never synced twice. Items keep an explicit state:
//   pending  — created offline, awaiting sync
//   synced   — accepted by the server (created or recognised as duplicate)
//   conflict — server rejected on a business rule (e.g. stock no longer available)
//   failed   — transient/unexpected error; eligible for retry
// Conflicts/failures are NEVER silently discarded — they stay for the cashier.
// ===========================================================================

export type PosQueueStatus = "pending" | "synced" | "conflict" | "failed";

export interface PosSalePayload {
  items: Array<{ variant_id: number; quantity: number; line_discount_dzd?: number }>;
  payments: Array<{ method: string; amount_dzd: number; tendered_dzd?: number }>;
  customer_id?: number | null;
  order_discount_dzd?: number;
  notes?: string;
}

export interface PosQueueItem {
  client_txn_id: string;
  type: "sale";
  created_at: string; // ISO, local creation time
  register_session_id?: number | null;
  payload: PosSalePayload;
  total_dzd: number;
  status: PosQueueStatus;
  error?: string | null;
  reason?: string | null;
  attempts: number;
  sale_reference?: string | null;
}

export interface SyncSummary {
  created: number;
  duplicate: number;
  conflict: number;
  failed: number;
}

const STORAGE_KEY = "luxe_pos_offline_queue";

interface OfflineQueueRow {
  client_txn_id: string;
  type: string;
  created_at: string;
  register_session_id?: number | null;
  payload_json: string;
  total_dzd: number;
  status: string;
  error?: string | null;
  reason?: string | null;
  attempts: number;
  sale_reference?: string | null;
  updated_at: string;
}

function itemToRow(item: PosQueueItem): OfflineQueueRow {
  return {
    client_txn_id: item.client_txn_id,
    type: item.type || "sale",
    created_at: item.created_at,
    register_session_id: item.register_session_id ?? null,
    payload_json: JSON.stringify(item.payload),
    total_dzd: item.total_dzd,
    status: item.status,
    error: item.error ?? null,
    reason: item.reason ?? null,
    attempts: item.attempts,
    sale_reference: item.sale_reference ?? null,
    updated_at: new Date().toISOString(),
  };
}

function rowToItem(row: OfflineQueueRow): PosQueueItem {
  let payload: PosSalePayload;
  try {
    payload = JSON.parse(row.payload_json);
  } catch {
    payload = { items: [], payments: [] };
  }
  return {
    client_txn_id: row.client_txn_id,
    type: (row.type as any) || "sale",
    created_at: row.created_at,
    register_session_id: row.register_session_id ?? null,
    payload,
    total_dzd: row.total_dzd,
    status: (row.status as PosQueueStatus) || "pending",
    error: row.error ?? null,
    reason: row.reason ?? null,
    attempts: row.attempts,
    sale_reference: row.sale_reference ?? null,
  };
}

async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T | null> {
  if (typeof window === "undefined") return null;
  const isTauri = Boolean((window as any).__TAURI_INTERNALS__);
  if (!isTauri) return null;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<T>(cmd, args);
  } catch (err) {
    console.warn(`[posOfflineQueue] ${cmd} error:`, err);
    return null;
  }
}

type Listener = (items: PosQueueItem[]) => void;
const listeners = new Set<Listener>();

let memoryQueue: PosQueueItem[] = [];
let queueInitialized = false;

function readLocal(): PosQueueItem[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PosQueueItem[]) : [];
  } catch {
    return [];
  }
}

function writeLocal(items: PosQueueItem[]) {
  if (typeof localStorage !== "undefined") {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      /* quota */
    }
  }
}

export async function initPosQueue(): Promise<PosQueueItem[]> {
  const localItems = readLocal();
  const rows = await tauriInvoke<OfflineQueueRow[]>("pos_queue_list");
  if (rows !== null) {
    // If we had pending items in localStorage, migrate them to SQLite
    if (localItems.length > 0) {
      await tauriInvoke("pos_queue_upsert_batch", { items: localItems.map(itemToRow) });
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
      const refreshed = await tauriInvoke<OfflineQueueRow[]>("pos_queue_list");
      memoryQueue = (refreshed || []).map(rowToItem);
    } else {
      memoryQueue = rows.map(rowToItem);
    }
  } else {
    memoryQueue = localItems;
  }
  queueInitialized = true;
  listeners.forEach((fn) => fn([...memoryQueue]));
  return memoryQueue;
}

// Auto-initialize in background on module load
if (typeof window !== "undefined") {
  void initPosQueue();
}

function read(): PosQueueItem[] {
  if (!queueInitialized && memoryQueue.length === 0) {
    memoryQueue = readLocal();
  }
  return memoryQueue;
}

function write(items: PosQueueItem[]) {
  memoryQueue = items;
  writeLocal(items);
  void tauriInvoke("pos_queue_upsert_batch", { items: items.map(itemToRow) });
  listeners.forEach((fn) => fn([...items]));
}

export function subscribePosQueue(fn: Listener): () => void {
  fn(read());
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function getPosQueue(): PosQueueItem[] {
  return read();
}

export function posQueueCounts(): { pending: number; conflict: number; failed: number; total: number } {
  const items = read();
  return {
    pending: items.filter((i) => i.status === "pending").length,
    conflict: items.filter((i) => i.status === "conflict").length,
    failed: items.filter((i) => i.status === "failed").length,
    total: items.length,
  };
}

function newTxnId(): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `postxn-${Date.now()}-${rand}`;
}

export function enqueuePosSale(
  payload: PosSalePayload,
  total_dzd: number,
  register_session_id?: number | null
): PosQueueItem {
  const item: PosQueueItem = {
    client_txn_id: newTxnId(),
    type: "sale",
    created_at: new Date().toISOString().slice(0, 19),
    register_session_id: register_session_id ?? null,
    payload,
    total_dzd,
    status: "pending",
    attempts: 0,
    error: null,
    sale_reference: null,
  };
  const items = read();
  items.push(item);
  write(items);
  return item;
}

export function removeSyncedItems(): void {
  void tauriInvoke("pos_queue_clear_synced");
  write(read().filter((i) => i.status !== "synced"));
}

export function discardItem(clientTxnId: string): void {
  void tauriInvoke("pos_queue_remove", { clientTxnId });
  write(read().filter((i) => i.client_txn_id !== clientTxnId));
}

export function retryItem(clientTxnId: string): void {
  write(read().map((i) => (i.client_txn_id === clientTxnId ? { ...i, status: "pending", error: null } : i)));
}

// Items that should be sent to the server (pending + previously failed, not conflicts).
function syncableItems(): PosQueueItem[] {
  return read().filter((i) => i.status === "pending" || i.status === "failed");
}

interface SyncResultRow {
  client_txn_id: string;
  status: "created" | "duplicate" | "conflict" | "failed";
  sale_reference?: string;
  error?: string;
  reason?: string;
}

/**
 * Flush all syncable items via the provided batch API call. Updates each item's
 * state from the server result. Returns the server summary (or null if nothing
 * to sync / the call failed entirely — items stay pending for the next attempt).
 */
export async function syncPosQueue(
  batchApi: (operations: Array<{ client_txn_id: string; type: "sale"; register_session_id?: number | null; created_at_client?: string; payload: PosSalePayload }>) => Promise<{ results: SyncResultRow[]; summary: SyncSummary }>
): Promise<SyncSummary | null> {
  const toSync = syncableItems();
  if (toSync.length === 0) return { created: 0, duplicate: 0, conflict: 0, failed: 0 };

  let response: { results: SyncResultRow[]; summary: SyncSummary };
  try {
    response = await batchApi(
      toSync.map((i) => ({
        client_txn_id: i.client_txn_id,
        type: "sale",
        register_session_id: i.register_session_id ?? undefined,
        created_at_client: i.created_at,
        payload: i.payload,
      }))
    );
  } catch {
    // Whole batch failed (offline/server down) — bump attempts, keep pending.
    write(read().map((i) => (i.status === "pending" || i.status === "failed" ? { ...i, attempts: i.attempts + 1 } : i)));
    return null;
  }

  const byTxn = new Map(response.results.map((r) => [r.client_txn_id, r]));
  const updated = read().map((i) => {
    const r = byTxn.get(i.client_txn_id);
    if (!r) return i;
    if (r.status === "created" || r.status === "duplicate") {
      return { ...i, status: "synced" as PosQueueStatus, sale_reference: r.sale_reference || i.sale_reference, error: null };
    }
    if (r.status === "conflict") {
      return { ...i, status: "conflict" as PosQueueStatus, error: r.error || "Conflit", reason: r.reason || null, attempts: i.attempts + 1 };
    }
    return { ...i, status: "failed" as PosQueueStatus, error: r.error || "Échec", attempts: i.attempts + 1 };
  });
  write(updated);
  return response.summary;
}
