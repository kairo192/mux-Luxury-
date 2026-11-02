// ============================================================================
// PRO DESKTOP CMS — PERSISTENT DRAFT & SESSION STATE ENGINE
// Ensures switching tabs, reloading the window, or temporary disconnects
// NEVER reset unsaved administrator work in progress.
// ============================================================================

const memoryFallback: Record<string, string> = {};

export function readDraft<T>(key: string, defaultValue: T): T {
  try {
    const raw =
      (typeof localStorage !== "undefined" ? localStorage.getItem(key) : null) ??
      memoryFallback[key] ??
      null;
    if (!raw) return defaultValue;
    return JSON.parse(raw) as T;
  } catch {
    return defaultValue;
  }
}

export function writeDraft<T>(key: string, value: T): void {
  try {
    const serialized = JSON.stringify(value);
    memoryFallback[key] = serialized;
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(key, serialized);
    }
  } catch {
    // Ignore storage quota or sandbox restrictions
  }
}

export function clearDraft(key: string): void {
  try {
    delete memoryFallback[key];
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage restrictions
  }
}
