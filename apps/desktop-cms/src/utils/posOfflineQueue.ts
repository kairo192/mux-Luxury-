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

type Listener = (items: PosQueueItem[]) => void;
const listeners = new Set<Listener>();

function read(): PosQueueItem[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PosQueueItem[]) : [];
  } catch {
    return [];
  }
}

function write(items: PosQueueItem[]) {
  if (typeof localStorage !== "undefined") {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      /* quota — keep in-memory copy via listeners */
    }
  }
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
  write(read().filter((i) => i.status !== "synced"));
}

export function discardItem(clientTxnId: string): void {
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
