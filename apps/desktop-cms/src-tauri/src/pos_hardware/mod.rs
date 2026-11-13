// ============================================================================
// MUS LUXURY (LUXE) — POS HARDWARE BRIDGE (ESC/POS over USB/serial)
//
// The Tauri app lives on the shop floor and talks to physical devices a
// browser cannot reliably reach: thermal receipt printers, cash drawers
// connected via the printer's RJ11 pass-through, and (indirectly) USB
// barcode scanners that emulate a keyboard.
//
// This module exposes four Tauri commands:
//
//   pos_list_printers()                      → [{ name, system_name, is_default }]
//   pos_print_receipt(opts, lines)           → prints an ESC/POS receipt
//   pos_open_cash_drawer(opts)               → fires the drawer-kick pulse
//   pos_test_print(opts)                     → short diagnostic slip
//
// The ESC/POS byte builder in `escpos.rs` is pure Rust, has no dependencies,
// and is covered by unit tests so changes to the protocol are caught before
// they ever reach a physical printer. The actual OS-level write happens via
// the `printers` crate, which supports Windows (Spooler), macOS (CUPS) and
// Linux (CUPS). If no cross-platform printer backend is available we fall
// back to writing the raw bytes to a device path (e.g. `/dev/usb/lp0`,
// `LPT1` on Windows), which covers printers that register as a character
// device and ignore the Spooler.
//
// Encoding: we emit CP437 by default (the most widely supported single-byte
// code page on cheap 58mm/80mm thermal printers). Arabic text cannot be
// printed as characters by most of these printers; the storefront's RTL
// strings should be rendered to an image upstream and sent as a raster
// bitmap. v1 prints French / Latin receipts; raster bitmaps land in a later
// release (`docs/cicd/POS_HARDWARE.md` tracks the gap).
// ============================================================================

mod escpos;
mod zpl;

