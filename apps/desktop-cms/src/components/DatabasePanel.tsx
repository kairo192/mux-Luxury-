// ============================================================================
// Base de données & sauvegardes (owner only)
//   - where the data lives, how big, what it contains
//   - every backup (nightly, manual, safety copies) with one-click restore
//   - "Sauvegarder maintenant"
//   - "Nouvelle base de données": empties the store after a safety backup
// Restore and reset need the owner's password + a typed confirmation word.
// Backup files never leave the server (no download over the internet).
// ============================================================================

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Database,
  HardDrive,
  History,
  Image as ImageIcon,
  Loader2,
  Lock,
  LockOpen,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Trash2,
  X,
  HardDriveDownload,
  Upload as UploadIcon,
} from "lucide-react";
import { useT } from "../i18n";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import { serverDate } from "../utils/serverDate";
import { copyBackupToPc, listPcCopies, pcCopiesAvailable, sendPcCopyToServer, type PcCopies } from "../utils/backupCopies";

interface BackupMeta {
  name: string;
  kind: string;
  created_at: string;
  encrypted: boolean;
  size: number;
  total_rows: number | null;
  media?: { name: string; size: number } | null;
}

interface DbStatus {
  engine: string;
  version: string;
  location: string;
  size_bytes: number;
  total_rows: number;
  counts: Array<{ table: string; label: string; rows: number }>;
  encryption: boolean;
  retention_days: number;
  backups: BackupMeta[];
  last_backup: BackupMeta | null;
  warnings: string[];
}

function formatBytes(n: number): string {
  if (!n) return "0 o";
  if (n >= 1024 * 1024 * 1024) return `${(n / 1024 ** 3).toFixed(2)} Go`;
  if (n >= 1024 * 1024) return `${(n / 1024 ** 2).toFixed(1)} Mo`;
  if (n >= 1024) return `${Math.round(n / 1024)} Ko`;
  return `${n} o`;
}

