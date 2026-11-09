# POS hardware bridge

The Mus Luxury Desktop CMS talks to physical shop-floor devices through
native Rust commands registered in `apps/desktop-cms/src-tauri/src/pos_hardware/`.
A plain web page cannot reliably reach a USB thermal printer, fire a cash
drawer's pulse, or read barcode scans without stealing text input — so these
live outside the WebView.

Four devices, two independent printer channels, three Rust commands + one
browser hook:

| Device                       | Where the work happens                                   |
| ---------------------------- | -------------------------------------------------------- |
| Thermal **receipt** printer  | `pos_print_receipt` (Rust, ESC/POS over system printer or raw device) |
| Cash drawer                  | `pos_open_cash_drawer` (Rust, ESC p pulse via the receipt printer's RJ11) |
| Thermal **label** printer    | `pos_print_labels` (Rust, ZPL by default, ESC/POS fallback) |
| USB-HID barcode scanner      | `useBarcodeScanner` React hook (frontend only — scanners emulate a keyboard) |

Receipts and labels use **separate printers** by design — a boutique typically
has one 58/80 mm receipt printer behind the till and one dedicated 50×30 mm
Zebra-style label printer for product tagging. Each is configured
independently in POS → **Matériel**.

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

## Label printer

The label printer is a separate device — typically a 50×30 mm Zebra or
compatible. Configure it in **Matériel → Étiqueteuse**:

- **Protocole**: ZPL (recommended — Zebra, GoDEX, SNBC, most OEM clones) or
  ESC/POS text (fallback for thermal label printers that only speak ESC/POS).
- **Résolution**: 203 dpi (standard — most 50×30 mm labels) or 300/600 dpi
  (fine printers like Zebra ZD621).
- **Largeur × Hauteur** in millimetres. The Rust side scales everything to
  the chosen DPI automatically.

### What gets printed

The label layout is fixed to keep things fast and scannable:

```
+----------------------------------+
|           Mus Luxury             |   ← boutique header
|   Chemise Lin - Beige M          |   ← product + variant
|   SKU CHE-LN-BM                  |
|           4 500 DA               |   ← price (double-height)
|                                  |
| |||||  |||  ||||  |||| |||  ||  |   ← CODE128 or EAN-13 barcode
|    CHE-LN-BM                     |   ← barcode interpretation line
+----------------------------------+
```

Long product names are clipped with "…" so they never overflow the label
width.

### Quantities

The label modal has a quantity selector (1–100). The `^PQ` ZPL command sends
the count once and the printer replicates the label itself — printing 50
labels of one product takes ~2 s on a 203 dpi Zebra. On ESC/POS fallback
each copy is sent as its own slip with a cut between copies.

### Where in the UI

- Products page → open a variant → **Code-barres & Étiquette**
- Set the barcode (generate internal or paste an EAN/UPC), then **Imprimer**
- When a label printer is configured in **Matériel**, the Imprimer button
  prints natively; otherwise it opens a browser print preview.

## Supported printer protocols

| Protocol         | Supported?       | How                                       |
| ---------------- | ---------------- | ----------------------------------------- |
| ESC/POS (Epson)  | Yes              | Native byte builder in `escpos.rs`        |
| Star Mode        | No               | Buy an ESC/POS-compatible printer         |
| CUPS (macOS/Linux) | Yes (as transport) | System printer name + ESC/POS bytes     |
| Windows Spooler  | Yes (as transport) | System printer name + ESC/POS bytes     |
| Raw serial       | Partial          | Pass `COM3:`, `/dev/ttyUSB0` as `device_path` |
| Network (LAN)    | Via OS printer   | Install the printer at the OS level first |

### Label-printer-specific cheatsheet

| Printer                                   | Protocol  | Settings                       |
| ----------------------------------------- | --------- | ------------------------------ |
| Zebra ZD230 / ZD421 / GK420 / GX420       | ZPL       | 203 dpi, 50 × 30 mm            |
| Zebra ZD621                               | ZPL       | 300 dpi, 50 × 30 mm            |
| GoDEX RT230i / G500 / EZ-2250i            | ZPL       | 203 dpi                         |
| SNBC BTP-L580 / BTP-L540                  | ZPL       | 203 dpi                         |
| Xprinter XP-470B / XP-365B                | ESC/POS   | fallback — select "ESC/POS texte" |
| Thermal receipt printer re-purposed as label | ESC/POS   | fallback — select "ESC/POS texte" |

## Universal "system printer" path (any Windows printer)

Not every boutique buys a thermal receipt printer or a Zebra label printer.
Every modal that offers "Imprimer" also offers **Aperçu système (toute imprimante)**:
it opens an isolated print preview sized to the current paper setting
(58/80 mm for receipts, configured W×H mm for labels) and invokes
`window.print()`. The Tauri WebView's standard PDF preview appears — the
operator picks ANY installed Windows printer (laser, inkjet, A4-sheet-of-
labels, Microsoft Print to PDF), can zoom, change paper size, or **Save as
PDF**.

- The system-printer path is always available; the thermal/ZPL path is only
  there when one of the printers is configured in **Matériel**.
- When nothing is configured, "Imprimer" goes straight to the system path
  (no error, no "configure first" roadblock).
- Receipt content and boutique header come from fiscal settings, so a shop
  with no NIF/NIS/RC yet still prints a clean slip.

## POS search-as-you-type (luxury items without barcodes)

Mus Luxury sells high-end bags and pieces that rarely carry a barcode from
the supplier. The POS lookup box supports both modes at the same time:

- **Scan** — a USB-HID scanner's fast keystroke burst is detected by
  `useBarcodeScanner`, routed to `/pos/lookup`, and auto-added to the cart
  on exact match.
- **Live search** — human typing (debounced ~250 ms, minimum 2 chars) fires
  the same `/pos/lookup`; results grow in the grid below as you type. No
  Enter needed.
- **Enter / Chercher** — the explicit submit still works and clears the box
  on an exact match.

Every row in the results grid has a small **tag** icon → opens the
Barcode & Label modal for that variant: generate / scan / paste a barcode,
then print N sticky labels on the label printer. This closes the "add
stock → assign barcode later → print later" loop in one place.

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

# All ZPL label-builder commands produce the expected bytes.
rustc --test --edition 2021 \
  apps/desktop-cms/src-tauri/src/pos_hardware/zpl.rs \
  -o /tmp/zpl_test && /tmp/zpl_test
```

(Once a Tauri Linux dev stack is installed, `cargo test` inside
`apps/desktop-cms/src-tauri` runs the module tests under `pos_hardware::`
and the escpos / zpl sub-modules as well.)
