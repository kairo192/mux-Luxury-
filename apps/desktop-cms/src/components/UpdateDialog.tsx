// ============================================================================
// Update dialog — opened from the version chip in the header or from the
// "Mise à jour disponible" toast. Shows the installed version, checks the
// signed release feed, and installs + restarts on request. Before installing
// it warns if offline POS sales are still waiting to sync.
// ============================================================================

import React, { useEffect, useState } from "react";
import { CheckCircle2, Download, Loader2, RefreshCw, ShieldAlert, Sparkles, X } from "lucide-react";
import { useT } from "../i18n";
import {
  checkForUpdate,
  getUpdateState,
  installUpdate,
  loadUpdaterStatus,
  subscribeUpdateState,
  type UpdateState,
} from "../utils/appUpdater";
import { confirmClientAction } from "../utils/clientNotifier";
import { posQueueCounts } from "../utils/posOfflineQueue";

function formatBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} Mo`;
  if (n >= 1024) return `${Math.round(n / 1024)} Ko`;
  return `${n} o`;
}

export function UpdateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const [s, setS] = useState<UpdateState>(getUpdateState());

  useEffect(() => subscribeUpdateState(setS), []);

  useEffect(() => {
    if (!open) return;
    void loadUpdaterStatus();
    const onKey = (e: KeyboardEvent) => {
      const busy = getUpdateState().phase === "downloading" || getUpdateState().phase === "installing";
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const busy = s.phase === "downloading" || s.phase === "installing";
  const percent = s.total ? Math.min(100, Math.round((s.downloaded / s.total) * 100)) : null;

  const handleInstall = async () => {
    const q = posQueueCounts();
    const unsynced = q.pending + q.failed + q.conflict;
    if (unsynced > 0) {
      const ok = await confirmClientAction({
        title: t("update.pending_sales_title"),
        message: t("update.pending_sales_msg", { n: unsynced }),
        confirmLabel: t("update.continue"),
      });
      if (!ok) return;
    }
    await installUpdate();
  };

  return (
    <div className="animate-backdrop fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-dialog-title"
        className="animate-modal w-full max-w-md overflow-hidden rounded-2xl border-2 border-[#D4AF62] bg-white text-[#202923] shadow-2xl"
      >
        <div className="flex items-center gap-3 bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#D4AF62]/15 text-[#D4AF62]">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="update-dialog-title" className="font-serif text-base font-bold text-white">
              {t("update.title")}
            </h3>
            <p className="text-[11px] text-[#E8D4A5]/80">
              {t("update.current")} : <span className="font-mono font-bold">v{s.currentVersion || "—"}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label={t("common.close") || "Fermer"}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-black/25 text-white transition hover:bg-black/40 disabled:opacity-40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-6 text-sm">
          {s.phase === "unsupported" && <p className="rounded-xl bg-[#F8F6F0] p-3.5 text-gray-700">{t("update.unsupported")}</p>}

          {s.phase === "disabled" && (
            <p className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-amber-900">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{t("update.disabled")}</span>
            </p>
          )}

          {(s.phase === "idle" || s.phase === "checking") && (
            <p className="flex items-center gap-2 text-gray-600">
              {s.phase === "checking" && <Loader2 className="h-4 w-4 animate-spin text-[#063D2E]" />}
              {s.phase === "checking" ? t("update.checking") : t("update.auto")}
            </p>
          )}

          {s.phase === "up_to_date" && (
            <p className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 font-bold text-emerald-800">
              <CheckCircle2 className="h-4 w-4" />
              {t("update.up_to_date")}
            </p>
          )}

          {s.phase === "error" && (
            <p className="flex gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-rose-800">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{t("update.error")}</span>
            </p>
          )}

          {(s.phase === "available" || busy) && s.availableVersion && (
            <div className="space-y-3">
              <p className="flex items-center gap-2 font-serif text-base font-bold text-[#063D2E]">
                <Download className="h-4 w-4 text-[#D4AF62]" />
                {t("update.available", { v: s.availableVersion })}
              </p>
              {s.notes && (
                <div className="max-h-40 overflow-y-auto rounded-xl border border-[#D4AF62]/30 bg-[#F8F6F0] p-3.5">
                  <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-[#9A7A35]">{t("update.notes")}</p>
                  <p className="whitespace-pre-line text-xs leading-relaxed text-gray-700">{s.notes}</p>
                </div>
              )}
            </div>
          )}

          {busy && (
            <div className="space-y-1.5">
              <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  className={`h-full rounded-full bg-gradient-to-r from-[#063D2E] to-[#D4AF62] transition-all ${percent === null ? "w-1/3 animate-pulse" : ""}`}
                  style={percent === null ? undefined : { width: `${percent}%` }}
                />
              </div>
              <p className="text-xs text-gray-600">
                {s.phase === "installing"
                  ? t("update.installing")
                  : t("update.downloading", {
                      p: percent === null ? formatBytes(s.downloaded) : `${percent}% (${formatBytes(s.downloaded)})`,
                    })}
              </p>
            </div>
          )}

          {s.lastCheckedAt && !busy && (
            <p className="text-[11px] text-gray-400">
              {t("update.last_checked", {
                t: new Date(s.lastCheckedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              })}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            {s.phase === "available" ? (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-xl border border-gray-300 px-5 py-2.5 text-xs font-bold text-gray-700 transition hover:bg-gray-100"
                >
                  {t("update.later")}
                </button>
                <button
                  type="button"
                  onClick={handleInstall}
                  className="flex items-center gap-2 rounded-xl bg-[#063D2E] px-5 py-2.5 text-xs font-extrabold text-[#D4AF62] shadow transition hover:bg-[#02291F]"
                >
                  <Download className="h-4 w-4" />
                  {t("update.install")}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => void checkForUpdate()}
                disabled={busy || s.phase === "checking" || s.phase === "disabled" || s.phase === "unsupported"}
                className="flex items-center gap-2 rounded-xl bg-[#063D2E] px-5 py-2.5 text-xs font-extrabold text-[#D4AF62] shadow transition hover:bg-[#02291F] disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RefreshCw className={`h-4 w-4 ${s.phase === "checking" ? "animate-spin" : ""}`} />
                {t("update.check")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
