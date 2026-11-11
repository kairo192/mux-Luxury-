import React, { useEffect, useState } from "react";
import { X, Printer, RefreshCw, CheckCircle2, AlertTriangle, DoorOpen, Zap, Wifi, Tag, Database, Trash2 } from "lucide-react";
import {
  listPrinters,
  loadHardwareSettings,
  saveHardwareSettings,
  testPrint,
  openCashDrawer,
  isTauriRuntime,
  loadLabelPrinterSettings,
  saveLabelPrinterSettings,
  testPrintLabel,
  type PrinterInfo,
  type PrinterTarget,
  type LabelPrinterTarget,
} from "../utils/posHardware";
import { mirrorStatus, mirrorClear, type MirrorStatus } from "../utils/posMirror";
import { syncCatalog } from "../utils/posMirrorSync";
import { confirmClientAction } from "../utils/clientNotifier";
import { useT } from "../i18n";
import { useEscapeToClose } from "../utils/useEscapeToClose";

// ---------------------------------------------------------------------------
// PrinterSettingsModal — configure the thermal receipt printer, cash drawer
// pin, and paper width. Writes to localStorage via saveHardwareSettings.
// Also exposes "Imprimer un test" and "Ouvrir le tiroir" buttons so the
// cashier can verify the setup without recording a real sale.
// ---------------------------------------------------------------------------
interface Props {
  open: boolean;
  onClose: () => void;
  onFlash?: (kind: "ok" | "err", msg: string) => void;
}