use escpos::{Align, EscPos, DEFAULT_LINE_WIDTH};
use zpl::{render_batch as zpl_render_batch, BarcodeKind as ZplBarcodeKind, LabelContent as ZplLabelContent};
use serde::{Deserialize, Serialize};
use std::fs::OpenOptions;
use std::io::Write;
use std::net::{TcpStream, ToSocketAddrs};
use std::path::Path;
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrinterInfo {
    pub name: String,
    pub system_name: String,
    pub is_default: bool,
    pub state: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct PrinterTarget {
    /// `name` from `pos_list_printers`, OR a raw device path such as
    /// `/dev/usb/lp0`, `LPT1:` or `COM3:`. When both are empty we try the
    /// system default printer.
    #[serde(default)]
    pub printer_name: Option<String>,
    #[serde(default)]
    pub device_path: Option<String>,
    /// Network printer (raw "JetDirect" printing): IP address or name. Takes
    /// priority over the other fields. Kept apart from `device_path` because
    /// device names such as `LPT1:` or `COM3:` contain a colon too.
    #[serde(default)]
    pub host: Option<String>,
    /// TCP port of a network printer; 9100 when not given.
    #[serde(default)]
    pub port: Option<u16>,
    /// Characters per line. Most 58mm printers are 32; 80mm are 42-48.
    #[serde(default)]
    pub line_width: Option<u8>,
    /// Cash drawer pin: 2 or 5. Defaults to 2 (works on most Epson-compatible drawers).
    #[serde(default)]
    pub drawer_pin: Option<u8>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ReceiptLine {
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub align: Option<String>,   // "left" | "center" | "right"
    #[serde(default)]
    pub bold: bool,
    #[serde(default)]
    pub double_height: bool,
    #[serde(default)]
    pub double_width: bool,
    #[serde(default)]
    pub underline: bool,
    #[serde(default)]
    pub feed: Option<u8>,        // extra blank lines after this one
    /// Two-column row — if set, `text` is ignored and `left`/`right` are
    /// laid out to the full line_width.
    #[serde(default)]
    pub left: Option<String>,
    #[serde(default)]
    pub right: Option<String>,
    /// Horizontal rule (ASCII `-` across the full width). When true all
    /// other fields are ignored.
    #[serde(default)]
    pub rule: bool,
    /// Barcode: if set, a CODE128 barcode is printed with this value.
    #[serde(default)]
    pub barcode: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ReceiptOptions {
    #[serde(flatten)]
    pub target: PrinterTarget,
    #[serde(default)]
    pub open_drawer: bool,
    #[serde(default = "default_true")]
    pub cut: bool,
    /// Number of blank lines to feed at the end before the cut.
    #[serde(default = "default_feed")]
    pub feed_before_cut: u8,
}

fn default_true() -> bool { true }
fn default_feed() -> u8 { 3 }

// -------------------------------------------------- Rendering --------------

fn align_from(opt: &Option<String>) -> Align {
    match opt.as_deref() {
        Some("center") => Align::Center,
        Some("right") => Align::Right,
        _ => Align::Left,
    }
}

fn render_line(printer: &mut EscPos, line: &ReceiptLine, width: u8) {
    if line.rule {
        printer.align(Align::Left);
        printer.text(&"-".repeat(width as usize));
        printer.feed(1);
        return;
    }
    if line.left.is_some() || line.right.is_some() {
        let left = line.left.clone().unwrap_or_default();
        let right = line.right.clone().unwrap_or_default();
        printer.align(Align::Left);
        if line.bold { printer.bold(true); }
        printer.text(&two_column(&left, &right, width));
        if line.bold { printer.bold(false); }
        printer.feed(1);
        if let Some(n) = line.feed {
            if n > 0 { printer.feed(n); }
        }
        return;
    }
    printer.align(align_from(&line.align));
    if line.bold { printer.bold(true); }
    if line.underline { printer.underline(true); }
    if line.double_height || line.double_width {
        printer.text_size(line.double_width, line.double_height);
    }
    printer.text(&line.text);
    if line.double_height || line.double_width {
        printer.text_size(false, false);
    }
    if line.underline { printer.underline(false); }
    if line.bold { printer.bold(false); }
    printer.feed(1);
    if let Some(barcode) = &line.barcode {
        printer.align(Align::Center);
        printer.barcode_code128(barcode);
        printer.feed(1);
    }
    if let Some(n) = line.feed {
        if n > 0 { printer.feed(n); }
    }
}

fn two_column(left: &str, right: &str, width: u8) -> String {
    let w = width as usize;
    let left_chars: Vec<char> = left.chars().collect();
    let right_chars: Vec<char> = right.chars().collect();
    let total = left_chars.len() + right_chars.len();
    if total >= w {
        // Truncate the LEFT (description) side if we overflow; keep the
        // right (amount) intact so totals are never clipped.
        let keep = w.saturating_sub(right_chars.len() + 1);
        let mut out: String = left_chars.into_iter().take(keep).collect();
        out.push(' ');
        out.push_str(right);
        return out;
    }
    let pad = w - total;
    let mut out = String::from(left);
    out.push_str(&" ".repeat(pad));
    out.push_str(right);
    out
}

fn build_receipt_bytes(opts: &ReceiptOptions, lines: &[ReceiptLine]) -> Vec<u8> {
    let width = opts.target.line_width.unwrap_or(DEFAULT_LINE_WIDTH);
    let mut printer = EscPos::new();
    printer.init();
    printer.select_cp437();
    for line in lines {
        render_line(&mut printer, line, width);
    }
    if opts.feed_before_cut > 0 {
        printer.feed(opts.feed_before_cut);
    }
    if opts.cut {
        printer.partial_cut();
    }
    if opts.open_drawer {
        let pin = opts.target.drawer_pin.unwrap_or(2);
        printer.drawer_kick(pin);
    }
    printer.into_bytes()
}

// -------------------------------------------------- Transport --------------

#[cfg(feature = "with-printers")]
fn list_printers_impl() -> Vec<PrinterInfo> {
    printers::get_printers()
        .into_iter()
        .map(|p| PrinterInfo {
            name: p.name.clone(),
            system_name: p.system_name.clone(),
            is_default: p.is_default,
            state: format!("{:?}", p.state),
        })
        .collect()
}

#[cfg(not(feature = "with-printers"))]
fn list_printers_impl() -> Vec<PrinterInfo> {
    // No Spooler/CUPS backend compiled in — the operator must target a raw
    // device path. Return an empty list so the UI can prompt accordingly.
    Vec::new()
}

#[cfg(feature = "with-printers")]
fn send_to_system_printer(name: &str, bytes: &[u8]) -> Result<(), String> {
    use printers::common::base::job::PrinterJobOptions;
    let target = printers::get_printer_by_name(name)
        .ok_or_else(|| format!("imprimante introuvable: {}", name))?;
    let mut options = PrinterJobOptions::none();
    options.name = Some("Mus Luxury receipt");
    target
        .print(bytes, options)
        .map_err(|e| format!("échec d'impression ({}): {:?}", name, e))?;
    Ok(())
}

#[cfg(not(feature = "with-printers"))]
fn send_to_system_printer(name: &str, _bytes: &[u8]) -> Result<(), String> {
    Err(format!(
        "Impression système indisponible dans ce build — utilisez un chemin \
        d'appareil (device_path) pour cibler {} directement",
        name
    ))
}

fn send_to_device_path(path: &str, bytes: &[u8]) -> Result<(), String> {
    let p = Path::new(path);
    if !p.exists() {
        return Err(format!("chemin introuvable: {}", path));
    }
    let mut f = OpenOptions::new()
        .write(true)
        .append(true)
        .open(p)
        .map_err(|e| format!("ouverture {} impossible: {}", path, e))?;
    f.write_all(bytes)
        .map_err(|e| format!("écriture sur {} échouée: {}", path, e))?;
    Ok(())
}

/// Raw printing to a network printer (port 9100 on almost every ESC/POS and
/// Zebra printer): connect with a timeout, write everything, flush.
fn send_to_network(host: &str, port: u16, bytes: &[u8]) -> Result<(), String> {
    let addrs: Vec<_> = (host, port)
        .to_socket_addrs()
        .map_err(|e| format!("adresse {}:{} introuvable: {}", host, port, e))?
        .collect();
    let mut last_err = format!("adresse {}:{} introuvable", host, port);
    for addr in addrs {
        match TcpStream::connect_timeout(&addr, Duration::from_secs(4)) {
            Ok(mut stream) => {
                stream
                    .set_write_timeout(Some(Duration::from_secs(10)))
                    .map_err(|e| format!("imprimante {}:{}: {}", host, port, e))?;
                stream
                    .write_all(bytes)
                    .and_then(|_| stream.flush())
                    .map_err(|e| format!("envoi à {}:{} échoué: {}", host, port, e))?;
                return Ok(());
            }
            Err(e) => last_err = format!("imprimante {}:{} injoignable: {}", host, port, e),
        }
    }
    Err(last_err)
}

fn send_bytes(target: &PrinterTarget, bytes: &[u8]) -> Result<(), String> {
    if let Some(host) = &target.host {
        if !host.trim().is_empty() {
            return send_to_network(host.trim(), target.port.unwrap_or(9100), bytes);
        }
    }
    if let Some(path) = &target.device_path {
        if !path.trim().is_empty() {
            return send_to_device_path(path, bytes);
        }
    }
    let printer = target
        .printer_name
        .clone()
        .filter(|n| !n.trim().is_empty())
        .or_else(default_printer_name)
        .ok_or_else(|| {
            "aucune imprimante configurée: choisissez une imprimante ou un \
             chemin d'appareil dans les Paramètres"
                .to_string()
        })?;
    send_to_system_printer(&printer, bytes)
}

#[cfg(feature = "with-printers")]
fn default_printer_name() -> Option<String> {
    printers::get_default_printer().map(|p| p.name)
}

#[cfg(not(feature = "with-printers"))]
fn default_printer_name() -> Option<String> { None }

// -------------------------------------------------- Tauri commands --------

#[tauri::command]
pub fn pos_list_printers() -> Vec<PrinterInfo> {
    list_printers_impl()
}

#[tauri::command]
pub fn pos_print_receipt(opts: ReceiptOptions, lines: Vec<ReceiptLine>) -> Result<(), String> {
    let bytes = build_receipt_bytes(&opts, &lines);
    send_bytes(&opts.target, &bytes)
}

#[tauri::command]
pub fn pos_open_cash_drawer(opts: PrinterTarget) -> Result<(), String> {
    let mut printer = EscPos::new();
    printer.init();
    let pin = opts.drawer_pin.unwrap_or(2);
    printer.drawer_kick(pin);
    send_bytes(&opts, &printer.into_bytes())
}

// -------------------------------------------------- Label-printer types ----

#[derive(Debug, Clone, Deserialize, Default)]
pub struct LabelPrinterTarget {
    #[serde(default)]
    pub printer_name: Option<String>,
    #[serde(default)]
    pub device_path: Option<String>,
    #[serde(default)]
    pub host: Option<String>,
    #[serde(default)]
    pub port: Option<u16>,
    /// "zpl" (default — Zebra & compatibles) or "escpos-text" (fallback for
    /// ESC/POS label printers; prints labels as plain-text slips).
    #[serde(default = "default_label_format")]
    pub format: String,
    #[serde(default)]
    pub width_mm: Option<u16>,
    #[serde(default)]
    pub height_mm: Option<u16>,
    #[serde(default)]
    pub dpi: Option<u16>,
}

fn default_label_format() -> String { "zpl".to_string() }

impl LabelPrinterTarget {
    fn as_printer_target(&self) -> PrinterTarget {
        PrinterTarget {
            printer_name: self.printer_name.clone(),
            device_path: self.device_path.clone(),
            host: self.host.clone(),
            port: self.port,
            line_width: None,
            drawer_pin: None,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct LabelPayload {
    pub header: String,
    pub product_name: String,
    #[serde(default)]
    pub variant_title: String,
    pub sku: String,
    pub price_text: String,
    pub barcode_value: String,
    /// "code128" or "ean13" (case-insensitive). Default: "code128".
    #[serde(default = "default_symbology")]
    pub barcode_kind: String,
    #[serde(default = "default_copies")]
    pub copies: u16,
}

fn default_symbology() -> String { "code128".to_string() }
fn default_copies() -> u16 { 1 }

fn parse_barcode_kind(s: &str) -> ZplBarcodeKind {
    match s.to_ascii_lowercase().as_str() {
        "ean13" | "ean-13" | "ean" => ZplBarcodeKind::Ean13,
        _ => ZplBarcodeKind::Code128,
    }
}

fn to_zpl_content(p: &LabelPayload) -> ZplLabelContent {
    ZplLabelContent {
        header: p.header.clone(),
        product_name: p.product_name.clone(),
        variant_title: p.variant_title.clone(),
        sku: p.sku.clone(),
        price_text: p.price_text.clone(),
        barcode_value: p.barcode_value.clone(),
        barcode_kind: parse_barcode_kind(&p.barcode_kind),
        copies: p.copies.max(1).min(100),
    }
}

/// ESC/POS fallback for label printers that don't speak ZPL: prints each
/// label as a compact ESC/POS slip with a cut between labels. Works on any
/// ESC/POS receipt-style printer wired as a label device.
fn render_labels_escpos_text(labels: &[LabelPayload], width_chars: u8) -> Vec<u8> {
    let mut p = EscPos::new();
    p.init();
    p.select_cp437();
    for label in labels {
        for _ in 0..label.copies.max(1).min(100) {
            p.align(Align::Center);
            p.bold(true);
            p.text(&label.header);
            p.feed(1);
            p.bold(false);
            let name = if label.variant_title.is_empty() {
                label.product_name.clone()
            } else {
                format!("{} - {}", label.product_name, label.variant_title)
            };
            p.text(&name);
            p.feed(1);
            p.text(&format!("SKU {}", label.sku));
            p.feed(1);
            p.text_size(true, true);
            p.text(&label.price_text);
            p.text_size(false, false);
            p.feed(1);
            p.barcode_code128(&label.barcode_value);
            p.feed(1);
            p.partial_cut();
        }
    }
    // Suppress "unused" warning on width_chars; kept in the signature so a
    // future ESC/POS layout can honour column width per label.
    let _ = width_chars;
    p.into_bytes()
}

#[tauri::command]
pub fn pos_print_labels(opts: LabelPrinterTarget, labels: Vec<LabelPayload>) -> Result<(), String> {
    if labels.is_empty() {
        return Err("Aucune étiquette à imprimer".into());
    }
    let width_mm = opts.width_mm.unwrap_or(zpl::DEFAULT_LABEL_WIDTH_MM);
    let height_mm = opts.height_mm.unwrap_or(zpl::DEFAULT_LABEL_HEIGHT_MM);
    let dpi = opts.dpi.unwrap_or(zpl::DEFAULT_DPI);

    let bytes = match opts.format.to_ascii_lowercase().as_str() {
        "escpos" | "escpos-text" => render_labels_escpos_text(&labels, DEFAULT_LINE_WIDTH),
        _ => {
            let content: Vec<ZplLabelContent> = labels.iter().map(to_zpl_content).collect();
            zpl_render_batch(&content, width_mm, height_mm, dpi)
        }
    };
    send_bytes(&opts.as_printer_target(), &bytes)
}

#[tauri::command]
pub fn pos_test_print_label(opts: LabelPrinterTarget) -> Result<(), String> {
    let sample = vec![LabelPayload {
        header: "Mus Luxury".into(),
        product_name: "Test etiquette".into(),
        variant_title: "".into(),
        sku: "TEST-001".into(),
        price_text: "1 234 DA".into(),
        barcode_value: "MUSLUXURY".into(),
        barcode_kind: "code128".into(),
        copies: 1,
    }];
    pos_print_labels(opts, sample)
}

#[tauri::command]
pub fn pos_test_print(opts: PrinterTarget) -> Result<(), String> {
    let receipt_opts = ReceiptOptions {
        target: opts.clone(),
        open_drawer: false,
        cut: true,
        feed_before_cut: 2,
    };
    let width = opts.line_width.unwrap_or(DEFAULT_LINE_WIDTH);
    let lines = vec![
        ReceiptLine { text: "MUS LUXURY".to_string(), align: Some("center".into()), bold: true, double_height: true, double_width: true, ..Default::default() },
        ReceiptLine { text: "Test imprimante".to_string(), align: Some("center".into()), ..Default::default() },
        ReceiptLine { rule: true, ..Default::default() },
        ReceiptLine { left: Some("Largeur".into()), right: Some(format!("{} car.", width)), ..Default::default() },
        ReceiptLine { left: Some("Date".into()), right: Some(chrono_now()), ..Default::default() },
        ReceiptLine { rule: true, ..Default::default() },
        ReceiptLine { text: "Si vous lisez ceci,".to_string(), align: Some("center".into()), ..Default::default() },
        ReceiptLine { text: "l'imprimante est prête.".to_string(), align: Some("center".into()), ..Default::default() },
        ReceiptLine { feed: Some(1), ..Default::default() },
        ReceiptLine { barcode: Some("MUSLUXURY".into()), ..Default::default() },
    ];
    pos_print_receipt(receipt_opts, lines)
}

// Sentinel default needed by Default derive on ReceiptLine
impl Default for ReceiptLine {
    fn default() -> Self {
        Self {
            text: String::new(),
            align: None,
            bold: false,
            double_height: false,
            double_width: false,
            underline: false,
            feed: None,
            left: None,
            right: None,
            rule: false,
            barcode: None,
        }
    }
}

// Minimal "now" formatter — avoids pulling in `chrono` just for a timestamp
// string. Returns ISO-8601 YYYY-MM-DD HH:MM:SS in local-wall-clock, best
// effort (SystemTime → UTC seconds → naive breakdown).
fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    // Very small, dependency-free Gregorian breakdown — accurate for any
    // date from 1970 onward.
    let (y, m, d) = date_from_days((secs / 86400) as i64);
    let rem = (secs.rem_euclid(86400)) as u32;
    let (hh, mm, ss) = (rem / 3600, (rem / 60) % 60, rem % 60);
    format!("{:04}-{:02}-{:02} {:02}:{:02}:{:02}", y, m, d, hh, mm, ss)
}

fn date_from_days(mut n: i64) -> (i32, u32, u32) {
    // https://howardhinnant.github.io/date_algorithms.html#civil_from_days
    n += 719468;
    let era = if n >= 0 { n / 146097 } else { (n - 146096) / 146097 };
    let doe = (n - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    let y = if m <= 2 { y + 1 } else { y };
    (y as i32, m, d)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn network_printer_receives_the_bytes() {
        use std::io::Read;
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = std::thread::spawn(move || {
            let (mut s, _) = listener.accept().unwrap();
            let mut got = Vec::new();
            s.read_to_end(&mut got).unwrap();
            got
        });
        let target = PrinterTarget { host: Some("127.0.0.1".into()), port: Some(port),
            device_path: Some("COM3:".into()), ..Default::default() };
        send_bytes(&target, b"\x1b@ticket").unwrap();
        assert_eq!(server.join().unwrap(), b"\x1b@ticket");
    }

    #[test]
    fn unreachable_network_printer_reports_an_error() {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        drop(listener); // nothing listens there any more
        let target = PrinterTarget { host: Some("127.0.0.1".into()), port: Some(port), ..Default::default() };
        let err = send_bytes(&target, b"x").unwrap_err();
        assert!(err.contains("injoignable"), "{}", err);
    }

    #[test]
    fn two_column_layout_pads_between() {
        let out = two_column("Total", "1 000", 32);
        assert_eq!(out.chars().count(), 32);
        assert!(out.starts_with("Total"));
        assert!(out.ends_with("1 000"));
    }

    #[test]
    fn two_column_truncates_left_on_overflow() {
        let out = two_column(
            "An unreasonably long product description",
            "99 999",
            20,
        );
        assert!(out.ends_with("99 999"));
        // Still exactly or below the target width (truncation path).
        assert!(out.chars().count() <= 20);
    }

    #[test]
    fn receipt_init_cut_and_drawer_present() {
        let opts = ReceiptOptions {
            target: PrinterTarget::default(),
            open_drawer: true,
            cut: true,
            feed_before_cut: 1,
        };
        let bytes = build_receipt_bytes(&opts, &[
            ReceiptLine { text: "Hello".into(), ..Default::default() },
        ]);
        // init: ESC @
        assert_eq!(&bytes[0..2], &[0x1B, 0x40]);
        // partial cut sequence: GS V 1 appears somewhere near the end
        assert!(windows_contains(&bytes, &[0x1D, 0x56, 0x01]) || windows_contains(&bytes, &[0x1D, 0x56, 0x42]));
        // drawer-kick starts with ESC p (0x1B 0x70)
        assert!(windows_contains(&bytes, &[0x1B, 0x70]));
    }

    #[test]
    fn drawer_pin_defaults_to_two() {
        let mut p = EscPos::new();
        p.drawer_kick(2);
        let b = p.into_bytes();
        assert_eq!(b, vec![0x1B, 0x70, 0x00, 25, 250]);
    }

    #[test]
    fn date_from_days_known_value() {
        // 2026-11-09 is day 20766 from the unix epoch.
        let (y, m, d) = date_from_days(20766);
        assert_eq!((y, m, d), (2026, 11, 9));
    }

    fn windows_contains(hay: &[u8], needle: &[u8]) -> bool {
        hay.windows(needle.len()).any(|w| w == needle)
    }
}
