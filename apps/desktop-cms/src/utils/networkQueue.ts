// ============================================================================
// MUS LUXURY DESKTOP CMS — NETWORK TELEMETRY, RETRY & OFFLINE MUTATION QUEUE
// Features:
// - Live RTT / server latency tracking (X-Response-Time-Ms & client RTT)
// - Request correlation ID tracking (X-Request-ID)
// - Offline mutation queue with automatic replay on network restoration
// ============================================================================

export interface NetworkTelemetryState {
  online: boolean;
  latencyMs: number;
  lastRequestId: string;
  queuedCount: number;
  retryCount: number;
  lastSyncAt: string;
}

export interface QueuedMutationItem {
  id: string;
  path: string;
  method: string;
  body?: string;
  description: string;
  createdAt: number;
}

const QUEUE_STORAGE_KEY = "luxe_cms_offline_mutation_queue";

let telemetryState: NetworkTelemetryState = {
  online: typeof navigator !== "undefined" ? navigator.onLine !== false : true,
  latencyMs: 14,
  lastRequestId: "req_init",
  queuedCount: 0,
  retryCount: 0,
  lastSyncAt: new Date().toLocaleTimeString("fr-FR"),
};

type TelemetryListener = (state: NetworkTelemetryState) => void;
const telemetryListeners: Set<TelemetryListener> = new Set();

function emitTelemetry() {
  const snapshot = { ...telemetryState };
  telemetryListeners.forEach((fn) => fn(snapshot));
}

export function subscribeNetworkTelemetry(fn: TelemetryListener): () => void {
  telemetryListeners.add(fn);
  fn({ ...telemetryState });
  return () => {
    telemetryListeners.delete(fn);
  };
}

export function getNetworkTelemetry(): NetworkTelemetryState {
  return { ...telemetryState };
}

export function recordNetworkSample(opts: {
  online: boolean;
  latencyMs?: number;
  requestId?: string;
  retried?: boolean;
}) {
  telemetryState.online = opts.online;
  if (typeof opts.latencyMs === "number" && opts.latencyMs >= 0) {
    telemetryState.latencyMs = Math.max(1, Math.round(opts.latencyMs));
  }
  if (opts.requestId) {
    telemetryState.lastRequestId = opts.requestId;
  }
  if (opts.retried) {
    telemetryState.retryCount += 1;
  }
  if (opts.online) {
    const now = new Date();
    telemetryState.lastSyncAt = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
  }
  emitTelemetry();
}

export function getOfflineQueue(): QueuedMutationItem[] {
  if (typeof sessionStorage === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(QUEUE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveOfflineQueue(items: QueuedMutationItem[]) {
  telemetryState.queuedCount = items.length;
  if (typeof sessionStorage !== "undefined") {
    try {
      sessionStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(items));
    } catch {
      // ignore storage quota errors
    }
  }
  emitTelemetry();
}

export function enqueueOfflineMutation(item: Omit<QueuedMutationItem, "id" | "createdAt">): QueuedMutationItem {
  const current = getOfflineQueue();
  const created: QueuedMutationItem = {
    ...item,
    id: `q_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    createdAt: Date.now(),
  };
  current.push(created);
  saveOfflineQueue(current);
  return created;
}

export async function flushOfflineMutationQueue(
  executor: (item: QueuedMutationItem) => Promise<unknown>
): Promise<{ replayed: number; remaining: number }> {
  const queue = getOfflineQueue();
  if (queue.length === 0) {
    return { replayed: 0, remaining: 0 };
  }
  const remaining: QueuedMutationItem[] = [];
  let replayed = 0;
  for (const item of queue) {
    try {
      await executor(item);
      replayed += 1;
    } catch {
      remaining.push(item);
    }
  }
  saveOfflineQueue(remaining);
  return { replayed, remaining: remaining.length };
}