export const PrinterSettingsModal: React.FC<Props> = ({ open, onClose, onFlash }) => {
  useEscapeToClose(onClose, open);
  const t = useT();
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);
  const [settings, setSettings] = useState<PrinterTarget>(() => loadHardwareSettings());
  const [labelSettings, setLabelSettings] = useState<LabelPrinterTarget>(() => loadLabelPrinterSettings());
  const [loadingPrinters, setLoadingPrinters] = useState(false);
  const [testing, setTesting] = useState<null | "print" | "drawer" | "label">(null);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [tab, setTab] = useState<"receipt" | "label" | "mirror">("receipt");
  const [mirror, setMirror] = useState<MirrorStatus | null>(null);
  const [mirrorBusy, setMirrorBusy] = useState<null | "sync" | "clear">(null);
  const inTauri = isTauriRuntime();

  const refresh = async () => {
    setLoadingPrinters(true);
    try {
      const p = await listPrinters();
      setPrinters(p);
    } finally {
      setLoadingPrinters(false);
    }
  };

  useEffect(() => {
    if (open) {
      setStatus(null);
      refresh();
      setSettings(loadHardwareSettings());
      setLabelSettings(loadLabelPrinterSettings());
      mirrorStatus().then(setMirror);
    }
  }, [open]);

  const refreshMirrorStat = async () => setMirror(await mirrorStatus());

  const onSyncNow = async (force: boolean) => {
    setMirrorBusy("sync");
    const r = await syncCatalog(force);
    await refreshMirrorStat();
    setMirrorBusy(null);
    if (r.ok) flash("ok", force
      ? `Catalogue rechargé (${r.variants_upserted} variantes).`
      : `Mise à jour: ${r.variants_upserted} variantes.`);
    else flash("err", r.error ?? "Sync échouée");
  };

  const onClearMirror = async () => {
    const confirmed = await confirmClientAction({
      title: t("common.delete"),
      message: t("printer_settings.prompt_clear"),
      danger: true,
    });
    if (!confirmed) return;
    setMirrorBusy("clear");
    await mirrorClear();
    await refreshMirrorStat();
    setMirrorBusy(null);
    flash("ok", t("printer_settings.flash_cache_cleared"));
  };

  if (!open) return null;

  const flash = (kind: "ok" | "err", msg: string) => {
    setStatus({ kind, msg });
    onFlash?.(kind, msg);
  };

  const saveReceipt = () => {
    const normalised: PrinterTarget = {
      printer_name: settings.printer_name?.trim() || null,
      device_path: settings.device_path?.trim() || null,
      line_width: Number(settings.line_width) || 32,
      drawer_pin: settings.drawer_pin === 5 ? 5 : 2,
    };
    saveHardwareSettings(normalised);
    setSettings(normalised);
  };

  const saveLabel = () => {
    const normalised: LabelPrinterTarget = {
      printer_name: labelSettings.printer_name?.trim() || null,
      device_path: labelSettings.device_path?.trim() || null,
      format: labelSettings.format === "escpos-text" ? "escpos-text" : "zpl",
      width_mm: Number(labelSettings.width_mm) || 50,
      height_mm: Number(labelSettings.height_mm) || 30,
      dpi: (labelSettings.dpi === 300 || labelSettings.dpi === 600 ? labelSettings.dpi : 203),
    };
    saveLabelPrinterSettings(normalised);
    setLabelSettings(normalised);
  };

  const saveAll = () => {
    saveReceipt();
    saveLabel();
    flash("ok", t("printer_settings.flash_saved"));
  };

  const onTestPrint = async () => {
    saveReceipt();
    setTesting("print");
    const r = await testPrint(settings);
    setTesting(null);
    if (r.ok) flash("ok", t("printer_settings.flash_test_receipt"));
    else flash("err", r.error);
  };

  const onOpenDrawer = async () => {
    saveReceipt();
    setTesting("drawer");
    const r = await openCashDrawer(settings);
    setTesting(null);
    if (r.ok) flash("ok", t("printer_settings.flash_drawer"));
    else flash("err", r.error);
  };

  const onTestLabel = async () => {
    saveLabel();
    setTesting("label");
    const r = await testPrintLabel(labelSettings);
    setTesting(null);
    if (r.ok) flash("ok", t("printer_settings.flash_test_label"));
    else flash("err", r.error);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl border-2 border-[#063D2E] overflow-hidden">
        <div className="flex items-center justify-between p-5 bg-[#063D2E] text-[#D4AF62]">
          <div className="flex items-center gap-2 font-bold text-lg">
            <Printer className="w-6 h-6" /> {t("printer_settings.title")}
          </div>
          <button aria-label="Fermer" type="button" onClick={onClose} className="h-10 w-10 flex items-center justify-center rounded-full hover:bg-white/10 active:scale-95">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 pt-4 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("receipt")}
            className={`flex-1 h-11 rounded-2xl font-bold flex items-center justify-center gap-2 active:scale-95 ${tab === "receipt" ? "bg-[#063D2E] text-[#D4AF62]" : "bg-gray-100 text-gray-500"}`}
          >
            <Printer className="w-4 h-4" /> {t("printer_settings.tab_receipts")}
          </button>
          <button
            type="button"
            onClick={() => setTab("label")}
            className={`flex-1 h-11 rounded-2xl font-bold flex items-center justify-center gap-2 active:scale-95 ${tab === "label" ? "bg-[#063D2E] text-[#D4AF62]" : "bg-gray-100 text-gray-500"}`}
          >
            <Tag className="w-4 h-4" /> {t("printer_settings.tab_labels")}
          </button>
          <button
            type="button"
            onClick={() => setTab("mirror")}
            className={`flex-1 h-11 rounded-2xl font-bold flex items-center justify-center gap-2 active:scale-95 ${tab === "mirror" ? "bg-[#063D2E] text-[#D4AF62]" : "bg-gray-100 text-gray-500"}`}
          >
            <Database className="w-4 h-4" /> {t("printer_settings.tab_catalog")}
          </button>
        </div>

        <div className="p-5 space-y-4 text-sm">
          {!inTauri && (
            <div className="p-3 rounded-2xl bg-amber-50 border-2 border-amber-200 text-amber-900 flex gap-2 items-start">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                {t("printer_settings.browser_warning")}
              </div>
            </div>
          )}

          {status && (
            <div className={`p-3 rounded-2xl border-2 flex gap-2 items-start ${status.kind === "ok" ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-red-50 border-red-200 text-red-900"}`}>
              {status.kind === "ok" ? <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" /> : <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />}
              <div className="font-semibold">{status.msg}</div>
            </div>
          )}

          {tab === "receipt" ? <>
          <div className="space-y-2">
            <label className="flex items-center justify-between gap-2 font-bold text-[#063D2E]">
              <span className="flex items-center gap-2"><Wifi className="w-4 h-4" /> {t("printer_settings.sys_printer")}</span>
              <button type="button" onClick={refresh} className="h-9 px-3 rounded-xl bg-[#063D2E]/10 text-[#063D2E] font-bold flex items-center gap-1.5 active:scale-95">
                <RefreshCw className={`w-4 h-4 ${loadingPrinters ? "animate-spin" : ""}`} /> {t("printer_settings.btn_refresh")}
              </button>
            </label>
            <select
              value={settings.printer_name ?? ""}
              onChange={(e) => setSettings(s => ({ ...s, printer_name: e.target.value || null }))}
              className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
              disabled={!inTauri}
            >
              <option value="">{t("printer_settings.default_printer_opt")}</option>
              {printers.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.is_default ? t("printer_settings.default_suffix") : ""} · {p.state}
                </option>
              ))}
            </select>
            {inTauri && !printers.length && !loadingPrinters && (
              <div className="text-xs text-gray-500">
                {t("printer_settings.no_printers_detected")}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label className="font-bold text-[#063D2E]">
              {t("printer_settings.raw_device_path")}
            </label>
            <input
              type="text"
              value={settings.device_path ?? ""}
              onChange={(e) => setSettings(s => ({ ...s, device_path: e.target.value || null }))}
              placeholder="Ex: /dev/usb/lp0, LPT1, COM3"
              className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] font-mono text-sm"
            />
            <div className="text-xs text-gray-500">
              {t("printer_settings.raw_device_hint")}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="font-bold text-[#063D2E]">{t("printer_settings.ticket_width")}</label>
              <select
                value={settings.line_width ?? 32}
                onChange={(e) => setSettings(s => ({ ...s, line_width: Number(e.target.value) }))}
                className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
              >
                <option value={32}>58 mm — 32 caractères</option>
                <option value={42}>80 mm — 42 caractères</option>
                <option value={48}>80 mm — 48 caractères</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="font-bold text-[#063D2E]">{t("printer_settings.drawer_pin")}</label>
              <select
                value={settings.drawer_pin ?? 2}
                onChange={(e) => setSettings(s => ({ ...s, drawer_pin: (Number(e.target.value) === 5 ? 5 : 2) }))}
                className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
              >
                <option value={2}>Pin 2 (Epson, Star — par défaut)</option>
                <option value={5}>Pin 5 (Citizen, variantes)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <button
              type="button"
              onClick={onTestPrint}
              disabled={testing !== null || !inTauri}
              className="h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
            >
              <Zap className="w-5 h-5" /> {testing === "print" ? t("printer_settings.btn_test_print_sending") : t("printer_settings.btn_test_print")}
            </button>
            <button
              type="button"
              onClick={onOpenDrawer}
              disabled={testing !== null || !inTauri}
              className="h-14 rounded-2xl bg-[#D4AF62] text-[#063D2E] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
            >
              <DoorOpen className="w-5 h-5" /> {testing === "drawer" ? t("printer_settings.btn_open_drawer_sending") : t("printer_settings.btn_open_drawer")}
            </button>
          </div>
          </> : tab === "label" ? (
          <>
            {/* ========== LABEL PRINTER TAB ========== */}
            <div className="space-y-2">
              <label className="flex items-center justify-between gap-2 font-bold text-[#063D2E]">
                <span className="flex items-center gap-2"><Tag className="w-4 h-4" /> {t("printer_settings.label_printer")}</span>
              </label>
              <select
                value={labelSettings.printer_name ?? ""}
                onChange={(e) => setLabelSettings(s => ({ ...s, printer_name: e.target.value || null }))}
                className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
                disabled={!inTauri}
              >
                <option value="">{t("printer_settings.no_label_printer_opt")}</option>
                {printers.map(p => (
                  <option key={`lbl-${p.name}`} value={p.name}>
                    {p.name}{p.is_default ? t("printer_settings.default_suffix") : ""} · {p.state}
                  </option>
                ))}
              </select>
              <div className="text-xs text-gray-500">
                {t("printer_settings.label_printer_hint")}
              </div>
            </div>

            <div className="space-y-2">
              <label className="font-bold text-[#063D2E]">{t("printer_settings.raw_device_path")}</label>
              <input
                type="text"
                value={labelSettings.device_path ?? ""}
                onChange={(e) => setLabelSettings(s => ({ ...s, device_path: e.target.value || null }))}
                placeholder="Ex: /dev/usb/lp1, USB001, COM4"
                className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] font-mono text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="font-bold text-[#063D2E]">{t("printer_settings.protocol")}</label>
                <select
                  value={labelSettings.format ?? "zpl"}
                  onChange={(e) => setLabelSettings(s => ({ ...s, format: e.target.value === "escpos-text" ? "escpos-text" : "zpl" }))}
                  className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
                >
                  <option value="zpl">{t("printer_settings.protocol_zpl")}</option>
                  <option value="escpos-text">{t("printer_settings.protocol_escpos")}</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="font-bold text-[#063D2E]">{t("printer_settings.resolution")}</label>
                <select
                  value={labelSettings.dpi ?? 203}
                  onChange={(e) => setLabelSettings(s => ({ ...s, dpi: (Number(e.target.value) === 300 ? 300 : Number(e.target.value) === 600 ? 600 : 203) }))}
                  className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
                  disabled={labelSettings.format === "escpos-text"}
                >
                  <option value={203}>203 dpi (standard)</option>
                  <option value={300}>300 dpi (haute définition)</option>
                  <option value={600}>600 dpi (très haute définition)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="font-bold text-[#063D2E]">{t("printer_settings.width_mm")}</label>
                <input
                  type="number" min={10} max={210}
                  value={labelSettings.width_mm ?? 50}
                  onChange={(e) => setLabelSettings(s => ({ ...s, width_mm: Number(e.target.value) || 50 }))}
                  className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
                />
              </div>
              <div className="space-y-2">
                <label className="font-bold text-[#063D2E]">{t("printer_settings.height_mm")}</label>
                <input
                  type="number" min={10} max={297}
                  value={labelSettings.height_mm ?? 30}
                  onChange={(e) => setLabelSettings(s => ({ ...s, height_mm: Number(e.target.value) || 30 }))}
                  className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={onTestLabel}
                disabled={testing !== null || !inTauri}
                className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
              >
                <Zap className="w-5 h-5" /> {testing === "label" ? t("printer_settings.btn_test_print_sending") : t("printer_settings.btn_test_label")}
              </button>
            </div>
          </>) : (
          <>
            {/* ========== LOCAL CATALOG MIRROR TAB ========== */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 font-bold text-[#063D2E]">
                <Database className="w-4 h-4" /> {t("printer_settings.catalog_mirror_title")}
              </label>
              <div className="text-xs text-gray-500">
                {t("printer_settings.catalog_mirror_desc")}
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="p-3 rounded-2xl bg-[#FCFBF8] border border-gray-100 text-center">
                  <div className="text-[11px] text-gray-500 uppercase tracking-wide">{t("printer_settings.stat_products")}</div>
                  <div className="font-mono font-bold text-xl text-[#063D2E]">{mirror?.product_count ?? "—"}</div>
                </div>
                <div className="p-3 rounded-2xl bg-[#FCFBF8] border border-gray-100 text-center">
                  <div className="text-[11px] text-gray-500 uppercase tracking-wide">{t("printer_settings.stat_variants")}</div>
                  <div className="font-mono font-bold text-xl text-[#063D2E]">{mirror?.variant_count ?? "—"}</div>
                </div>
                <div className="p-3 rounded-2xl bg-[#FCFBF8] border border-gray-100 text-center">
                  <div className="text-[11px] text-gray-500 uppercase tracking-wide">{t("printer_settings.stat_barcodes")}</div>
                  <div className="font-mono font-bold text-xl text-[#063D2E]">{mirror?.variants_with_barcode ?? "—"}</div>
                </div>
              </div>

              <div className="text-xs text-gray-500 font-mono break-all">
                {mirror?.last_synced_at
                  ? t("printer_settings.last_sync", { date: new Date(mirror.last_synced_at).toLocaleString("fr-DZ") })
                  : t("printer_settings.never_synced")}
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <button
                  type="button"
                  disabled={mirrorBusy !== null || !inTauri}
                  onClick={() => onSyncNow(false)}
                  className="h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
                >
                  <RefreshCw className={`w-5 h-5 ${mirrorBusy === "sync" ? "animate-spin" : ""}`} />
                  {t("printer_settings.btn_sync")}
                </button>
                <button
                  type="button"
                  disabled={mirrorBusy !== null || !inTauri}
                  onClick={() => onSyncNow(true)}
                  className="h-14 rounded-2xl bg-[#D4AF62] text-[#063D2E] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
                  title="Recharge la totalité du catalogue"
                >
                  <Database className="w-5 h-5" /> {t("printer_settings.btn_full_reload")}
                </button>
              </div>

              <button
                type="button"
                disabled={mirrorBusy !== null || !inTauri}
                onClick={onClearMirror}
                className="w-full h-11 rounded-2xl border-2 border-red-200 text-red-600 font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
              >
                <Trash2 className="w-4 h-4" /> {t("printer_settings.btn_clear_cache")}
              </button>
            </div>
          </>)}
        </div>

        <div className="p-4 bg-gray-50 border-t-2 border-gray-100 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="h-11 px-4 rounded-xl bg-white border-2 border-gray-200 font-bold active:scale-95">
            {t("printer_settings.btn_close")}
          </button>
          <button type="button" onClick={() => { saveAll(); onClose(); }} className="h-11 px-5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <CheckCircle2 className="w-4 h-4" /> {t("printer_settings.btn_save")}
          </button>
        </div>
      </div>
    </div>
  );
};
