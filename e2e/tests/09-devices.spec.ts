import { test, expect, type Page } from "@playwright/test";
import * as net from "node:net";
import { api, watch, cmsLogin, cmsOpen } from "../support/helpers";

// Devices page: detection, checks without printing, real print tests with a
// human answer, cash drawer, scanner, and "use on this PC".
//
// The desktop app's printer commands (Rust, `src-tauri/src/pos_hardware`) are
// tested against real printers / print queues by `cargo test` and
// `infrastructure/scripts/test-print-queue.sh`. Here the CMS runs in a browser,
// so the desktop bridge is simulated: it answers like the Rust commands do
// (same shapes, same "ERR:<code>:<detail>" errors) and records every call.

const BRIDGE = () => {
  const printers = [
    { name: "POS-80", system_name: "POS-80", is_default: true, state: "ready", kind: "receipt", port_name: "USB001", driver_name: "POS-80" },
    { name: "ZDesigner GK420t", system_name: "ZDesigner GK420t", is_default: false, state: "offline", kind: "label", port_name: "USB002", driver_name: "ZDesigner GK420t" },
    { name: "Microsoft Print to PDF", system_name: "Microsoft Print to PDF", is_default: false, state: "ready", kind: "virtual", port_name: "PORTPROMPT:", driver_name: "Microsoft Print To PDF" },
  ];
  const calls: any[] = [];
  (window as any).__hwCalls = calls;
  (window as any).__TAURI_INTERNALS__ = {
    transformCallback: () => 0,
    invoke: async (cmd: string, args: any = {}) => {
      calls.push({ cmd, args: JSON.parse(JSON.stringify(args)) });
      const o = args.opts || {};
      switch (cmd) {
        case "pos_list_printers": return printers.map(({ name, system_name, is_default, state }) => ({ name, system_name, is_default, state }));
        case "pos_detect_devices":
          return { printers, ports: [{ path: "COM3", kind: "serial" }], subnet: "192.168.1.0/24", network_scanned: !!args.scanNetwork,
            network: args.scanNetwork ? [{ host: "192.168.1.50", port: 9100 }] : [] };
        case "pos_check_printer":
          if (o.printer_name === "ZDesigner GK420t") throw "ERR:printer_offline:ZDesigner GK420t";
          return o.host ? "reachable" : "ready";
        case "pos_test_print": return null;
        case "pos_test_print_label": throw `ERR:job_stuck:${o.printer_name}`;
        case "pos_open_cash_drawer": return null;
        case "keychain_status": return { os_keychain: false };
        default: return null;
      }
    },
  };
};

const calls = (page: Page, cmd: string) => page.evaluate((c) => (window as any).__hwCalls.filter((x: any) => x.cmd === c), cmd);
const card = (page: Page, name: string) => page.locator(`[data-testid="device-card"][data-device-name="${name}"]`);
const answer = async (page: Page, label: RegExp) => {
  const d = page.locator('[aria-labelledby="active-confirm-title"]');
  await expect(d).toBeVisible();
  await d.getByRole("button", { name: label }).click();
};

test.beforeAll(async () => {
  const { items } = await api<{ items: Array<{ id: number }> }>("/admin/devices");
  for (const d of items) await api(`/admin/devices/${d.id}`, { method: "DELETE" });
});

