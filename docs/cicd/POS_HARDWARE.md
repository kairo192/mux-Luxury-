# POS hardware bridge

The Mus Luxury Desktop CMS talks to physical shop-floor devices through
native Rust commands registered in `apps/desktop-cms/src-tauri/src/pos_hardware/`.
A plain web page cannot reliably reach a USB thermal printer, fire a cash
drawer's pulse, or read barcode scans without stealing text input — so these
live outside the WebView.

Three pieces of hardware, two commands + one browser hook:

| Device                       | Where the work happens                                   |
| ---------------------------- | -------------------------------------------------------- |
| Thermal receipt printer      | `pos_print_receipt` (Rust, ESC/POS over system printer or raw device) |
| Cash drawer                  | `pos_open_cash_drawer` (Rust, ESC p pulse via the printer's RJ11) |
| USB-HID barcode scanner      | `useBarcodeScanner` React hook (frontend only — scanners emulate a keyboard) |

## First-time setup

1. Plug the thermal printer into the POS computer. Install the manufacturer
   driver so Windows / macOS / Linux lists it as an available printer.
2. Plug the cash drawer's RJ11 cable into the back of the printer (NOT into
   a USB port — the drawer kicks off the printer's pass-through pulse).
3. Plug the barcode scanner. No driver is needed: it registers as a HID
   keyboard. If it's new, print its "set suffix to CR" code once (in the
   scanner's quick-start sheet) so each scan ends with Enter.
4. Open the Desktop CMS → POS → **Matériel** (top toolbar).
5. Pick the printer from the list, choose paper width (32 chars for 58 mm,
   42–48 chars for 80 mm), pick drawer pin 2 (Epson/Star) or 5 (Citizen).
6. Click **Imprimer un test** — a short diagnostic slip should come out.
7. Click **Ouvrir le tiroir** — the drawer should pop.

Settings are persisted in the Tauri store as `luxe_pos_hardware_settings`.
They stay per-install, so each boutique PC is configured once.

## What happens during a sale

```
cashier presses Encaisser
    │
    ▼
POST /api/v1/admin/pos/sales   ◀── backend records the sale, decrements stock
    │  (success)
    ▼
printSaleReceipt(sale)         ◀── pos_hardware.ts formats ESC/POS from the sale JSON
    │
    ▼
pos_print_receipt              ◀── Rust renders bytes, sends to printer
    │
    ▼
payment method === cash  ──────▶  drawer kick pulse (ESC p) appended
```

If the sale used a non-cash payment method, the drawer is NOT kicked.
If the printer errors, the POS still records the sale — a toast tells the
cashier what went wrong, and the browser fallback print dialog opens.

## Scanner

`useBarcodeScanner(onScan)` listens for keystroke bursts anywhere on the POS
page (any fast burst terminated by Enter or Tab). Humans typing into form
fields are not affected: the hook ignores keys with inter-keystroke gaps >
50 ms, and ignores all input inside `<input>` / `<textarea>` unless the
field opts in with `data-barcode-target="true"`. The POS lookup box opts in
so a scan both fills the box and triggers the lookup; every other text
field is untouched.

## Supported printer protocols

| Protocol         | Supported?       | How                                       |
| ---------------- | ---------------- | ----------------------------------------- |
| ESC/POS (Epson)  | Yes              | Native byte builder in `escpos.rs`        |
| Star Mode        | No               | Buy an ESC/POS-compatible printer         |
| CUPS (macOS/Linux) | Yes (as transport) | System printer name + ESC/POS bytes     |
| Windows Spooler  | Yes (as transport) | System printer name + ESC/POS bytes     |
| Raw serial       | Partial          | Pass `COM3:`, `/dev/ttyUSB0` as `device_path` |
| Network (LAN)    | Via OS printer   | Install the printer at the OS level first |

## Known gaps / roadmap

- **Arabic text** does not print on most thermal printers — ESC/POS only
  covers single-byte code pages, and Mus Luxury runs CP437 by default. To
  print Arabic we would need to render the Arabic string to a monochrome
  bitmap client-side (HTML5 canvas) and send it as a raster image (`GS v 0`).
  Receipts currently fall back to the French / Latin content; the Arabic
  version is skipped. Planned for a follow-up release.
- **Scale integration**, **payment terminal integration** (SATIM / Chargily)
  are not in scope here. They would be separate native modules.
- **Printer status monitoring** — the current API is fire-and-forget. An
  "out of paper" slip never reports back. Epson's real-time status
  protocol (`DLE EOT 1`) can be added later with a synchronous USB IOCTL;
  the browser-print fallback would then kick in automatically.

## Troubleshooting

| Symptom                                           | Likely cause / fix                                                  |
| ------------------------------------------------- | ------------------------------------------------------------------- |
| "Aucune imprimante configurée"                    | Open **Matériel** and select a printer or fill in a device path.    |
| Test print produces nothing                       | Wrong printer selected; OS driver not installed; try a different USB port. |
| Receipts look like random characters              | Driver is interpreting ESC/POS as plain text. Use the printer's **Generic / Text Only** driver (Windows) or print directly to the device path. |
| French accents print as `?`                       | Your printer uses WPC1252, not CP437. Switch the printer's DIP code page to CP437 (printer manual), or send us a driver override. |
| Drawer doesn't open                               | Try pin 5 instead of 2; verify the RJ11 is in the DRAWER jack, not NETWORK; check the drawer's own cable. |
| Scanner types into product fields instead of scanning | The field has `data-barcode-target="true"` by mistake, or the scanner isn't ending with Enter. Check the scanner's suffix configuration. |
| Scanner is never detected                         | The scanner isn't in HID keyboard mode — some default to serial. Follow the quick-start to enable HID keyboard emulation. |

## Testing

The Rust byte builder has unit tests you can run without connected hardware:

```bash
# All ESC/POS commands produce the expected bytes.
rustc --test --edition 2021 \
  apps/desktop-cms/src-tauri/src/pos_hardware/escpos.rs \
  -o /tmp/escpos_test && /tmp/escpos_test
```

(Once a Tauri Linux dev stack is installed, `cargo test` inside
`apps/desktop-cms/src-tauri` runs the module tests under `pos_hardware::`
and the escpos sub-module as well.)
