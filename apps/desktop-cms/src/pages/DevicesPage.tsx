import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Printer,
  ScanLine,
  Tags,
  Monitor,
  Archive,
  HardDrive,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Star,
  Trash2,
  Pencil,
  Activity,
  X,
  Info,
  Search,
  Laptop,
  DoorOpen,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { confirmClientAction } from "../utils/clientNotifier";
import { useT } from "../i18n";
import {
  isTauriRuntime,
  testPrint,
  testPrintLabel,
  checkPrinter,
  openCashDrawer,
  detectDevices,
  type Detection,
} from "../utils/posHardware";
import { openSystemPrint } from "../utils/systemPrint";
import { serverDate } from "../utils/serverDate";
import { localeFor, tr } from "../i18n/translations";
import {
  drawerTarget,
  isUsedOnThisPc,
  labelTargetFromDevice,
  targetFromDevice,
  setAsThisPcPrinter,
  type ConnectionType,
  type DeviceType,
  type ShopDevice,
} from "../utils/shopDevices";
import { DetectDevicesDialog, type DevicePrefill } from "../components/devices/DetectDevicesDialog";
import { ScanTestDialog } from "../components/devices/ScanTestDialog";

type Device = ShopDevice;

const TYPE_ICON: Record<DeviceType, any> = {
  receipt_printer: Printer,
  label_printer: Tags,
  barcode_scanner: ScanLine,
  cash_drawer: Archive,
  customer_display: Monitor,
  other: HardDrive,
};

const CONNECTION_LABEL: Record<ConnectionType, string> = {
  usb: "USB",
  network: "TCP / IP",
  windows: "Windows",
  serial: "RS232 / COM",
  hid_keyboard: "HID",
  browser: "Browser",
};

/** Connections that make sense for each kind of device. */
const CONNECTIONS_FOR: Record<DeviceType, ConnectionType[]> = {
  receipt_printer: ["windows", "usb", "network", "serial"],
  label_printer: ["windows", "usb", "network", "serial"],
  barcode_scanner: ["hid_keyboard", "serial"],
  cash_drawer: ["usb"],
  customer_display: ["serial", "usb", "network"],
  other: ["usb", "network", "windows", "serial", "hid_keyboard"],
};

const STATUS_STYLE: Record<string, string> = {
  ok: "bg-emerald-100 text-emerald-700",
  error: "bg-red-100 text-red-700",
  offline: "bg-amber-100 text-amber-700",
  unknown: "bg-gray-200 text-gray-600",
};

const isPrinterType = (t: DeviceType) => t === "receipt_printer" || t === "label_printer";

const emptyForm = {
  id: null as number | null,
  name: "",
  device_type: "receipt_printer" as DeviceType,
  connection_type: "windows" as ConnectionType,
  location: "",
  host: "",
  port: "",
  windows_printer_name: "",
  device_path: "",
  paper_width_mm: "80",
  prefix: "",
  suffix: "",
  drawer_pin: "2",
  printer_device_id: "",
  label_format: "zpl",
};

type Form = typeof emptyForm;

