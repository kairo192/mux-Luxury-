// ============================================================================
// MUS LUXURY DESKTOP CMS — NOTIFICATION HISTORY + NATIVE OS BRIDGE
//
// Listens to the clientNotifier bus and:
//   1. keeps a short history (bell panel in the header) with unread count,
//   2. raises a native Windows / OS notification for items flagged `os: true`
//      (new online orders, ready updates, background sync results) — only
//      while the CMS window is NOT in front, so the cashier is never spammed.
//
// History lives in sessionStorage: it survives a reload but not a restart,
// because entries can carry customer names from order alerts.
// ============================================================================

import { subscribeClientNotifications, ClientNotificationItem } from "./clientNotifier";
import { getTauriInvoke } from "./posHardware";

export interface NotificationHistoryEntry {
  id: string;
  type: ClientNotificationItem["type"];
  title: string;
  message: string;
  timestamp: string;
  createdAt: number;
  category: NonNullable<ClientNotificationItem["category"]>;
  read: boolean;
  count: number;
}

const HISTORY_KEY = "luxe_cms_notification_history";
const OS_PREF_KEY = "luxe_cms_os_notifications";
const MAX_HISTORY = 60;
const DEDUPE_WINDOW_MS = 5000;

type Listener = () => void;
const listeners = new Set<Listener>();

function loadHistory(): NotificationHistoryEntry[] {
  try {
    const raw = sessionStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_HISTORY) : [];
  } catch {
    return [];
  }
}

let history: NotificationHistoryEntry[] = typeof window !== "undefined" ? loadHistory() : [];

function persistAndEmit() {
  try {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    // storage full / disabled: history stays in memory only
  }
  listeners.forEach((fn) => fn());
}

function record(item: ClientNotificationItem) {
  const createdAt = item.createdAt ?? Date.now();
  const last = history[0];
  if (
    last &&
    last.type === item.type &&
    last.title === item.title &&
    last.message === item.message &&
    createdAt - last.createdAt < DEDUPE_WINDOW_MS
  ) {
    history = [{ ...last, count: last.count + 1, read: false, createdAt, timestamp: item.timestamp }, ...history.slice(1)];
  } else {
    history = [
      {
        id: item.id,
        type: item.type,
        title: item.title,
        message: item.message,
        timestamp: item.timestamp,
        createdAt,
        category: item.category ?? "system",
        read: false,
        count: 1,
      },
      ...history,
    ].slice(0, MAX_HISTORY);
  }
  persistAndEmit();
}

if (typeof window !== "undefined") {
  subscribeClientNotifications((item) => {
    record(item);
    if (item.os && isOsNotificationsEnabled()) {
      void sendOsNotification(item.title, item.message);
    }
  });
}

export function subscribeNotificationHistory(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function getNotificationHistory(): NotificationHistoryEntry[] {
  return history;
}

export function getUnreadCount(): number {
  return history.reduce((n, e) => n + (e.read ? 0 : 1), 0);
}

export function markAllNotificationsRead(): void {
  if (!history.some((e) => !e.read)) return;
  history = history.map((e) => (e.read ? e : { ...e, read: true }));
  persistAndEmit();
}

export function clearNotificationHistory(): void {
  history = [];
  persistAndEmit();
}

// -------------------------------------------------- OS notifications ----

export function isOsNotificationsEnabled(): boolean {
  try {
    return localStorage.getItem(OS_PREF_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setOsNotificationsEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(OS_PREF_KEY, enabled ? "on" : "off");
  } catch {
    /* ignore */
  }
  if (enabled) void ensureBrowserNotificationPermission();
  listeners.forEach((fn) => fn());
}

async function ensureBrowserNotificationPermission(): Promise<boolean> {
  if (getTauriInvoke()) return true; // the native plugin needs no prompt on Windows
  if (typeof Notification === "undefined") return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    return (await Notification.requestPermission()) === "granted";
  } catch {
    return false;
  }
}

/**
 * Raises a native notification. In the desktop app this goes through the
 * `os_notify` Tauri command (Windows Action Center + taskbar flash); in a
 * browser it falls back to the Web Notification API. Silently does nothing
 * when the window is focused (the in-app toast already shows it) or when
 * the platform refuses.
 */
export async function sendOsNotification(title: string, body: string, onlyWhenUnfocused = true): Promise<boolean> {
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      const res = await invoke("os_notify", { title, body, onlyWhenUnfocused });
      return Boolean(res?.shown);
    } catch {
      return false;
    }
  }
  if (typeof Notification === "undefined") return false;
  if (onlyWhenUnfocused && typeof document !== "undefined" && document.hasFocus() && !document.hidden) return false;
  if (Notification.permission !== "granted") return false;
  try {
    const n = new Notification(title, { body, tag: `${title}|${body}`.slice(0, 64) });
    n.onclick = () => {
      window.focus();
      n.close();
    };
    return true;
  } catch {
    return false;
  }
}

/** Brings the CMS window to the front (desktop) or focuses the tab (browser). */
export async function focusMainWindow(): Promise<void> {
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      await invoke("app_focus_main_window");
    } catch {
      /* ignore */
    }
    return;
  }
  try {
    window.focus();
  } catch {
    /* ignore */
  }
}