test("desktop app: detect, add, check, print test, use on this PC, drawer, scanner", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(BRIDGE);
  const w = watch(page);
  await cmsLogin(page, undefined, "en");
  await page.evaluate(() => { localStorage.removeItem("luxe_pos_hardware_settings"); localStorage.removeItem("luxe_pos_label_printer_settings"); });
  await cmsOpen(page, "Devices");
  const main = page.locator("main");

  // ---- detection: printers of this PC, then the local network
  await main.getByRole("button", { name: "Detect" }).click();
  const dlg = page.getByRole("dialog", { name: "Devices this PC can see" });
  await expect(dlg.getByTestId("detected-printer")).toHaveCount(3);
  await expect(dlg.getByTestId("detected-printer").filter({ hasText: "ZDesigner GK420t" })).toContainText("Offline");
  await expect(dlg.getByTestId("detected-printer").filter({ hasText: "Microsoft Print to PDF" })).toContainText("Virtual");
  await expect(dlg.getByTestId("detected-port")).toContainText("COM3");
  await dlg.getByRole("button", { name: "Search the network" }).click();
  await expect(dlg.getByTestId("detected-network")).toContainText("192.168.1.50:9100");
  expect((await calls(page, "pos_detect_devices")).at(-1).args).toEqual({ scanNetwork: true });

  // ---- add the USB receipt printer found: the form comes filled in
  await dlg.getByRole("button", { name: "Add POS-80" }).click();
  const form = page.getByRole("dialog", { name: "New Device" });
  await expect(form.locator("input").first()).toHaveValue("POS-80");
  await expect(form.locator('input[list="detected-printers"]')).toHaveValue("POS-80");
  await form.getByRole("button", { name: "Save Device" }).click();
  await expect(card(page, "POS-80")).toBeVisible();

  // ---- and the label printer
  await main.getByRole("button", { name: "Detect" }).click();
  await expect(dlg.getByTestId("detected-printer").filter({ hasText: "POS-80" })).toContainText("Already in the list");
  await dlg.getByRole("button", { name: "Add ZDesigner GK420t" }).click();
  await expect(form.locator("select").first()).toHaveValue("label_printer");
  await form.getByRole("button", { name: "Save Device" }).click();
  await expect(card(page, "ZDesigner GK420t")).toBeVisible();

  // ---- Check: no paper, status recorded
  await card(page, "POS-80").getByRole("button", { name: "Check" }).click();
  await expect(page.getByTestId("devices-success")).toContainText("POS-80: OK (Ready), nothing was printed.");
  await expect(card(page, "POS-80").getByTestId("device-status")).toHaveText("OK");
  expect((await calls(page, "pos_check_printer")).at(-1).args.opts.printer_name).toBe("POS-80");

  await card(page, "ZDesigner GK420t").getByRole("button", { name: "Check" }).click();
  await expect(page.getByTestId("devices-error")).toContainText("is offline: check it is switched on and plugged in");
  await expect(card(page, "ZDesigner GK420t").getByTestId("device-status")).toHaveText("Error");

  // ---- Print test: real slip in the CMS language, then the person answers
  await card(page, "POS-80").getByRole("button", { name: "Test Print" }).click();
  await answer(page, /Yes, printed/);
  await expect(page.getByTestId("devices-success")).toContainText("POS-80: printing checked.");
  const slip = (await calls(page, "pos_test_print")).at(-1).args;
  expect(slip.opts.printer_name).toBe("POS-80");
  expect(JSON.stringify(slip.lines)).toContain("Printer test");

  await card(page, "POS-80").getByRole("button", { name: "Test Print" }).click();
  await answer(page, /^No$/);
  await expect(card(page, "POS-80").getByTestId("device-status")).toHaveText("Error");
  await expect(card(page, "POS-80")).toContainText("did not come out");

  // A label job left in the queue is NOT reported as printed (no question asked).
  await card(page, "ZDesigner GK420t").getByRole("button", { name: "Test Print" }).click();
  await expect(page.getByTestId("devices-error")).toContainText("Nothing came out");
  await expect(page.locator('[aria-labelledby="active-confirm-title"]')).toHaveCount(0);

  // ---- Use on this PC: the till prints on it
  await card(page, "POS-80").getByRole("button", { name: "Use on this PC" }).click();
  await expect(card(page, "POS-80")).toContainText("this PC");
  const local = await page.evaluate(() => JSON.parse(localStorage.getItem("luxe_pos_hardware_settings") || "{}"));
  expect(local.printer_name).toBe("POS-80");

  // ---- cash drawer plugged into POS-80 (pin 5)
  await main.getByRole("button", { name: "Add", exact: true }).click();
  await form.locator("input").first().fill("Drawer");
  await form.locator("select").first().selectOption("cash_drawer");
  await form.locator("select").nth(1).selectOption({ label: "POS-80" });
  await form.locator("select").nth(2).selectOption("5");
  await form.getByRole("button", { name: "Save Device" }).click();
  await card(page, "Drawer").getByRole("button", { name: "Open drawer" }).click();
  await answer(page, /Yes, it opened/);
  await expect(card(page, "Drawer").getByTestId("device-status")).toHaveText("OK");
  const kick = (await calls(page, "pos_open_cash_drawer")).at(-1).args.opts;
  expect([kick.printer_name, kick.drawer_pin]).toEqual(["POS-80", 5]);

  // ---- scanner: a code typed by hand is refused, a fast scan is recorded
  await main.getByRole("button", { name: "Add", exact: true }).click();
  await form.locator("input").first().fill("Scanner");
  await form.locator("select").first().selectOption("barcode_scanner");
  await form.getByRole("button", { name: "Save Device" }).click();
  await card(page, "Scanner").getByRole("button", { name: "Test a scan" }).click();
  const scan = page.getByRole("dialog", { name: /Testing scanner/ });
  const field = scan.getByRole("textbox", { name: "Scanned code" });
  await field.pressSequentially("ABC123", { delay: 150 });
  await field.press("Enter");
  await expect(scan).toContainText("typed by hand");
  await field.pressSequentially("MUS-2026-0042", { delay: 5 });
  await field.press("Enter");
  await expect(scan.getByTestId("scanned-value")).toHaveText("MUS-2026-0042");
  await scan.getByRole("button", { name: "Close" }).last().click();
  await expect(card(page, "Scanner").getByTestId("device-status")).toHaveText("OK");

  w.expectClean();
});

