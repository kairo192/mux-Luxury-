// ============================================================================
// Pure-Rust ZPL II builder for label printers (Zebra, compatible OEMs).
//
// ZPL is the de-facto standard for dedicated retail label printers — Zebra
// ZD230, ZD421, GK420 and most compatibles all accept it. It is a text
// protocol: a label is wrapped in `^XA` … `^XZ`, with each field positioned
// absolutely by the `^FO x,y` command. Dimensions are in printer dots:
//   203 dpi  ≈ 8 dots/mm (most common on 50×30mm boutique labels)
//   300 dpi  ≈ 12 dots/mm
//
// The barcode primitives we use:
//   ^BCN,h,Y,N,N      CODE128 (height=h dots, print interpretation line)
//   ^BEN,h,Y,N        EAN-13
//
// Font sizing uses the built-in `^CF0,height` scalable font (0 is the
// default upright vector). Everything else — bold, centering — is faked by
// choosing fonts/positions, keeping the protocol subset small and portable.
// ============================================================================

pub const DEFAULT_LABEL_WIDTH_MM: u16 = 50;
pub const DEFAULT_LABEL_HEIGHT_MM: u16 = 30;
pub const DEFAULT_DPI: u16 = 203;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BarcodeKind {
    Code128,
    Ean13,
}

#[derive(Debug, Default)]
pub struct Zpl {
    buf: String,
    pub dots_per_mm: u16,
}

impl Zpl {
    pub fn new(dpi: u16) -> Self {
        let dots_per_mm = match dpi {
            300 => 12,
            600 => 24,
            _ => 8, // 203 dpi fallback
        };
        Self { buf: String::with_capacity(512), dots_per_mm }
    }

    pub fn mm(&self, mm: u16) -> u16 {
        mm * self.dots_per_mm
    }

    pub fn start_label(&mut self, width_mm: u16, _height_mm: u16) {
        // ^XA — begin label format.
        // ^PW — print width in dots (full label width).
        // ^LH 0,0 — label home top-left.
        self.buf.push_str("^XA\n");
        self.buf.push_str(&format!("^PW{}\n", self.mm(width_mm)));
        self.buf.push_str("^LH0,0\n");
        // ^CI28 — UTF-8 input so accented characters print correctly.
        self.buf.push_str("^CI28\n");
    }

    pub fn end_label(&mut self) {
        self.buf.push_str("^XZ\n");
    }

    /// Set the default font height (dots). ZPL's scalable font 0 handles
    /// any height; width is proportional unless we override it.
    pub fn set_font_height(&mut self, height_dots: u16) {
        self.buf.push_str(&format!("^CF0,{}\n", height_dots));
    }

    pub fn text(&mut self, x_dots: u16, y_dots: u16, s: &str) {
        self.buf.push_str(&format!(
            "^FO{},{}^FD{}^FS\n",
            x_dots,
            y_dots,
            zpl_escape(s),
        ));
    }

    /// Text at a given height in dots — convenient when a single label uses
    /// mixed sizes without resetting ^CF0.
    pub fn text_sized(&mut self, x_dots: u16, y_dots: u16, s: &str, height_dots: u16, width_dots: u16) {
        self.buf.push_str(&format!(
            "^FO{},{}^A0N,{},{}^FD{}^FS\n",
            x_dots,
            y_dots,
            height_dots,
            width_dots,
            zpl_escape(s),
        ));
    }

    pub fn barcode(&mut self, x_dots: u16, y_dots: u16, kind: BarcodeKind, value: &str, height_dots: u16) {
        // ^BY sets module width (bar) and height-ratio. Module 2 at 203 dpi
        // gives ~0.25 mm narrow bars — scannable on cheap readers.
        self.buf.push_str(&format!("^BY2,2,{}\n", height_dots));
        self.buf.push_str(&format!("^FO{},{}\n", x_dots, y_dots));
        match kind {
            BarcodeKind::Code128 => {
                // ^BC orientation,height,interpretation,above,check
                self.buf.push_str(&format!("^BCN,{},Y,N,N\n", height_dots));
            }
            BarcodeKind::Ean13 => {
                self.buf.push_str(&format!("^BEN,{},Y,N\n", height_dots));
            }
        }
        self.buf.push_str(&format!("^FD{}^FS\n", zpl_escape(value)));
    }

