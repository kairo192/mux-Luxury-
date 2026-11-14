import React, { useRef } from "react";
import { AlertTriangle, CheckCircle2, ShieldAlert, X } from "lucide-react";
import { useT } from "../i18n";
import { ToastStack } from "../components/ToastStack";
import { useModalFocus } from "../utils/useModalFocus";
import type { ClientConfirmRequest, ClientNotificationItem } from "../utils/clientNotifier";

interface Props {
  messageQueue: ClientNotificationItem[];
  setMessageQueue: React.Dispatch<React.SetStateAction<ClientNotificationItem[]>>;
  closeMessageBox: () => void;
  activeConfirm: ClientConfirmRequest | null;
  messageBoxOkButtonRef: React.RefObject<HTMLButtonElement | null>;
  confirmCancelButtonRef: React.RefObject<HTMLButtonElement | null>;
}

/** Toasts, the queued blocking message box and the confirmation dialog (App's notification centre). */
export function ClientNotificationCenter({ messageQueue, setMessageQueue, closeMessageBox, activeConfirm, messageBoxOkButtonRef, confirmCancelButtonRef }: Props) {
  const t = useT();
  const activeMessageBox = messageQueue[0] ?? null;
  const messageBoxRef = useRef<HTMLDivElement | null>(null);
  const confirmRef = useRef<HTMLDivElement | null>(null);
  // Focus stays inside the topmost of the two and comes back where it was;
  // App still picks the button that gets focus first (OK / Annuler).
  // Layers follow the z-index: the confirmation (z-80) sits above the message (z-75).
  useModalFocus(messageBoxRef, Boolean(activeMessageBox), messageBoxOkButtonRef, 75);
  useModalFocus(confirmRef, Boolean(activeConfirm), confirmCancelButtonRef, 80);
  return (
    <>
      {/* Non-blocking toasts: bottom corner, newest nearest the corner */}
      <ToastStack />

      {/* Modal Client Message Box (Boîte de Message Client) — queued */}
      {activeMessageBox && (
        <div className="animate-backdrop fixed inset-0 z-[75] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            ref={messageBoxRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="active-message-box-title"
            aria-describedby="active-message-box-body"
            className="animate-modal bg-white text-[#202923] rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
          >
            <div
              className={`px-5 py-3.5 flex items-center justify-between gap-3 ${
                activeMessageBox.type === "error"
                  ? "bg-gradient-to-r from-red-950 to-red-800 text-white"
                  : activeMessageBox.type === "warning"
                  ? "bg-gradient-to-r from-amber-900 to-amber-700 text-white"
                  : "bg-gradient-to-r from-[#02291F] to-[#063D2E] text-white"
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center shrink-0">
                  {activeMessageBox.type === "error" && <ShieldAlert className="w-4 h-4 text-rose-200" />}
                  {activeMessageBox.type === "warning" && <AlertTriangle className="w-4 h-4 text-amber-200" />}
                  {(activeMessageBox.type === "info" || activeMessageBox.type === "success") && (
                    <CheckCircle2 className="w-4 h-4 text-[#D4AF62]" />
                  )}
                </span>
                <span className="text-sm font-extrabold text-[#E8D4A5] truncate">
                  {activeMessageBox.type === "error"
                    ? t("msgbox.title.error")
                    : activeMessageBox.type === "warning"
                    ? t("msgbox.title.warning")
                    : t("msgbox.title.info")}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {messageQueue.length > 1 && (
                  <span className="px-2 py-0.5 rounded-full bg-black/25 text-[10px] font-bold text-white/90">
                    {t("msgbox.counter", { i: 1, n: messageQueue.length })}
                  </span>
                )}
                <button
                  type="button"
                  onClick={closeMessageBox}
                  aria-label={t("common.close") || "Fermer"}
                  className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <h4 id="active-message-box-title" className="text-base font-serif font-bold text-[#063D2E]">
                {activeMessageBox.title}
              </h4>
              <p
                id="active-message-box-body"
                className="text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30"
              >
                {activeMessageBox.message}
              </p>
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <span className="text-[10px] text-gray-400 font-mono">
                  {activeMessageBox.timestamp} • {t("msgbox.keyboard_hint")}
                </span>
                <div className="ms-auto flex gap-2 whitespace-nowrap">
                  {messageQueue.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setMessageQueue([])}
                      className="px-4 py-2.5 rounded-xl border border-gray-300 text-gray-600 font-bold hover:bg-gray-100 transition"
                    >
                      {t("msgbox.dismiss_all")}
                    </button>
                  )}
                  <button
                    ref={messageBoxOkButtonRef}
                    type="button"
                    onClick={closeMessageBox}
                    className="px-6 py-2.5 rounded-xl bg-[#063D2E] hover:bg-[#02291F] text-[#D4AF62] font-extrabold text-xs shadow focus:outline-none focus:ring-2 focus:ring-[#D4AF62] focus:ring-offset-2"
                  >
                    {messageQueue.length > 1 ? t("msgbox.next") : t("msgbox.ok") || "Compris (Fermer)"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Confirmation Dialog */}
      {activeConfirm && (
        <div className="animate-backdrop fixed inset-0 z-[80] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            ref={confirmRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="active-confirm-title"
            className="bg-white text-[#202923] rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
          >
            <div
              className={`px-5 py-3.5 flex items-center justify-between ${
                activeConfirm.danger ? "bg-red-900 text-white" : "bg-[#063D2E] text-white"
              }`}
            >
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-[#D4AF62]" />
                <span id="active-confirm-title" className="text-base font-extrabold text-[#D4AF62]">
                  {activeConfirm.title}
                </span>
              </div>
              <button
                type="button"
                onClick={() => activeConfirm.resolve(false)}
                aria-label={t("common.close") || "Fermer"}
                className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30">
                {activeConfirm.message}
              </p>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  ref={confirmCancelButtonRef}
                  type="button"
                  onClick={() => activeConfirm.resolve(false)}
                  className="px-5 py-2.5 rounded-xl border border-gray-300 text-gray-700 font-bold hover:bg-gray-100 transition focus:outline-none focus:ring-2 focus:ring-[#D4AF62]"
                >
                  {activeConfirm.cancelLabel || t("common.cancel")}
                </button>
                <button
                  type="button"
                  onClick={() => activeConfirm.resolve(true)}
                  className={`px-6 py-2.5 rounded-xl font-extrabold text-xs shadow transition ${
                    activeConfirm.danger
                      ? "bg-red-600 hover:bg-red-700 text-white"
                      : "bg-[#063D2E] hover:bg-[#02291F] text-[#D4AF62]"
                  }`}
                >
                  {activeConfirm.confirmLabel || t("common.confirm")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
