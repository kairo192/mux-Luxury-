// ============================================================================
// Header bell — notification history with unread badge, mark-as-read,
// clear, and the "Windows notifications" on/off switch.
// ============================================================================

import { useEffect, useReducer, useRef, useState } from "react";
import { AlertTriangle, Bell, CheckCircle2, Info, ShieldAlert, ShoppingBag, Download, RefreshCw, CheckCheck, Trash2 } from "lucide-react";
import { useT } from "../i18n";
import {
  clearNotificationHistory,
  getNotificationHistory,
  getUnreadCount,
  isOsNotificationsEnabled,
  markAllNotificationsRead,
  setOsNotificationsEnabled,
  subscribeNotificationHistory,
  type NotificationHistoryEntry,
} from "../utils/notificationCenter";

const TYPE_STYLE: Record<NotificationHistoryEntry["type"], string> = {
  success: "bg-emerald-50 text-emerald-600",
  info: "bg-[#F8F1E1] text-[#9A7A35]",
  warning: "bg-amber-50 text-amber-600",
  error: "bg-rose-50 text-rose-600",
};

function EntryIcon({ e }: { e: NotificationHistoryEntry }) {
  const cls = "h-4 w-4";
  if (e.category === "order") return <ShoppingBag className={cls} />;
  if (e.category === "update") return <Download className={cls} />;
  if (e.category === "sync") return <RefreshCw className={cls} />;
  if (e.type === "success") return <CheckCircle2 className={cls} />;
  if (e.type === "warning") return <AlertTriangle className={cls} />;
  if (e.type === "error") return <ShieldAlert className={cls} />;
  return <Info className={cls} />;
}

export function NotificationBell() {
  const t = useT();
  const [, rerender] = useReducer((x: number) => x + 1, 0);
  const [open, setOpen] = useState(false);
  const [osOn, setOsOn] = useState(isOsNotificationsEnabled());
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => subscribeNotificationHistory(rerender), []);

  // Close on outside click / Esc; entries seen while open become "read" on close.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const tick = window.setInterval(rerender, 30000); // keep "il y a N min" fresh
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
      window.clearInterval(tick);
      markAllNotificationsRead();
    };
  }, [open]);

  const history = getNotificationHistory();
  const unread = getUnreadCount();

  const relative = (ts: number) => {
    const minutes = Math.floor((Date.now() - ts) / 60000);
    if (minutes < 1) return t("notif.center.just_now");
    if (minutes < 60) return t("notif.center.minutes_ago", { n: minutes });
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("notif.center.open")}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={t("notif.center.title")}
        className={`relative flex h-9 w-9 items-center justify-center rounded-full border transition ${
          open ? "border-[#D4AF62] bg-[#D4AF62] text-[#02291F]" : "border-[#D4AF62]/40 bg-white/10 text-[#E8D4A5] hover:bg-white/20"
        }`}
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -top-1 -end-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-extrabold text-white ring-2 ring-[#063D2E]">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("notif.center.title")}
          className="animate-panel absolute end-0 top-full z-[60] mt-2 flex max-h-[72vh] w-[400px] flex-col overflow-hidden rounded-2xl bg-white text-[#202923] shadow-2xl ring-1 ring-black/10"
        >
          <div className="flex items-center gap-2 border-b border-gray-100 bg-[#F8F6F0] px-4 py-3">
            <Bell className="h-4 w-4 text-[#063D2E]" />
            <span className="font-serif text-sm font-bold text-[#063D2E]">{t("notif.center.title")}</span>
            {unread > 0 && (
              <span className="whitespace-nowrap rounded-full bg-rose-600 px-2 py-px text-[10px] font-bold text-white">
                {t("notif.center.unread", { n: unread })}
              </span>
            )}
            <button
              type="button"
              onClick={markAllNotificationsRead}
              disabled={unread === 0}
              title={t("notif.center.mark_read")}
              className="ms-auto flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-bold text-[#063D2E] transition hover:bg-white disabled:opacity-40"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              {t("notif.center.mark_read")}
            </button>
          </div>

          <ul className="flex-1 overflow-y-auto">
            {history.length === 0 && (
              <li className="flex flex-col items-center gap-2 px-6 py-10 text-center text-xs text-gray-500">
                <Bell className="h-6 w-6 text-gray-300" />
                {t("notif.center.empty")}
              </li>
            )}
            {history.map((e) => (
              <li
                key={e.id}
                className={`flex gap-3 border-b border-gray-50 px-4 py-3 ${e.read ? "" : "bg-[#FBF7EC]"}`}
              >
                <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${TYPE_STYLE[e.type]}`}>
                  <EntryIcon e={e} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-[13px] font-bold text-[#063D2E]">{e.title}</p>
                    {e.count > 1 && (
                      <span className="rounded-full bg-gray-100 px-1.5 text-[10px] font-bold text-gray-600">
                        {t("notif.repeat", { n: e.count })}
                      </span>
                    )}
                    {!e.read && <span className="ms-auto h-2 w-2 shrink-0 rounded-full bg-rose-500" aria-hidden="true" />}
                  </div>
                  {e.message && <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-gray-600">{e.message}</p>}
                  <p className="mt-1 text-[10px] font-medium text-gray-400">{relative(e.createdAt)}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-3 border-t border-gray-100 px-4 py-3">
            <button
              type="button"
              role="switch"
              aria-checked={osOn}
              onClick={() => {
                const next = !osOn;
                setOsOn(next);
                setOsNotificationsEnabled(next);
              }}
              className="flex min-w-0 flex-1 items-center gap-2.5 text-start"
            >
              <span
                className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition ${osOn ? "bg-[#063D2E]" : "bg-gray-300"}`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${
                    osOn ? "start-[18px]" : "start-0.5"
                  }`}
                />
              </span>
              <span className="min-w-0">
                <span className="block text-xs font-bold text-[#063D2E]">{t("notif.center.os_toggle")}</span>
                <span className="block text-[10px] leading-snug text-gray-500">{t("notif.center.os_hint")}</span>
              </span>
            </button>
            <button
              type="button"
              onClick={clearNotificationHistory}
              disabled={history.length === 0}
              className="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-bold text-gray-500 transition hover:bg-gray-100 hover:text-rose-600 disabled:opacity-40"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t("notif.center.clear")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