test("browser: network printer checked by the server, print test through the system dialog", async ({ page }) => {
  // A real "printer" on this machine (raw printing port), then switched off.
  const server = net.createServer((s) => s.end());
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", () => r()));
  const port = (server.address() as net.AddressInfo).port;

  const w = watch(page);
  await cmsLogin(page, undefined, "en");
  await cmsOpen(page, "Devices");
  const main = page.locator("main");
  await expect(main).toContainText("You are in a browser");

  await main.getByRole("button", { name: "Detect" }).click();
  await expect(page.getByRole("dialog", { name: "Devices this PC can see" })).toContainText("Detection works in the desktop app");
  await page.keyboard.press("Escape");

  await main.getByRole("button", { name: "Add", exact: true }).click();
  const form = page.getByRole("dialog", { name: "New Device" });
  await form.locator("input").first().fill("Network POS");
  await form.locator("select").nth(1).selectOption("network");
  await form.getByRole("button", { name: "Save Device" }).click();
  await expect(form.getByRole("alert")).toHaveText("Enter the device's IP address.");
  await form.getByPlaceholder("192.168.1.50").fill("127.0.0.1");
  await form.getByPlaceholder("9100").fill(String(port));
  await form.getByRole("button", { name: "Save Device" }).click();

  await card(page, "Network POS").getByRole("button", { name: "Check" }).click();
  await expect(card(page, "Network POS").getByTestId("device-status")).toHaveText("OK");
  await new Promise<void>((r) => server.close(() => r()));
  await card(page, "Network POS").getByRole("button", { name: "Check" }).click();
  await expect(card(page, "Network POS").getByTestId("device-status")).toHaveText("Error");

  // Print test: the page goes into a hidden frame and the system print dialog opens.
  await card(page, "Network POS").getByRole("button", { name: "Test Print" }).click();
  await expect(page.locator("iframe[data-luxe-print]")).toHaveCount(1);
  expect(await page.frameLocator("iframe[data-luxe-print]").locator("body").innerText()).toContain("Network POS");
  await answer(page, /Yes, printed/);
  await expect(card(page, "Network POS").getByTestId("device-status")).toHaveText("OK");
  w.expectClean();
});