    /// Number of copies to print for THIS label format. Equivalent to
    /// invoking the same label N times but much faster — the printer itself
    /// replicates it without round-tripping the host.
    pub fn print_quantity(&mut self, copies: u16) {
        if copies > 1 {
            self.buf.push_str(&format!("^PQ{},0,1,Y\n", copies));
        }
    }

    pub fn into_bytes(self) -> Vec<u8> {
        self.buf.into_bytes()
    }

    #[cfg(test)]
    pub fn as_str(&self) -> &str {
        &self.buf
    }
}

/// ZPL reserves `^` `~` `\` as control characters inside `^FD` data fields.
/// Replace them with hex-encoded equivalents so a product name with an `^`
/// in it doesn't accidentally terminate the field.
fn zpl_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '^' => out.push_str("_5E"),
            '~' => out.push_str("_7E"),
            '\\' => out.push_str("_5C"),
            '\n' | '\r' => out.push(' '),
            c => out.push(c),
        }
    }
    out
}

// -------------------------------------------------- Label composition -----

#[derive(Debug, Clone)]
pub struct LabelContent {
    pub header: String,       // boutique / store name
    pub product_name: String,
    pub variant_title: String,
    pub sku: String,
    pub price_text: String,   // formatted price including currency
    pub barcode_value: String,
    pub barcode_kind: BarcodeKind,
    pub copies: u16,
}

/// Render one LabelContent onto one ZPL label, sized for the given width/
/// height (mm) and DPI. Layout is fixed: header small, product name small,
/// SKU small, price big, barcode at the bottom.
pub fn render_label(content: &LabelContent, width_mm: u16, height_mm: u16, dpi: u16) -> Vec<u8> {
    let mut z = Zpl::new(dpi);
    let w = z.dots_per_mm as u16 * width_mm;
    z.start_label(width_mm, height_mm);

    // Vertical cursor in dots.
    let left = z.mm(2);
    let mut y = z.mm(2);

    // Header (centred-ish, small)
    z.text_sized(left, y, &content.header, z.mm(3), z.mm(3));
    y += z.mm(4);

    // Product line
    let product_line = if content.variant_title.is_empty() {
        content.product_name.clone()
    } else {
        format!("{} - {}", content.product_name, content.variant_title)
    };
    z.text_sized(left, y, &clip_for_width(&product_line, w, z.mm(3)), z.mm(3), z.mm(3));
    y += z.mm(4);

    // SKU
    z.text_sized(left, y, &format!("SKU {}", content.sku), z.mm(3), z.mm(2));
    y += z.mm(4);

    // Price — twice as tall, right-ish positioning.
    z.text_sized(left, y, &content.price_text, z.mm(6), z.mm(5));
    y += z.mm(8);

    // Barcode — fill the rest of the label vertically up to the bottom margin.
    let bottom_margin = z.mm(2);
    let remaining = height_mm.saturating_sub((y / z.dots_per_mm) + bottom_margin / z.dots_per_mm);
    let bar_h = z.mm(remaining.max(8));
    z.barcode(left, y, content.barcode_kind, &content.barcode_value, bar_h);

    z.print_quantity(content.copies);
    z.end_label();
    z.into_bytes()
}

/// Rough clip of a text to fit within `width_dots` at a given font width
/// (approximate). Prevents the product-name line from overflowing the label.
fn clip_for_width(s: &str, width_dots: u16, approx_char_width_dots: u16) -> String {
    if approx_char_width_dots == 0 {
        return s.to_string();
    }
    let max_chars = (width_dots / approx_char_width_dots) as usize;
    if s.chars().count() <= max_chars {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(max_chars.saturating_sub(1)).collect();
        out.push('…');
        out
    }
}