export const DevicesPage: React.FC = () => {
  const t = useT();
  const desktop = isTauriRuntime();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [detectOpen, setDetectOpen] = useState(false);
  const [scanFor, setScanFor] = useState<Device | null>(null);
  const [seen, setSeen] = useState<Detection | null>(null);
  const [, bump] = useState(0);

  const typeLabels = useMemo<Record<DeviceType, string>>(() => ({
    receipt_printer: t("devices.receipt_printer"),
    label_printer: t("devices.label_printer"),
    barcode_scanner: t("devices.barcode_scanner"),
    cash_drawer: t("devices.cash_drawer"),
    customer_display: t("devices.type_customer_display"),
    other: t("devices.type_other"),
  }), [t]);

  const statusLabels = useMemo<Record<string, string>>(() => ({
    ok: t("devices.status_ok"),
    error: t("devices.status_error"),
    offline: t("devices.status_offline"),
    unknown: t("devices.status_unknown"),
  }), [t]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listDevices();
      setDevices(d.items || []);
    } catch (e: any) {
      setError(e?.userMessage || t("status.error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  // Printers / ports of this PC, for the choices of the form.
  useEffect(() => {
    if (form && desktop && !seen) detectDevices(false).then((d) => d && setSeen(d)).catch(() => undefined);
  }, [form, desktop, seen]);

  const flash = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 5000);
  };
  const fail = (msg: string) => {
    setError(msg);
    setSuccess(null);
  };

  /** Record the result of a test on the server (status shown to everyone). */
  const report = async (dev: Device, ok: boolean, err?: string) => {
    try {
      await DesktopCmsApi.testDevice(dev.id, ok ? { success: true } : { success: false, error: (err || t("dev.print_test_failed")).slice(0, 480) });
    } catch (e: any) {
      fail(e?.userMessage || t("status.error"));
    }
    load();
  };

  const buildConfig = (f: Form) => {
    const cfg: Record<string, any> = {};
    if (f.connection_type === "network") {
      cfg.host = f.host.trim();
      cfg.port = parseInt(f.port || "9100", 10) || 9100;
    }
    if ((f.connection_type === "windows" || f.connection_type === "usb") && f.windows_printer_name.trim()) cfg.windows_printer_name = f.windows_printer_name.trim();
    if ((f.connection_type === "usb" || f.connection_type === "serial") && f.device_path.trim()) cfg.device_path = f.device_path.trim();
    if (isPrinterType(f.device_type)) cfg.paper_width_mm = parseInt(f.paper_width_mm || "80", 10);
    if (f.device_type === "label_printer") cfg.label_format = f.label_format === "escpos-text" ? "escpos-text" : "zpl";
    if (f.device_type === "barcode_scanner") {
      if (f.prefix) cfg.prefix = f.prefix;
      if (f.suffix) cfg.suffix = f.suffix;
    }
    if (f.device_type === "cash_drawer") {
      cfg.drawer_pin = f.drawer_pin === "5" ? 5 : 2;
      if (f.printer_device_id) cfg.printer_device_id = Number(f.printer_device_id);
    }
    return cfg;
  };

  /** What is missing for the device to be reachable (null when complete). */
  const missing = (f: Form): string | null => {
    if (!f.name.trim()) return t("dvx.need_name");
    if (f.connection_type === "network" && !f.host.trim()) return t("dvx.need_host");
    if (f.connection_type === "network" && f.port && !(Number(f.port) >= 1 && Number(f.port) <= 65535)) return t("dvx.need_port");
    if (isPrinterType(f.device_type)) {
      if (f.connection_type === "windows" && !f.windows_printer_name.trim()) return t("dvx.need_printer");
      if (f.connection_type === "usb" && !f.windows_printer_name.trim() && !f.device_path.trim()) return t("dvx.need_printer_or_port");
    }
    if (f.connection_type === "serial" && f.device_type !== "barcode_scanner" && !f.device_path.trim()) return t("dvx.need_port_path");
    return null;
  };

  const save = async () => {
    if (!form) return;
    const why = missing(form);
    if (why) return setFormError(why);
    setFormError(null);
    setBusy(-1);
    try {
      const config = buildConfig(form);
      if (form.id === null) {
        await DesktopCmsApi.createDevice({
          name: form.name.trim(),
          device_type: form.device_type,
          connection_type: form.connection_type,
          location: form.location.trim() || null,
          config,
        });
      } else {
        await DesktopCmsApi.updateDevice(form.id, { name: form.name.trim(), location: form.location.trim() || null, config });
      }
      flash(t("common.saved"));
      setForm(null);
      load();
    } catch (e: any) {
      setFormError(e?.userMessage || t("status.error"));
    } finally {
      setBusy(null);
    }
  };

  const withBusy = async (dev: Device, job: () => Promise<void>) => {
    setBusy(dev.id);
    try {
      await job();
    } catch (e: any) {
      fail(e?.userMessage || String(e?.message ?? e) || t("status.error"));
    } finally {
      setBusy(null);
    }
  };

  // "Test": checks the device WITHOUT printing. Printers are plugged into the
  // shop PC: the desktop app checks them there; the server is only asked for
  // a network printer when the CMS runs in a browser (it says honestly when it
  // cannot see the shop's network).
  const runTest = (dev: Device) => withBusy(dev, async () => {
    if (dev.device_type === "barcode_scanner") {
      setScanFor(dev);
      return;
    }
    if (dev.device_type === "cash_drawer") {
      if (!desktop) return fail(t("dvx.desktop_needed"));
      const target = drawerTarget(dev, devices);
      if (!target) return fail(t("dvx.drawer_no_printer"));
      const r = await openCashDrawer(target);
      if (!r.ok) {
        fail(`${dev.name} : ${r.error}`);
        return report(dev, false, r.error);
      }
      const opened = await confirmClientAction({ title: t("dvx.drawer_title"), message: t("dvx.drawer_question", { name: dev.name }), confirmLabel: t("dvx.yes_opened"), cancelLabel: t("dev.no") });
      if (opened) flash(t("dvx.drawer_ok", { name: dev.name }));
      else fail(t("dvx.drawer_not_opened", { name: dev.name }));
      return report(dev, opened, opened ? undefined : t("dvx.drawer_not_opened_short"));
    }
    if (isPrinterType(dev.device_type) && desktop) {
      const r = await checkPrinter(targetFromDevice(dev));
      if (r.ok) flash(t("dvx.check_ok", { name: dev.name, state: t(`dvx.state_${r.state || "unknown"}`) }));
      else fail(`${dev.name} : ${r.error}`);
      return report(dev, r.ok, r.error);
    }
    if (isPrinterType(dev.device_type) && dev.connection_type !== "network") return fail(t("dev.desktop_only"));
    const res = await DesktopCmsApi.testDevice(dev.id);
    if (res.status === "ok") flash(t("dvx.check_ok", { name: dev.name, state: t("dvx.state_reachable") }));
    else fail(`${dev.name} : ${res.last_error || t("dev.state_unknown")}`);
    load();
  });

  // "Print test": a real ticket / label. Only the person in front of the
  // printer knows whether it came out (and is readable): ask, then record.
  const printTest = (dev: Device) => withBusy(dev, async () => {
    if (desktop) {
      const r = dev.device_type === "label_printer"
        ? await testPrintLabel(labelTargetFromDevice(dev))
        : await testPrint(targetFromDevice(dev), dev.name);
      if (!r.ok) {
        fail(`${dev.name} : ${r.error}`);
        return report(dev, false, r.error);
      }
    } else {
      const width = Number(dev.config?.paper_width_mm) === 58 ? 58 : 80;
      const esc = (v: string) => v.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
      const r = openSystemPrint({
        title: `Test ${dev.name}`,
        paper: { kind: "mm", width, height: 120 },
        marginMm: 3,
        html: `<div class="page" style="font-family:monospace;text-align:center;font-size:12px">
          <div style="font-weight:700">Mus Luxury</div><div>${esc(t("dev.test_page"))}</div><div>${esc(dev.name)}</div>
          <div>${esc(new Date().toLocaleString(localeFor()))}</div><div>................................</div><div>${esc(t("dev.printer_ok"))}</div></div>`,
      });
      if (!r.ok) return fail(`${dev.name} : ${r.error}`);
    }
    const printed = await confirmClientAction({
      title: t("dev.test_title"),
      message: t(dev.device_type === "label_printer" ? "dvx.label_question" : "dvx.print_question", { name: dev.name }),
      confirmLabel: t("dev.yes_printed"),
      cancelLabel: t("dev.no"),
    });
    if (printed) flash(t("dvx.print_ok", { name: dev.name }));
    else fail(t("dev.not_out", { name: dev.name }));
    return report(dev, printed, printed ? undefined : t("dev.not_out_server"));
  });

  const makeThisPcPrinter = (dev: Device) => {
    setAsThisPcPrinter(dev);
    bump((n) => n + 1);
    flash(t(dev.device_type === "label_printer" ? "dvx.used_label" : "dvx.used_receipt", { name: dev.name }));
  };

  const setDefault = (dev: Device) => withBusy(dev, async () => {
    await DesktopCmsApi.setDefaultDevice(dev.id);
    flash(`${dev.name} ${t("devices.badge_default")}`);
    load();
  });

  const remove = async (dev: Device) => {
    const confirmed = await confirmClientAction({
      title: t("common.delete"),
      message: `${t("common.delete")} « ${dev.name} » ?`,
      danger: true,
    });
    if (!confirmed) return;
    await withBusy(dev, async () => {
      await DesktopCmsApi.deleteDevice(dev.id);
      flash(t("common.deleted"));
      load();
    });
  };

  const editDevice = (dev: Device) => {
    setFormError(null);
    setForm({
      ...emptyForm,
      id: dev.id,
      name: dev.name,
      device_type: dev.device_type,
      connection_type: dev.connection_type,
      location: dev.location || "",
      host: dev.config?.host || "",
      port: dev.config?.port ? String(dev.config.port) : "",
      windows_printer_name: dev.config?.windows_printer_name || "",
      device_path: dev.config?.device_path || "",
      paper_width_mm: dev.config?.paper_width_mm ? String(dev.config.paper_width_mm) : "80",
      prefix: dev.config?.prefix || "",
      suffix: dev.config?.suffix || "",
      drawer_pin: Number(dev.config?.drawer_pin) === 5 ? "5" : "2",
      printer_device_id: dev.config?.printer_device_id ? String(dev.config.printer_device_id) : "",
      label_format: dev.config?.label_format === "escpos-text" ? "escpos-text" : "zpl",
    });
  };

  const newFrom = (p?: DevicePrefill) => {
    setDetectOpen(false);
    setFormError(null);
    setForm({ ...emptyForm, ...(p || {}), port: p?.port || "", host: p?.host || "", device_path: p?.device_path || "", windows_printer_name: p?.windows_printer_name || "" } as Form);
  };

  const receiptPrinters = devices.filter((d) => d.device_type === "receipt_printer");
  const describe = (dev: Device) => {
    const c = dev.config || {};
    if (dev.device_type === "cash_drawer") {
      const p = receiptPrinters.find((d) => d.id === Number(c.printer_device_id)) || receiptPrinters.find((d) => d.is_default);
      return `${t("dvx.via_printer", { name: p ? p.name : t("dvx.this_pc_printer") })} · ${t("dvx.pin", { n: Number(c.drawer_pin) === 5 ? 5 : 2 })}`;
    }
    return [
      CONNECTION_LABEL[dev.connection_type],
      dev.location || "",
      c.host ? `${c.host}:${c.port || 9100}` : "",
      c.windows_printer_name || "",
      c.device_path || "",
    ].filter(Boolean).join(" · ");
  };

  const grouped = (Object.keys(typeLabels) as DeviceType[])
    .map((typeKey) => ({ type: typeKey, items: devices.filter((d) => d.device_type === typeKey) }))
    .filter((g) => g.items.length > 0);

  const btn = "h-10 px-3 rounded-xl font-bold flex items-center gap-1.5 active:scale-95 disabled:opacity-50";
  const input = "w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none";
  const printerChoices = seen?.printers.filter((p) => p.kind !== "virtual") ?? [];
  const portChoices = seen?.ports ?? [];

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div role="alert" className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> <span data-testid="devices-error">{error}</span>
          <button aria-label={tr("ui.close")} type="button" onClick={() => setError(null)} className="ms-auto w-8 h-8 rounded-lg flex items-center justify-center hover:bg-red-100"><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div role="status" className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> <span data-testid="devices-success">{success}</span>
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <HardDrive className="w-5 h-5" /> {t("devices.title")}
          </h3>
          <p className="text-gray-500 mt-1">{t("devices.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <button aria-label={tr("ui.refresh")} type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
            <RefreshCw className="w-5 h-5" />
          </button>
          <button type="button" onClick={() => setDetectOpen(true)} className="h-12 px-5 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95">
            <Search className="w-5 h-5" /> {t("dvx.detect")}
          </button>
          <button type="button" onClick={() => newFrom()} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> {t("devices.btn_add")}
          </button>
        </div>
      </div>

      <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600 flex items-start gap-2">
        <Info className="w-5 h-5 shrink-0 mt-0.5 text-[#063D2E]" />
        <span>{desktop ? t("dvx.notice_desktop") : t("dvx.notice_browser")}</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("status.loading")}
        </div>
      ) : devices.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          {t("dvx.empty")}
        </div>
      ) : (
        grouped.map((g) => {
          const Icon = TYPE_ICON[g.type];
          return (
            <div key={g.type} className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-3 flex items-center gap-2">
                <Icon className="w-5 h-5" /> {typeLabels[g.type]} ({g.items.length})
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {g.items.map((dev) => {
                  const here = isPrinterType(dev.device_type) && desktop && isUsedOnThisPc(dev);
                  const working = busy === dev.id;
                  return (
                    <div key={dev.id} data-testid="device-card" data-device-name={dev.name} className="p-4 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-bold text-[#063D2E] flex flex-wrap items-center gap-2">
                            {dev.name}
                            {dev.is_default && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#7a5c16] bg-[#D4AF62]/20 px-1.5 py-0.5 rounded">
                                <Star className="w-3 h-3" /> {t("devices.badge_default")}
                              </span>
                            )}
                            {here && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-100 px-1.5 py-0.5 rounded">
                                <Laptop className="w-3 h-3" /> {t("dvx.badge_this_pc")}
                              </span>
                            )}
                          </div>
                          <div className="text-gray-500 text-[11px] break-all">{describe(dev)}</div>
                        </div>
                        <span data-testid="device-status" className={`px-2 py-1 rounded-lg text-xs font-bold whitespace-nowrap ${STATUS_STYLE[dev.status]}`}>
                          {statusLabels[dev.status]}
                        </span>
                      </div>

                      {dev.last_error && dev.status !== "ok" && (
                        <div className={`mt-2 text-[11px] break-words ${dev.status === "error" ? "text-red-600" : "text-gray-500"}`}>{dev.last_error}</div>
                      )}
                      {dev.last_test_at && (
                        <div className="mt-1 text-[11px] text-gray-400">{t("devices.last_test", { date: serverDate(dev.last_test_at).toLocaleString(localeFor()) })}</div>
                      )}

                      <div className="flex flex-wrap gap-1.5 mt-3">
                        <button type="button" disabled={busy !== null} onClick={() => runTest(dev)} className={`${btn} bg-[#063D2E] text-[#D4AF62]`}>
                          {dev.device_type === "cash_drawer" ? <DoorOpen className="w-4 h-4" /> : dev.device_type === "barcode_scanner" ? <ScanLine className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
                          {working ? t("dvx.testing") : dev.device_type === "cash_drawer" ? t("dvx.btn_open_drawer") : dev.device_type === "barcode_scanner" ? t("dvx.btn_scan_test") : t("dvx.btn_check")}
                        </button>
                        {isPrinterType(dev.device_type) && (
                          <button type="button" disabled={busy !== null} onClick={() => printTest(dev)} className={`${btn} bg-[#D4AF62] text-[#02291F]`}>
                            <Printer className="w-4 h-4" /> {t("devices.btn_test_print")}
                          </button>
                        )}
                        {isPrinterType(dev.device_type) && desktop && !here && (
                          <button type="button" disabled={busy !== null} onClick={() => makeThisPcPrinter(dev)} className={`${btn} border-2 border-emerald-300 text-emerald-800`}>
                            <Laptop className="w-4 h-4" /> {t("dvx.btn_use_here")}
                          </button>
                        )}
                        {!dev.is_default && (
                          <button type="button" disabled={busy !== null} onClick={() => setDefault(dev)} className={`${btn} border-2 border-gray-200`}>
                            <Star className="w-4 h-4" /> {t("devices.btn_set_default")}
                          </button>
                        )}
                        <button aria-label={`${t("misc.edit")} ${dev.name}`} type="button" onClick={() => editDevice(dev)} className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button aria-label={`${t("misc.delete")} ${dev.name}`} type="button" disabled={busy !== null} onClick={() => remove(dev)} className="h-10 w-10 rounded-xl border-2 border-red-200 flex items-center justify-center text-red-500 active:scale-95 disabled:opacity-50">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      {detectOpen && <DetectDevicesDialog devices={devices} onAdd={newFrom} onClose={() => setDetectOpen(false)} />}

      {scanFor && (
        <ScanTestDialog
          deviceName={scanFor.name}
          prefix={scanFor.config?.prefix}
          suffix={scanFor.config?.suffix}
          onDone={(r) => {
            if (r.ok) flash(t("dvx.scan_recorded", { name: scanFor.name, code: r.value || "" }));
            else fail(`${scanFor.name} : ${r.error}`);
            report(scanFor, r.ok, r.error);
          }}
          onClose={() => setScanFor(null)}
        />
      )}

      {/* FORM MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div role="dialog" aria-modal="true" aria-labelledby="device-form-title" className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 id="device-form-title" className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? t("devices.modal_new") : t("devices.modal_edit")}</h3>
              <button aria-label={tr("ui.close")} type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              {formError && <div role="alert" className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold">{formError}</div>}
              <Field label={t("devices.lbl_name")}>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={input} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label={t("devices.lbl_type")}>
                  <select
                    disabled={form.id !== null}
                    value={form.device_type}
                    onChange={(e) => {
                      const type = e.target.value as DeviceType;
                      const allowed = CONNECTIONS_FOR[type];
                      setForm({ ...form, device_type: type, connection_type: allowed.includes(form.connection_type) ? form.connection_type : allowed[0] });
                    }}
                    className={`${input} bg-white disabled:opacity-60`}
                  >
                    {(Object.keys(typeLabels) as DeviceType[]).map((tKey) => (
                      <option key={tKey} value={tKey}>{typeLabels[tKey]}</option>
                    ))}
                  </select>
                </Field>
                {form.device_type !== "cash_drawer" && (
                  <Field label={t("devices.lbl_connection")}>
                    <select
                      disabled={form.id !== null}
                      value={form.connection_type}
                      onChange={(e) => setForm({ ...form, connection_type: e.target.value as ConnectionType })}
                      className={`${input} bg-white disabled:opacity-60`}
                    >
                      {CONNECTIONS_FOR[form.device_type].map((c) => (
                        <option key={c} value={c}>{CONNECTION_LABEL[c]}</option>
                      ))}
                    </select>
                  </Field>
                )}
              </div>

              {form.connection_type === "network" && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <Field label={t("devices.lbl_host")}>
                      <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} className={`${input} font-mono`} placeholder="192.168.1.50" />
                    </Field>
                  </div>
                  <Field label={t("devices.lbl_port")}>
                    <input value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} className={`${input} font-mono`} placeholder="9100" />
                  </Field>
                </div>
              )}
              {(form.connection_type === "windows" || form.connection_type === "usb") && form.device_type !== "cash_drawer" && (
                <Field label={t("devices.lbl_windows_printer")}>
                  <input list="detected-printers" value={form.windows_printer_name} onChange={(e) => setForm({ ...form, windows_printer_name: e.target.value })} className={input} placeholder="POS-80" />
                  <datalist id="detected-printers">
                    {printerChoices.map((p) => <option key={p.system_name || p.name} value={p.name}>{`${t(`dvx.state_${p.state}`)} · ${p.port_name}`}</option>)}
                  </datalist>
                  {desktop && printerChoices.length > 0 && <span className="block text-[11px] text-gray-500 mt-1">{t("dvx.pick_detected", { n: printerChoices.length })}</span>}
                </Field>
              )}
              {(form.connection_type === "serial" || form.connection_type === "usb") && form.device_type !== "cash_drawer" && form.device_type !== "barcode_scanner" && (
                <Field label={form.connection_type === "usb" ? t("dvx.lbl_port_optional") : t("dvx.lbl_port_path")}>
                  <input list="detected-ports" value={form.device_path} onChange={(e) => setForm({ ...form, device_path: e.target.value })} className={`${input} font-mono`} placeholder={form.connection_type === "serial" ? "COM3" : "USB001, /dev/usb/lp0"} />
                  <datalist id="detected-ports">
                    {portChoices.map((p) => <option key={p.path} value={p.path}>{t(`dvx.port_${p.kind}`)}</option>)}
                  </datalist>
                </Field>
              )}
              {isPrinterType(form.device_type) && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t("devices.lbl_paper_width")}>
                    <select value={form.paper_width_mm} onChange={(e) => setForm({ ...form, paper_width_mm: e.target.value })} className={`${input} bg-white`}>
                      <option value="58">58 mm</option>
                      <option value="80">80 mm</option>
                    </select>
                  </Field>
                  {form.device_type === "label_printer" && (
                    <Field label={t("printer_settings.protocol")}>
                      <select value={form.label_format} onChange={(e) => setForm({ ...form, label_format: e.target.value })} className={`${input} bg-white`}>
                        <option value="zpl">{t("printer_settings.protocol_zpl")}</option>
                        <option value="escpos-text">{t("printer_settings.protocol_escpos")}</option>
                      </select>
                    </Field>
                  )}
                </div>
              )}
              {form.device_type === "cash_drawer" && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <Field label={t("dvx.lbl_drawer_printer")}>
                      <select value={form.printer_device_id} onChange={(e) => setForm({ ...form, printer_device_id: e.target.value })} className={`${input} bg-white`}>
                        <option value="">{t("dvx.opt_default_printer")}</option>
                        {receiptPrinters.map((p) => <option key={p.id} value={String(p.id)}>{p.name}</option>)}
                      </select>
                    </Field>
                  </div>
                  <Field label={t("printer_settings.drawer_pin")}>
                    <select value={form.drawer_pin} onChange={(e) => setForm({ ...form, drawer_pin: e.target.value })} className={`${input} bg-white`}>
                      <option value="2">2</option>
                      <option value="5">5</option>
                    </select>
                  </Field>
                </div>
              )}
              {form.device_type === "barcode_scanner" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t("devices.lbl_prefix")}><input value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value })} className={`${input} font-mono`} /></Field>
                  <Field label={t("devices.lbl_suffix")}><input value={form.suffix} onChange={(e) => setForm({ ...form, suffix: e.target.value })} className={`${input} font-mono`} placeholder="\\n" /></Field>
                </div>
              )}
              <Field label={t("devices.lbl_location")}>
                <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className={input} />
              </Field>

              <button type="button" disabled={busy !== null} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {form.id === null ? t("devices.btn_save_new") : t("devices.btn_save_update")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <label className="block">
    <span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase tracking-wide">{label}</span>
    {children}
  </label>
);
