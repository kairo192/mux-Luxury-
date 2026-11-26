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

## First-time setup (Devices page)

1. Plug the thermal printer into the till PC and install its driver (or Windows'
   **Generic / Text Only** driver) so Windows lists it. A network printer only
   needs to be on the shop's network (its self-test page shows its IP address).
2. Plug the cash drawer's RJ11 cable into the back of the receipt printer
   (the drawer opens through the printer, never through a USB port).
3. Plug the barcode scanner (USB keyboard mode; suffix "Enter" if its
   quick-start sheet offers it).
4. In the desktop app: **Administration → Devices → Detect**. The dialog lists
   - the printers installed on this PC (state ready / offline / paused, port such as
     `USB001`, kind guessed from name + driver: receipts, labels, office, virtual PDF);
   - **Search the network**: every address of the PC's local /24 network that answers
     on the raw printing port 9100 (a connection is opened and closed, nothing is sent;
     only private networks are searched);
   - the COM / USB ports (Windows registry `SERIALCOMM`; `/dev/usb/lp*`, `/dev/ttyUSB*`… elsewhere).
   **Add** fills in the form; the form also offers the detected printers / ports.
5. On each device:
   - **Check** — no paper: a network printer accepts a connection, a port opens, a
     Windows printer exists, is not offline / paused and has nothing stuck in its queue.
   - **Test Print** — a real slip (CMS language; French when the CMS is in Arabic,
     thermal printers have no Arabic letters) or label, then the person answers
     "did it come out?". Only that answer marks the device OK.
   - **Open drawer** (cash drawer) — sends the pulse through its receipt printer
     (the one chosen in its settings, else the default one), then asks "did it open?".
   - **Test a scan** (scanner) — scan any code within 30 s; a code typed by hand
     (more than 60 ms between keys) is refused.
   - **Use on this PC** — makes the printer this PC's till / label printer. A till PC
     with nothing set up takes the shop's default receipt and label printers by itself.
   Every result is recorded on the server (status, last error, date) for everyone.

POS → **Matériel** still holds this PC's own settings (system printer, network IP,
port, paper width, drawer pin, label format) with **Check / Test print / Open drawer**.
They are kept per PC (`luxe_pos_hardware_settings`, `luxe_pos_label_printer_settings`).

### Honest results

- Windows accepts a job even when the printer is off, unplugged or out of paper: the
  job just waits. After sending, the app watches the job for 8 s; still waiting →
  "Nothing came out: the job is waiting in the print queue…" (not "printed").
- An offline or paused printer is refused before anything is sent.
- Errors come from the desktop app as `ERR:<code>:<detail>` and are shown in the
  CMS language (`hw.err_<code>`): printer_not_found, printer_offline, printer_paused,
  job_stuck, job_paused, job_cancelled, jobs_waiting, print_failed, path_not_found,
  path_open_failed, path_write_failed, net_resolve_failed, net_unreachable,
  net_send_failed, no_printer, no_labels, system_print_unavailable.
- On Linux / macOS (CUPS) the bytes are sent raw (`raw=true`), never through a text filter.

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

## Local catalog mirror (offline POS)

The Desktop CMS keeps a local SQLite copy of the catalog in the user's
app-data directory (`<AppData>/Mus Luxury CMS/pos_mirror.sqlite3`) so the
POS can look up and sell products with zero connectivity. Backend feeds it
through two endpoints:

```
GET /api/v1/admin/pos/catalog/snapshot
    Full dump of every active product + variant. Used on first launch.

GET /api/v1/admin/pos/catalog/deltas?since=<cursor>
    Everything created or updated since `since`. Called every time the POS
    opens and after each reconnect.
```

### Freshness

- Automatic sync on POS page mount and on every "offline → online" flip.
- Manual re-sync and full re-seed from **Matériel → Catalogue**.
- The cursor is stamped as `now + 1 s` so a snapshot cleanly hands off to
  the next delta at the exact second boundary (no duplicates, no misses).

### Lookup policy

Every lookup goes through `posLookupResolver`:

1. **Try the mirror first.** Barcode or SKU hit → return the variant
   immediately.
2. **Mirror miss + online → ask the API.** The mirror may be a few
   seconds stale on a brand-new product.
3. **Mirror miss + offline → return the mirror's best fallback** (empty
   or fuzzy name match). The cashier sees a "hors ligne" chip on the
   toolbar.

### Capacity

Each variant is ~150 bytes in the mirror. A 5 000-variant catalog is
under 1 MB on disk. Indexes on `barcode` and `sku` give O(log n) lookups;
a name search strips accents and uses `LIKE` on a normalized column.

### Trigger-backed change capture

`product_variants.updated_at` is stamped by two triggers added in
migration `003_product_variants_updated_at` (SQLite + Postgres):

- `AFTER UPDATE OF ...` for stock, price, title, barcode, SKU, active
  flag, image, cost, low-stock threshold.
- `AFTER INSERT` (SQLite) / `BEFORE INSERT` (Postgres) stamps new rows
  so a brand-new variant never has a NULL cursor value.

### Troubleshooting

| Symptom                                      | Fix                                                          |
| -------------------------------------------- | ------------------------------------------------------------ |
| Chip shows 0 variants after first launch     | Click **Recharger complet** in Matériel → Catalogue.         |
| Stock in the POS doesn't match the dashboard | Click **Synchroniser** in the chip or in Matériel.           |
| Mirror looks corrupted                       | **Effacer le cache local** in Matériel; next sync re-seeds.  |

## Known gaps / roadmap

- **Arabic text** does not print on most thermal printers — ESC/POS only
  covers single-byte code pages, and Mus Luxury runs CP437 by default. To
  print Arabic we would need to render the Arabic string to a monochrome
  bitmap client-side (HTML5 canvas) and send it as a raster image (`GS v 0`).
  Receipts currently fall back to the French / Latin content; the Arabic
  version is skipped. Planned for a follow-up release.
- **Scale integration**, **card payment terminal integration**
  are not in scope here. They would be separate native modules.
- **Paper sensor of a raw port / network printer** — a printer reached by IP or COM
  port has no print queue to watch: the bytes were delivered, but "out of paper" is
  only known from the person's answer to the print test. Epson's real-time status
  (`DLE EOT 4`) could be read back on those links later.

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

```bash
cd apps/desktop-cms/src-tauri && cargo test           # ESC/POS, ZPL, detection, network printer,
                                                      # device ports, queue follow-up (no hardware)
bash infrastructure/scripts/test-print-queue.sh       # one real print through a CUPS raw queue to a
                                                      # fake network printer: exact bytes, printer off
                                                      # -> "job_stuck", paused queue refused
```

Both run in CI (`desktop-rust-tests`). The Devices page itself is covered by
`e2e/tests/09-devices.spec.ts` (desktop bridge simulated with the same answers and
error codes as the Rust commands; plus a real TCP "printer" checked by the server).
Windows-only code is checked with `cargo check --target x86_64-pc-windows-gnu`.

On the shop PC, with the real printers, the checklist is: Detect → Add → Check →
Test Print (answer honestly) → Use on this PC → a real sale prints and the drawer opens.