/// Render N labels into one ZPL byte stream. Prefer this over calling
/// render_label repeatedly: it writes the format once with `^PQ copies`.
pub fn render_batch(labels: &[LabelContent], width_mm: u16, height_mm: u16, dpi: u16) -> Vec<u8> {
    let mut out: Vec<u8> = Vec::with_capacity(labels.len() * 512);
    for label in labels {
        out.extend_from_slice(&render_label(label, width_mm, height_mm, dpi));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dpi_to_dots_per_mm() {
        assert_eq!(Zpl::new(203).dots_per_mm, 8);
        assert_eq!(Zpl::new(300).dots_per_mm, 12);
        assert_eq!(Zpl::new(600).dots_per_mm, 24);
        assert_eq!(Zpl::new(0).dots_per_mm, 8); // unknown DPI falls back to 203
    }

    #[test]
    fn label_wrapping_tags_present() {
        let mut z = Zpl::new(203);
        z.start_label(50, 30);
        z.text(10, 10, "hello");
        z.end_label();
        let s = z.as_str();
        assert!(s.starts_with("^XA"));
        assert!(s.contains("^PW400"));            // 50mm × 8 dots/mm
        assert!(s.contains("^FO10,10^FDhello^FS"));
        assert!(s.ends_with("^XZ\n"));
    }

    #[test]
    fn code128_barcode_uses_bcn() {
        let mut z = Zpl::new(203);
        z.barcode(0, 0, BarcodeKind::Code128, "ABC123", 60);
        let s = z.as_str();
        assert!(s.contains("^BCN,60,Y,N,N"));
        assert!(s.contains("^FDABC123^FS"));
    }

    #[test]
    fn ean13_barcode_uses_ben() {
        let mut z = Zpl::new(203);
        z.barcode(0, 0, BarcodeKind::Ean13, "0123456789012", 60);
        assert!(z.as_str().contains("^BEN,60,Y,N"));
    }

    #[test]
    fn caret_in_data_is_escaped() {
        let escaped = zpl_escape("A^B");
        assert_eq!(escaped, "A_5EB");
    }

    #[test]
    fn print_quantity_above_one_emits_pq() {
        let mut z = Zpl::new(203);
        z.print_quantity(5);
        assert!(z.as_str().contains("^PQ5"));
    }

    #[test]
    fn print_quantity_one_is_omitted() {
        let mut z = Zpl::new(203);
        z.print_quantity(1);
        assert!(z.as_str().is_empty());
    }

    #[test]
    fn render_label_full_fixture() {
        // A short-enough product line to clear the auto-clip at 50 mm width.
        let label = LabelContent {
            header: "Mus Luxury".into(),
            product_name: "Lin".into(),
            variant_title: "Beige M".into(),
            sku: "LN-BM".into(),
            price_text: "4 500 DA".into(),
            barcode_value: "6209876543210".into(),
            barcode_kind: BarcodeKind::Ean13,
            copies: 3,
        };
        let bytes = render_label(&label, 50, 30, 203);
        let s = std::str::from_utf8(&bytes).unwrap();
        assert!(s.contains("^XA"));
        assert!(s.contains("Mus Luxury"));
        assert!(s.contains("Lin - Beige M"));
        assert!(s.contains("SKU LN-BM"));
        assert!(s.contains("4 500 DA"));
        assert!(s.contains("^BEN,"));
        assert!(s.contains("^FD6209876543210^FS"));
        assert!(s.contains("^PQ3"));
        assert!(s.ends_with("^XZ\n"));
    }

    #[test]
    fn long_product_name_is_clipped_with_ellipsis() {
        let label = LabelContent {
            header: "Mus Luxury".into(),
            product_name: "An unreasonably long product name that will not fit".into(),
            variant_title: "".into(),
            sku: "X".into(),
            price_text: "1 DA".into(),
            barcode_value: "1".into(),
            barcode_kind: BarcodeKind::Code128,
            copies: 1,
        };
        let bytes = render_label(&label, 50, 30, 203);
        let s = std::str::from_utf8(&bytes).unwrap();
        assert!(s.contains("…"), "expected ellipsis clip marker, got: {}", s);
    }

    #[test]
    fn render_batch_emits_one_xa_per_label() {
        let label = LabelContent {
            header: "Mus".into(), product_name: "P".into(), variant_title: "".into(),
            sku: "S".into(), price_text: "1 DA".into(),
            barcode_value: "123".into(), barcode_kind: BarcodeKind::Code128, copies: 1,
        };
        let bytes = render_batch(&[label.clone(), label.clone(), label.clone()], 50, 30, 203);
        let s = std::str::from_utf8(&bytes).unwrap();
        assert_eq!(s.matches("^XA").count(), 3);
        assert_eq!(s.matches("^XZ").count(), 3);
    }
}
