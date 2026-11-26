// The shop's device list (Devices page, kept on the server) and the printers
// THIS PC prints on (till settings, kept on the PC). A device of the list can
// be "used on this PC", and a PC with nothing set up takes the shop's default
// receipt / label printer, so a printer added once on the Devices page is the
// one the till really uses.
import { DesktopCmsApi } from "../api/adminClient";
import {
  isHardwareConfigured,
  isLabelPrinterConfigured,
  loadHardwareSettings,
  loadLabelPrinterSettings,
  saveHardwareSettings,
  saveLabelPrinterSettings,
  type LabelPrinterTarget,
  type PrinterTarget,
} from "./posHardware";

export type DeviceType = "receipt_printer" | "label_printer" | "barcode_scanner" | "cash_drawer" | "customer_display" | "other";
export type ConnectionType = "usb" | "network" | "windows" | "serial" | "hid_keyboard" | "browser";

export interface ShopDevice {
  id: number;
  name: string;
  device_type: DeviceType;
  connection_type: ConnectionType;
  config: Record<string, any>;
  capabilities: string[];
  location?: string | null;
  is_default: boolean;
  status: "unknown" | "ok" | "error" | "offline";
  last_error?: string | null;
  last_test_at?: string | null;
}

const text = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : null);

/** Characters per line for a paper width: 58 mm → 32, 80 mm → 42 (unless set). */
export function lineWidthFor(cfg: Record<string, any>): number {
  const n = Number(cfg?.line_width);
  if (n === 32 || n === 42 || n === 48) return n;
  return Number(cfg?.paper_width_mm) === 58 ? 32 : 42;
}

/** Where a receipt printer (or the printer a cash drawer is plugged into) is reached. */
export function targetFromDevice(dev: Pick<ShopDevice, "connection_type" | "config">): PrinterTarget {
  const cfg = dev.config || {};
  const network = dev.connection_type === "network";
  return {
    printer_name: network ? null : text(cfg.windows_printer_name),
    device_path: network ? null : text(cfg.device_path),
    host: network ? text(cfg.host) : null,
    port: network ? Number(cfg.port) || 9100 : null,
    line_width: lineWidthFor(cfg),
    drawer_pin: Number(cfg.drawer_pin) === 5 ? 5 : 2,
  };
}

export function labelTargetFromDevice(dev: Pick<ShopDevice, "connection_type" | "config">): LabelPrinterTarget {
  const base = targetFromDevice(dev);
  const cfg = dev.config || {};
  const dpi = Number(cfg.dpi);
  return {
    printer_name: base.printer_name,
    device_path: base.device_path,
    host: base.host,
    port: base.port,
    format: cfg.label_format === "escpos-text" ? "escpos-text" : "zpl",
    width_mm: Number(cfg.label_width_mm) || 50,
    height_mm: Number(cfg.label_height_mm) || 30,
    dpi: dpi === 300 || dpi === 600 ? dpi : 203,
  };
}

/** A cash drawer opens through the receipt printer it is plugged into: the one
 *  chosen in its settings, else the shop's default receipt printer, else this
 *  PC's receipt printer. */
export function drawerTarget(drawer: ShopDevice, all: ShopDevice[]): PrinterTarget | null {
  const printers = all.filter((d) => d.device_type === "receipt_printer");
  const linked = printers.find((d) => d.id === Number(drawer.config?.printer_device_id))
    || printers.find((d) => d.is_default);
  const pin = Number(drawer.config?.drawer_pin) === 5 ? 5 : 2;
  if (linked) return { ...targetFromDevice(linked), drawer_pin: pin };
  const local = loadHardwareSettings();
  return isHardwareConfigured(local) ? { ...local, drawer_pin: pin } : null;
}

const same = (a: unknown, b: unknown) => String(a ?? "").trim().toLowerCase() === String(b ?? "").trim().toLowerCase();

/** Is this device the receipt / label printer of this PC? */
export function isUsedOnThisPc(dev: ShopDevice): boolean {
  const local = dev.device_type === "label_printer" ? loadLabelPrinterSettings() : loadHardwareSettings();
  const t = targetFromDevice(dev);
  if (t.host) return same(local.host, t.host) && Number(local.port || 9100) === Number(t.port || 9100);
  if (t.device_path) return same(local.device_path, t.device_path);
  if (t.printer_name) return same(local.printer_name, t.printer_name) && !local.host && !local.device_path;
  return false;
}

/** Make this device the receipt (or label) printer of this PC. */
export function setAsThisPcPrinter(dev: ShopDevice): void {
  if (dev.device_type === "label_printer") {
    saveLabelPrinterSettings(labelTargetFromDevice(dev));
  } else if (dev.device_type === "receipt_printer") {
    const keepPin = loadHardwareSettings().drawer_pin;
    saveHardwareSettings({ ...targetFromDevice(dev), drawer_pin: keepPin ?? 2 });
  }
}

/** A PC with no receipt / label printer set up takes the shop's defaults.
 *  Returns what was taken (for a notice), never throws. */
export async function adoptShopDefaults(): Promise<{ receipt?: string; label?: string }> {
  const taken: { receipt?: string; label?: string } = {};
  const needReceipt = !isHardwareConfigured();
  const needLabel = !isLabelPrinterConfigured();
  if (!needReceipt && !needLabel) return taken;
  try {
    const items: ShopDevice[] = (await DesktopCmsApi.listDevices())?.items || [];
    const pick = (type: DeviceType) => items.find((d) => d.device_type === type && d.is_default) || (items.filter((d) => d.device_type === type).length === 1 ? items.find((d) => d.device_type === type) : undefined);
    const receipt = needReceipt ? pick("receipt_printer") : undefined;
    if (receipt) {
      const drawer = pick("cash_drawer");
      saveHardwareSettings({ ...targetFromDevice(receipt), drawer_pin: Number(drawer?.config?.drawer_pin) === 5 ? 5 : 2 });
      taken.receipt = receipt.name;
    }
    const label = needLabel ? pick("label_printer") : undefined;
    if (label) {
      saveLabelPrinterSettings(labelTargetFromDevice(label));
      taken.label = label.name;
    }
  } catch {
    /* no access to the device list (cashier without the right) or offline: keep as is */
  }
  return taken;
}