function formatDate(iso: string): string {
  try {
    return serverDate(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

type Danger = { mode: "reset" } | { mode: "restore"; backup: BackupMeta };

/** GET /admin/system/configuration — names and states only, never values. */
interface ServerConfig {
  production: boolean;
  ok: boolean;
  problems: string[];
}

export function DatabasePanel({ active, isOwner }: { active: boolean; isOwner: boolean }) {
  const t = useT();
  const [status, setStatus] = useState<DbStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [withMedia, setWithMedia] = useState(false);
  const [danger, setDanger] = useState<Danger | null>(null);
  const [keepSettings, setKeepSettings] = useState(true);
  const [password, setPassword] = useState("");
  const [confirmWord, setConfirmWord] = useState("");
  const [pcCopies, setPcCopies] = useState<PcCopies | null>(null);
  const [serverConfig, setServerConfig] = useState<ServerConfig | null>(null);
  const desktopApp = pcCopiesAvailable();

  const load = useCallback(async () => {
    if (!isOwner) return;
    setLoading(true);
    setLoadError("");
    try {
      setStatus((await DesktopCmsApi.getDatabaseStatus()) as DbStatus);
      if (desktopApp) setPcCopies(await listPcCopies().catch(() => null));
      setServerConfig((await DesktopCmsApi.getServerConfiguration().catch(() => null)) as ServerConfig | null);
    } catch (err: any) {
      const tr = notifyClientError(err, t("db.load_error"), false);
      setLoadError(tr.message);
    } finally {
      setLoading(false);
    }
  }, [isOwner, t, desktopApp]);

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  const kindLabel = (k: string) => {
    const key = `db.kind.${k}`;
    const label = t(key);
    return label === key ? k : label;
  };

  async function handleBackupNow() {
    setBusy(true);
    try {
      const meta: any = await DesktopCmsApi.createDatabaseBackup(withMedia);
      notifyClientSuccess(t("db.backup_done_title"), t("db.backup_done_body", { size: formatBytes(meta?.size || 0) }));
      await load();
    } catch (err: any) {
      notifyClientError(err, t("db.backup_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyToPc(name: string) {
    setBusy(true);
    try {
      const where = await copyBackupToPc(name);
      notifyClientSuccess(t("db.copy_done_title"), t("db.copy_done_body", { path: where }));
      await load();
    } catch (err: any) {
      notifyClientError(err, t("db.copy_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSendBack(source: { name: string } | File) {
    setBusy(true);
    try {
      const meta: any = await sendPcCopyToServer(source);
      notifyClientSuccess(t("db.send_back_done_title"), t("db.send_back_done_body", { name: meta?.name || "" }));
      await load();
    } catch (err: any) {
      notifyClientError(err, t("db.send_back_failed"));
    } finally {
      setBusy(false);
    }
  }

  function openDanger(d: Danger) {
    setDanger(d);
    setPassword("");
    setConfirmWord("");
  }

  const expectedWord = danger?.mode === "reset" ? "EFFACER" : "RESTAURER";

  async function handleDangerConfirm() {
    if (!danger) return;
    setBusy(true);
    try {
      if (danger.mode === "reset") {
        const res: any = await DesktopCmsApi.resetDatabase(password, confirmWord, keepSettings);
        notifyClientSuccess(t("db.reset_done_title"), t("db.reset_done_body", { rows: res?.rows_deleted ?? 0, backup: res?.safety_backup ?? "" }), true);
      } else {
        const res: any = await DesktopCmsApi.restoreDatabaseBackup(danger.backup.name, password, confirmWord);
        notifyClientSuccess(t("db.restore_done_title"), t("db.restore_done_body", { backup: res?.safety_backup ?? "" }), true);
        if (res?.media_error) notifyClientWarning(t("db.restore_media_failed_title"), t("db.restore_media_failed_body"), true);
      }
      setDanger(null);
      // Everything on screen (catalog, orders, POS cache) is now stale.
      window.setTimeout(() => window.location.reload(), 2500);
    } catch (err: any) {
      notifyClientError(err, danger.mode === "reset" ? t("db.reset_failed") : t("db.restore_failed"));
    } finally {
      setBusy(false);
    }
  }

  if (!isOwner) {
    return (
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 flex items-center gap-3 text-xs text-gray-600">
        <Lock className="w-5 h-5 text-[#D4AF62]" />
        <span>{t("db.owner_only")}</span>
      </div>
    );
  }

  return (
    <div className="space-y-5 text-xs">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] p-6 rounded-2xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-4 text-white">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-[#D4AF62]/15 flex items-center justify-center">
            <Database className="w-6 h-6 text-[#D4AF62]" />
          </div>
          <div>
            <h3 className="text-base font-serif font-bold">{t("db.title")}</h3>
            <p className="text-[#E8D4A5]/80">{t("db.subtitle")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[#E8D4A5] cursor-pointer">
            <input type="checkbox" checked={withMedia} onChange={(e) => setWithMedia(e.target.checked)} className="accent-[#D4AF62]" />
            <ImageIcon className="w-4 h-4" />
            {t("db.include_media")}
          </label>
          <button
            type="button"
            onClick={handleBackupNow}
            disabled={busy || loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold shadow hover:bg-[#E8D4A5] transition disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Archive className="w-4 h-4" />}
            {t("db.backup_now")}
          </button>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            title={t("db.refresh")}
            className="w-10 h-10 rounded-xl bg-white/10 border border-[#D4AF62]/40 flex items-center justify-center hover:bg-white/20"
          >
            <RefreshCw className={`w-4 h-4 text-[#E8D4A5] ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {loadError && !status && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-2xl">{loadError}</div>
      )}

      {status && (
        <>
          {/* Status cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
              <p className="text-[10px] uppercase tracking-wider font-extrabold text-gray-400">{t("db.engine")}</p>
              <p className="mt-1 text-base font-bold text-[#063D2E] flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-[#D4AF62]" /> {status.engine}
              </p>
              <p className="text-[11px] text-gray-500 mt-0.5">{status.location}</p>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
              <p className="text-[10px] uppercase tracking-wider font-extrabold text-gray-400">{t("db.size")}</p>
              <p className="mt-1 text-base font-bold text-[#063D2E]">{formatBytes(status.size_bytes)}</p>
              <p className="text-[11px] text-gray-500 mt-0.5">{t("db.rows", { n: status.total_rows.toLocaleString() })}</p>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
              <p className="text-[10px] uppercase tracking-wider font-extrabold text-gray-400">{t("db.encryption")}</p>
              <p className={`mt-1 text-base font-bold flex items-center gap-2 ${status.encryption ? "text-emerald-700" : "text-amber-700"}`}>
                {status.encryption ? <Lock className="w-4 h-4" /> : <LockOpen className="w-4 h-4" />}
                {status.encryption ? t("db.encryption_on") : t("db.encryption_off")}
              </p>
              <p className="text-[11px] text-gray-500 mt-0.5">{t("db.retention", { n: status.retention_days })}</p>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
              <p className="text-[10px] uppercase tracking-wider font-extrabold text-gray-400">{t("db.last_backup")}</p>
              <p className="mt-1 text-base font-bold text-[#063D2E]">
                {status.last_backup ? formatDate(status.last_backup.created_at) : "—"}
              </p>
              <p className="text-[11px] text-gray-500 mt-0.5">
                {status.last_backup ? kindLabel(status.last_backup.kind) : t("db.no_backup")}
              </p>
            </div>
          </div>

          {/* Warnings */}
          {status.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-1.5">
              {status.warnings.map((w) => (
                <p key={w} className="flex gap-2 text-amber-900">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-px" />
                  <span>{w}</span>
                </p>
              ))}
            </div>
          )}

          {/* Server configuration (.env) */}
          {serverConfig && (
            <div className={`rounded-2xl p-4 border space-y-1.5 ${serverConfig.ok ? "bg-white border-gray-200" : "bg-red-50 border-red-200"}`}>
              <p className="font-bold text-[#063D2E]">
                {t("db.config_title")} — {serverConfig.ok ? t("db.config_ok") : t("db.config_missing")}
              </p>
              {serverConfig.problems.map((p) => (
                <p key={p} className="flex gap-2 text-amber-900">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-px" />
                  <span className="font-mono">{p}</span>
                </p>
              ))}
              <p className="text-gray-400">{t("db.config_hint")}</p>
            </div>
          )}

          {/* Contents */}
          <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40">
            <h4 className="font-serif font-bold text-sm text-[#063D2E] mb-3">{t("db.contents")}</h4>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {status.counts.map((c) => (
                <div key={c.table} className="rounded-xl bg-[#F8F6F0] px-3 py-2.5">
                  <p className="text-[11px] text-gray-500">{c.label}</p>
                  <p className="text-lg font-bold text-[#063D2E] font-mono">{c.rows.toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Backups */}
          <div className="bg-white rounded-2xl border border-[#D4AF62]/40 overflow-hidden">
            <div className="px-5 py-4 flex items-center gap-2 border-b border-gray-100">
              <History className="w-4 h-4 text-[#D4AF62]" />
              <h4 className="font-serif font-bold text-sm text-[#063D2E]">{t("db.backups_title", { n: status.backups.length })}</h4>
            </div>
            {status.backups.length === 0 ? (
              <p className="p-6 text-center text-gray-500">{t("db.no_backup")}</p>
            ) : (
              <table className="w-full text-start">
                <thead className="bg-[#F8F6F0] text-[10px] uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-5 py-2.5 text-start">{t("db.col_date")}</th>
                    <th className="px-3 py-2.5 text-start">{t("db.col_type")}</th>
                    <th className="px-3 py-2.5 text-start">{t("db.col_content")}</th>
                    <th className="px-3 py-2.5 text-start">{t("db.col_size")}</th>
                    <th className="px-5 py-2.5 text-end"></th>
                  </tr>
                </thead>
                <tbody>
                  {status.backups.map((b) => (
                    <tr key={b.name} className="border-t border-gray-50 hover:bg-[#FBF7EC]">
                      <td className="px-5 py-3 font-bold text-[#063D2E]">{formatDate(b.created_at)}</td>
                      <td className="px-3 py-3">
                        <span className="px-2 py-0.5 rounded-full bg-[#063D2E]/5 text-[#063D2E] font-bold text-[11px]">{kindLabel(b.kind)}</span>
                      </td>
                      <td className="px-3 py-3 text-gray-600">
                        <span className="inline-flex items-center gap-1.5">
                          {b.encrypted ? <Lock className="w-3.5 h-3.5 text-emerald-600" /> : <LockOpen className="w-3.5 h-3.5 text-amber-600" />}
                          {b.total_rows != null ? t("db.rows", { n: b.total_rows.toLocaleString() }) : "—"}
                          {b.media && (
                            <span className="inline-flex items-center gap-1 ms-2 text-gray-500">
                              <ImageIcon className="w-3.5 h-3.5" /> {formatBytes(b.media.size)}
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-3 py-3 font-mono text-gray-500">{formatBytes(b.size)}</td>
                      <td className="px-5 py-3 text-end whitespace-nowrap">
                        {b.encrypted && (
                          <button
                            type="button"
                            onClick={() => handleCopyToPc(b.name)}
                            disabled={busy}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 me-2 rounded-lg border border-gray-300 text-[#063D2E] font-bold hover:bg-gray-50 transition disabled:opacity-40"
                          >
                            <HardDriveDownload className="w-3.5 h-3.5" />
                            {pcCopies?.items.some((c) => c.name === b.name) ? t("db.copied_to_pc") : t("db.copy_to_pc")}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => openDanger({ mode: "restore", backup: b })}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#D4AF62] text-[#063D2E] font-bold hover:bg-[#D4AF62]/15 transition disabled:opacity-40"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          {t("db.restore")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Copies kept on this PC */}
          <div className="bg-white rounded-2xl border border-[#D4AF62]/40 p-5 space-y-3">
            <h4 className="font-serif font-bold text-sm text-[#063D2E] flex items-center gap-2">
              <HardDriveDownload className="w-4 h-4 text-[#D4AF62]" /> {t("db.pc_copies_title")}
            </h4>
            <p className="text-gray-600 leading-relaxed">
              {desktopApp && pcCopies
                ? t("db.pc_copies_desc", { folder: pcCopies.folder, keep: pcCopies.keep })
                : t("db.pc_copies_browser")}
            </p>
            {desktopApp && pcCopies && (
              pcCopies.items.length === 0 ? (
                <p className="text-gray-500">{t("db.pc_copies_empty")}</p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {pcCopies.items.slice(0, 8).map((c) => (
                    <li key={c.name} className="py-2 flex items-center justify-between gap-3">
                      <span className="font-mono text-[11px] text-gray-600 truncate">{c.name}</span>
                      <span className="flex items-center gap-3 shrink-0">
                        <span className="text-gray-500 font-mono">{formatBytes(c.size)}</span>
                        <button type="button" disabled={busy} onClick={() => handleSendBack({ name: c.name })}
                          className="px-3 py-1.5 rounded-lg border border-[#D4AF62] text-[#063D2E] font-bold hover:bg-[#D4AF62]/15 disabled:opacity-40">
                          {t("db.send_back")}
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              )
            )}
            <label className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-gray-300 cursor-pointer hover:bg-gray-50 font-bold text-[#063D2E]">
              <UploadIcon className="w-4 h-4" /> {t("db.send_file_btn")}
              <input
                type="file"
                accept=".enc"
                className="hidden"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (f) void handleSendBack(f);
                }}
              />
            </label>
          </div>

          {/* Danger zone */}
          <div className="bg-white rounded-2xl border-2 border-rose-200 p-5 flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl space-y-2">
              <h4 className="font-serif font-bold text-sm text-rose-800 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" /> {t("db.reset_title")}
              </h4>
              <p className="text-gray-600 leading-relaxed">{t("db.reset_erases")}</p>
              <p className="text-gray-600 leading-relaxed">{t("db.reset_keeps")}</p>
              <label className="flex items-center gap-2 font-bold text-[#063D2E] cursor-pointer pt-1">
                <input type="checkbox" checked={keepSettings} onChange={(e) => setKeepSettings(e.target.checked)} className="accent-[#063D2E]" />
                {t("db.keep_settings")}
              </label>
            </div>
            <button
              type="button"
              onClick={() => openDanger({ mode: "reset" })}
              disabled={busy}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-700 text-white font-extrabold shadow hover:bg-rose-800 transition disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              {t("db.reset_button")}
            </button>
          </div>
        </>
      )}

      {/* Confirmation dialog (reset / restore) */}
      {danger && (
        <div className="animate-backdrop fixed inset-0 z-[70] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="db-danger-title"
            className="animate-modal bg-white rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-rose-300"
          >
            <div className="px-5 py-3.5 flex items-center justify-between bg-gradient-to-r from-rose-950 to-rose-800 text-white">
              <span id="db-danger-title" className="font-extrabold text-sm flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                {danger.mode === "reset" ? t("db.reset_title") : t("db.restore_title")}
              </span>
              <button type="button" onClick={() => setDanger(null)} disabled={busy} aria-label={t("common.close")} className="w-7 h-7 rounded-full bg-black/25 flex items-center justify-center hover:bg-black/40">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-sm text-gray-700 leading-relaxed bg-[#F8F6F0] p-3.5 rounded-xl border border-rose-100">
                {danger.mode === "reset"
                  ? t("db.reset_warning")
                  : t("db.restore_warning", { date: formatDate(danger.backup.created_at) })}
              </p>
              <p className="flex items-center gap-2 text-emerald-800 font-bold">
                <CheckCircle2 className="w-4 h-4" /> {t("db.safety_note")}
              </p>
              <label className="block space-y-1">
                <span className="font-bold text-gray-700">{t("db.type_word", { word: expectedWord })}</span>
                <input
                  value={confirmWord}
                  onChange={(e) => setConfirmWord(e.target.value)}
                  autoFocus
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-300 font-mono tracking-widest uppercase focus:outline-none focus:ring-2 focus:ring-rose-300"
                  placeholder={expectedWord}
                />
              </label>
              <label className="block space-y-1">
                <span className="font-bold text-gray-700">{t("db.owner_password")}</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-rose-300"
                />
              </label>
              <div className="flex justify-end gap-3 pt-1">
                <button type="button" onClick={() => setDanger(null)} disabled={busy} className="px-5 py-2.5 rounded-xl border border-gray-300 text-gray-700 font-bold hover:bg-gray-100">
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  onClick={handleDangerConfirm}
                  disabled={busy || !password || confirmWord.trim().toUpperCase() !== expectedWord}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-700 text-white font-extrabold shadow hover:bg-rose-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                  {danger.mode === "reset" ? t("db.reset_button") : t("db.restore")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
