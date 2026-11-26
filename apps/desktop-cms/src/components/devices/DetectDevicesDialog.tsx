import { useEffect, useState } from "react";
import { X, Search, Printer, Tags, Wifi, Cable, RefreshCw, CheckCircle2, Plus, AlertTriangle } from "lucide-react";
import { detectDevices, isTauriRuntime, type Detection, type DetectedPrinter } from "../../utils/posHardware";
import type { ConnectionType, DeviceType, ShopDevice } from "../../utils/shopDevices";
import { useEscapeToClose } from "../../utils/useEscapeToClose";
import { tr } from "../../i18n/translations";

/** What the Devices form is pre-filled with when a detected device is added. */
export interface DevicePrefill {
  name: string;
  device_type: DeviceType;
  connection_type: ConnectionType;
  windows_printer_name?: string;
  device_path?: string;
  host?: string;
  port?: string;
}

const STATE_STYLE: Record<string, string> = {
  ready: "bg-emerald-100 text-emerald-700",
  printing: "bg-emerald-100 text-emerald-700",
  offline: "bg-red-100 text-red-700",
  paused: "bg-amber-100 text-amber-700",
  unknown: "bg-gray-200 text-gray-600",
};

const lc = (v: unknown) => String(v ?? "").trim().toLowerCase();

/** Lists what this PC sees (printers installed in Windows, printers on the
 *  local network, serial / USB ports) and adds one to the shop's devices. */
