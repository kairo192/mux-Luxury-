import React, { useEffect, useState } from "react";
import { X, Printer, RefreshCw, CheckCircle2, AlertTriangle, DoorOpen, Zap, Wifi } from "lucide-react";
import {
  listPrinters,
  loadHardwareSettings,
  saveHardwareSettings,
  testPrint,
  openCashDrawer,
  isTauriRuntime,
  type PrinterInfo,
  type PrinterTarget,
} from "../utils/posHardware";

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
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);
  const [settings, setSettings] = useState<PrinterTarget>(() => loadHardwareSettings());
  const [loadingPrinters, setLoadingPrinters] = useState(false);
  const [testing, setTesting] = useState<null | "print" | "drawer">(null);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
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
    }
  }, [open]);

  if (!open) return null;

  const flash = (kind: "ok" | "err", msg: string) => {
    setStatus({ kind, msg });
    onFlash?.(kind, msg);
  };

  const save = () => {
    const normalised: PrinterTarget = {
      printer_name: settings.printer_name?.trim() || null,
      device_path: settings.device_path?.trim() || null,
      line_width: Number(settings.line_width) || 32,
      drawer_pin: settings.drawer_pin === 5 ? 5 : 2,
    };
    saveHardwareSettings(normalised);
    setSettings(normalised);
    flash("ok", "Paramètres enregistrés");
  };

  const onTestPrint = async () => {
    save();
    setTesting("print");
    const r = await testPrint(settings);
    setTesting(null);
    if (r.ok) flash("ok", "Test envoyé à l'imprimante");
    else flash("err", r.error);
  };

  const onOpenDrawer = async () => {
    save();
    setTesting("drawer");
    const r = await openCashDrawer(settings);
    setTesting(null);
    if (r.ok) flash("ok", "Impulsion envoyée au tiroir");
    else flash("err", r.error);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl border-2 border-[#063D2E] overflow-hidden">
        <div className="flex items-center justify-between p-5 bg-[#063D2E] text-[#D4AF62]">
          <div className="flex items-center gap-2 font-bold text-lg">
            <Printer className="w-6 h-6" /> Imprimante & tiroir-caisse
          </div>
          <button type="button" onClick={onClose} className="h-10 w-10 flex items-center justify-center rounded-full hover:bg-white/10 active:scale-95">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 text-sm">
          {!inTauri && (
            <div className="p-3 rounded-2xl bg-amber-50 border-2 border-amber-200 text-amber-900 flex gap-2 items-start">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                Vous utilisez le navigateur. L'impression et le tiroir-caisse
                nécessitent l'application de bureau Mus Luxury.
              </div>
            </div>
          )}

          {status && (
            <div className={`p-3 rounded-2xl border-2 flex gap-2 items-start ${status.kind === "ok" ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-red-50 border-red-200 text-red-900"}`}>
              {status.kind === "ok" ? <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" /> : <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />}
              <div className="font-semibold">{status.msg}</div>
            </div>
          )}

          <div className="space-y-2">
            <label className="flex items-center justify-between gap-2 font-bold text-[#063D2E]">
              <span className="flex items-center gap-2"><Wifi className="w-4 h-4" /> Imprimante système</span>
              <button type="button" onClick={refresh} className="h-9 px-3 rounded-xl bg-[#063D2E]/10 text-[#063D2E] font-bold flex items-center gap-1.5 active:scale-95">
                <RefreshCw className={`w-4 h-4 ${loadingPrinters ? "animate-spin" : ""}`} /> Rafraîchir
              </button>
            </label>
            <select
              value={settings.printer_name ?? ""}
              onChange={(e) => setSettings(s => ({ ...s, printer_name: e.target.value || null }))}
              className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] text-base"
              disabled={!inTauri}
            >
              <option value="">— Utiliser l'imprimante par défaut du système —</option>
              {printers.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.is_default ? " (par défaut)" : ""} · {p.state}
                </option>
              ))}
            </select>
            {inTauri && !printers.length && !loadingPrinters && (
              <div className="text-xs text-gray-500">
                Aucune imprimante détectée. Vérifiez que l'imprimante est allumée et installée dans Windows / macOS / CUPS.
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label className="font-bold text-[#063D2E]">
              …ou chemin d'appareil brut (optionnel)
            </label>
            <input
              type="text"
              value={settings.device_path ?? ""}
              onChange={(e) => setSettings(s => ({ ...s, device_path: e.target.value || null }))}
              placeholder="Ex: /dev/usb/lp0, LPT1, COM3"
              className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] font-mono text-sm"
            />
            <div className="text-xs text-gray-500">
              Utilisez cette option pour les imprimantes série ou USB-CDC qui n'apparaissent pas comme imprimante système.
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="font-bold text-[#063D2E]">Largeur du ticket</label>
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
              <label className="font-bold text-[#063D2E]">Pin du tiroir-caisse</label>
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
              <Zap className="w-5 h-5" /> {testing === "print" ? "Envoi…" : "Imprimer un test"}
            </button>
            <button
              type="button"
              onClick={onOpenDrawer}
              disabled={testing !== null || !inTauri}
              className="h-14 rounded-2xl bg-[#D4AF62] text-[#063D2E] font-bold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-95"
            >
              <DoorOpen className="w-5 h-5" /> {testing === "drawer" ? "Envoi…" : "Ouvrir le tiroir"}
            </button>
          </div>
        </div>

        <div className="p-4 bg-gray-50 border-t-2 border-gray-100 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="h-11 px-4 rounded-xl bg-white border-2 border-gray-200 font-bold active:scale-95">
            Fermer
          </button>
          <button type="button" onClick={() => { save(); onClose(); }} className="h-11 px-5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <CheckCircle2 className="w-4 h-4" /> Enregistrer
          </button>
        </div>
      </div>
    </div>
  );
};
