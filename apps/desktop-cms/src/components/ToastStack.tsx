// ============================================================================
// Toast stack — non-blocking notifications in the bottom corner (bottom-right
// in FR/EN, bottom-left in Arabic). Newest sits nearest the corner, at most
// four are visible, identical toasts merge into one with a "×N" counter.
//
// Auto-dismiss is driven by the progress bar's CSS animation, so hovering a
// toast (or switching to another window) pauses it for free.
// Items that open a modal message box are NOT duplicated as toasts.
// ============================================================================

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, ShieldAlert, ShoppingBag, Download, RefreshCw, X } from "lucide-react";
import { useT } from "../i18n";
import { subscribeClientNotifications, type ClientNotificationItem } from "../utils/clientNotifier";

const MAX_VISIBLE = 4;

const DEFAULT_DURATION: Record<ClientNotificationItem["type"], number> = {
  success: 4500,
  info: 6000,
  warning: 8000,
  error: 10000,
};

const TONE: Record<
  ClientNotificationItem["type"],
  { border: string; iconBg: string; label: string; bar: string }
> = {
  success: { border: "border-s-emerald-500", iconBg: "bg-emerald-50 text-emerald-600", label: "text-emerald-700", bar: "bg-emerald-500" },
  info: { border: "border-s-[#D4AF62]", iconBg: "bg-[#F8F1E1] text-[#9A7A35]", label: "text-[#9A7A35]", bar: "bg-[#D4AF62]" },
  warning: { border: "border-s-amber-500", iconBg: "bg-amber-50 text-amber-600", label: "text-amber-700", bar: "bg-amber-500" },
  error: { border: "border-s-rose-600", iconBg: "bg-rose-50 text-rose-600", label: "text-rose-700", bar: "bg-rose-600" },
};

interface ToastEntry extends ClientNotificationItem {
  count: number;
  /** bumped when a duplicate arrives, to restart the progress animation */
  nonce: number;
}

function ToastIcon({ item }: { item: ClientNotificationItem }) {
  const cls = "h-[18px] w-[18px]";
  if (item.category === "order") return <ShoppingBag className={cls} />;
  if (item.category === "update") return <Download className={cls} />;
  if (item.category === "sync") return <RefreshCw className={cls} />;
  if (item.type === "success") return <CheckCircle2 className={cls} />;
  if (item.type === "warning") return <AlertTriangle className={cls} />;
  if (item.type === "error") return <ShieldAlert className={cls} />;
  return <Info className={cls} />;
}

export function ToastStack() {
  const t = useT();
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const [pageHidden, setPageHidden] = useState(() => typeof document !== "undefined" && document.hidden);

  useEffect(() => {
    const unsub = subscribeClientNotifications((item) => {
      if (item.showModalBox) return; // shown as a message box instead
      setToasts((prev) => {
        const dup = prev.find((p) => p.type === item.type && p.title === item.title && p.message === item.message);
        if (dup) {
          return prev.map((p) =>
            p === dup ? { ...p, count: p.count + 1, nonce: p.nonce + 1, timestamp: item.timestamp, action: item.action ?? p.action } : p
          );
        }
        return [...prev, { ...item, count: 1, nonce: 0 }].slice(-MAX_VISIBLE);
      });
    });
    const onVisibility = () => setPageHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      unsub();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const dismiss = (id: string) => setToasts((prev) => prev.filter((p) => p.id !== id));

  if (toasts.length === 0) return null;

  return (
    <section
      aria-label={t("notif.center.title")}
      data-paused={pageHidden ? "true" : "false"}
      className="luxe-toast-stack fixed bottom-5 end-5 z-[90] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-2.5 pointer-events-none"
    >
      {toasts.map((item) => {
        const tone = TONE[item.type];
        const duration = item.durationMs ?? DEFAULT_DURATION[item.type];
        return (
          <div
            key={item.id}
            role={item.type === "error" ? "alert" : "status"}
            aria-live={item.type === "error" ? "assertive" : "polite"}
            data-toast-type={item.type}
            className={`luxe-toast pointer-events-auto relative overflow-hidden rounded-2xl border border-black/5 border-s-4 ${tone.border} bg-white text-[#202923] shadow-[0_18px_40px_-12px_rgba(2,41,31,0.35)]`}
          >
            <div className="flex gap-3 p-3.5 pb-4">
              <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tone.iconBg}`}>
                <ToastIcon item={item} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-extrabold uppercase tracking-wider ${tone.label}`}>
                    {t(`notif.badge.${item.type}`)}
                  </span>
                  {item.count > 1 && (
                    <span className="rounded-full bg-[#063D2E] px-1.5 py-px text-[10px] font-bold text-[#D4AF62]">
                      {t("notif.repeat", { n: item.count })}
                    </span>
                  )}
                  <span className="ms-auto font-mono text-[10px] text-gray-400">{item.timestamp}</span>
                </div>
                <p className="mt-0.5 text-sm font-bold leading-snug text-[#063D2E]">{item.title}</p>
                {item.message && <p className="mt-0.5 line-clamp-3 text-xs leading-relaxed text-gray-600">{item.message}</p>}
                {item.action && (
                  <button
                    type="button"
                    onClick={() => {
                      item.action?.onClick();
                      dismiss(item.id);
                    }}
                    className="mt-2 rounded-lg bg-[#063D2E] px-3 py-1.5 text-xs font-extrabold text-[#D4AF62] transition hover:bg-[#02291F]"
                  >
                    {item.action.label}
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label={t("notif.close")}
                className="self-start rounded-lg p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {duration > 0 && (
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gray-100">
                <div
                  key={item.nonce}
                  className={`luxe-toast-progress h-full ${tone.bar}`}
                  style={{ animationDuration: `${duration}ms` }}
                  onAnimationEnd={() => dismiss(item.id)}
                />
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