export function DetectDevicesDialog({ devices, onAdd, onClose }: { devices: ShopDevice[]; onAdd: (p: DevicePrefill) => void; onClose: () => void }) {
  useEscapeToClose(onClose, true);
  const desktop = isTauriRuntime();
  const [found, setFound] = useState<Detection | null>(null);
  const [busy, setBusy] = useState<null | "local" | "network">(desktop ? "local" : null);
  const [error, setError] = useState<string | null>(null);

  const run = async (scanNetwork: boolean) => {
    setBusy(scanNetwork ? "network" : "local");
    setError(null);
    try {
      const d = await detectDevices(scanNetwork);
      if (d) setFound((prev) => (scanNetwork || !prev ? d : { ...d, network: prev.network, subnet: prev.subnet, network_scanned: prev.network_scanned }));
    } catch (e: any) {
      setError(String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    if (desktop) run(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const known = {
    printer: (p: DetectedPrinter) => devices.some((d) => [lc(p.name), lc(p.system_name)].includes(lc(d.config?.windows_printer_name))),
    host: (h: string) => devices.some((d) => lc(d.config?.host) === lc(h)),
    path: (p: string) => devices.some((d) => lc(d.config?.device_path) === lc(p)),
  };

  const addPrinter = (p: DetectedPrinter) => onAdd({
    name: p.name,
    device_type: p.kind === "label" ? "label_printer" : "receipt_printer",
    connection_type: /^usb/i.test(p.port_name) ? "usb" : "windows",
    windows_printer_name: p.name,
  });

  const already = <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700"><CheckCircle2 className="w-4 h-4" /> {tr("dvx.already_added")}</span>;
  const addBtn = (onClick: () => void, label: string) => (
    <button type="button" onClick={onClick} aria-label={label} className="h-9 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs flex items-center gap-1 active:scale-95 shrink-0">
      <Plus className="w-4 h-4" /> {tr("dvx.add")}
    </button>
  );

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="detect-title" className="bg-white rounded-3xl w-full max-w-2xl max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b sticky top-0 bg-white">
          <h3 id="detect-title" className="font-serif font-bold text-[#063D2E] text-lg flex items-center gap-2"><Search className="w-5 h-5" /> {tr("dvx.detect_title")}</h3>
          <button aria-label={tr("ui.close")} type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="p-5 space-y-5 text-sm">
          {!desktop ? (
            <div className="p-4 rounded-2xl bg-amber-50 border-2 border-amber-200 text-amber-900 flex gap-2"><AlertTriangle className="w-5 h-5 shrink-0" /> {tr("dvx.detect_desktop_only")}</div>
          ) : (
            <>
              {error && <div className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold">{error}</div>}

              <section>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-[#063D2E] flex items-center gap-2"><Printer className="w-4 h-4" /> {tr("dvx.sec_printers")}</h4>
                  <button type="button" onClick={() => run(false)} disabled={busy !== null} className="h-9 px-3 rounded-xl border-2 border-gray-200 font-bold text-xs flex items-center gap-1.5 disabled:opacity-50 active:scale-95">
                    <RefreshCw className={`w-4 h-4 ${busy === "local" ? "animate-spin" : ""}`} /> {tr("dvx.detect_again")}
                  </button>
                </div>
                {busy === "local" && !found ? <p className="text-gray-500">{tr("dvx.searching")}</p> : (found?.printers.length ?? 0) === 0 ? (
                  <p className="text-gray-500">{tr("dvx.no_printers")}</p>
                ) : (
                  <ul className="space-y-2">
                    {found!.printers.map((p) => (
                      <li key={p.system_name || p.name} data-testid="detected-printer" className={`p-3 rounded-2xl border flex items-center justify-between gap-3 ${p.kind === "virtual" ? "border-gray-100 bg-gray-50 opacity-70" : "border-gray-200 bg-[#FCFBF8]"}`}>
                        <div className="min-w-0">
                          <div className="font-bold text-[#063D2E] truncate flex items-center gap-2">
                            {p.kind === "label" ? <Tags className="w-4 h-4 shrink-0" /> : <Printer className="w-4 h-4 shrink-0" />}
                            {p.name}{p.is_default ? ` · ${tr("dvx.windows_default")}` : ""}
                          </div>
                          <div className="text-[11px] text-gray-500 flex flex-wrap items-center gap-1.5 mt-0.5">
                            <span className={`px-1.5 py-0.5 rounded font-bold ${STATE_STYLE[p.state] || STATE_STYLE.unknown}`}>{tr(`dvx.state_${p.state}`)}</span>
                            <span className="px-1.5 py-0.5 rounded bg-[#D4AF62]/20 text-[#7a5c16] font-bold">{tr(`dvx.kind_${p.kind}`)}</span>
                            {p.port_name && <span className="font-mono">{p.port_name}</span>}
                            {p.driver_name && <span className="truncate">· {p.driver_name}</span>}
                          </div>
                        </div>
                        {known.printer(p) ? already : addBtn(() => addPrinter(p), `${tr("dvx.add")} ${p.name}`)}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-[#063D2E] flex items-center gap-2"><Wifi className="w-4 h-4" /> {tr("dvx.sec_network")}</h4>
                  <button type="button" onClick={() => run(true)} disabled={busy !== null} className="h-9 px-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold text-xs flex items-center gap-1.5 disabled:opacity-50 active:scale-95">
                    <Search className={`w-4 h-4 ${busy === "network" ? "animate-pulse" : ""}`} /> {busy === "network" ? tr("dvx.searching_network") : tr("dvx.search_network")}
                  </button>
                </div>
                {!found?.network_scanned ? <p className="text-gray-500">{tr("dvx.network_hint")}</p>
                  : !found.subnet ? <p className="text-gray-500">{tr("dvx.no_local_network")}</p>
                  : found.network.length === 0 ? <p className="text-gray-500">{tr("dvx.no_network_printers", { net: found.subnet })}</p>
                  : (
                    <ul className="space-y-2">
                      <li className="text-[11px] text-gray-500">{tr("dvx.network_searched", { net: found.subnet })}</li>
                      {found.network.map((n) => (
                        <li key={n.host} data-testid="detected-network" className="p-3 rounded-2xl border border-gray-200 bg-[#FCFBF8] flex items-center justify-between gap-3">
                          <div className="font-mono font-bold text-[#063D2E]">{n.host}:{n.port}</div>
                          {known.host(n.host) ? already : addBtn(() => onAdd({ name: tr("dvx.network_printer_name", { host: n.host }), device_type: "receipt_printer", connection_type: "network", host: n.host, port: String(n.port) }), `${tr("dvx.add")} ${n.host}`)}
                        </li>
                      ))}
                    </ul>
                  )}
              </section>

              <section>
                <h4 className="font-bold text-[#063D2E] flex items-center gap-2 mb-2"><Cable className="w-4 h-4" /> {tr("dvx.sec_ports")}</h4>
                {(found?.ports.length ?? 0) === 0 ? <p className="text-gray-500">{tr("dvx.no_ports")}</p> : (
                  <ul className="space-y-2">
                    {found!.ports.map((p) => (
                      <li key={p.path} data-testid="detected-port" className="p-3 rounded-2xl border border-gray-200 bg-[#FCFBF8] flex items-center justify-between gap-3">
                        <div>
                          <div className="font-mono font-bold text-[#063D2E]">{p.path}</div>
                          <div className="text-[11px] text-gray-500">{tr(`dvx.port_${p.kind}`)}</div>
                        </div>
                        {known.path(p.path) ? already : addBtn(() => onAdd({ name: p.path, device_type: "receipt_printer", connection_type: p.kind === "serial" ? "serial" : "usb", device_path: p.path }), `${tr("dvx.add")} ${p.path}`)}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <p className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600">{tr("dvx.scanner_note")}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
