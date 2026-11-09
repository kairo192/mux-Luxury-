// ============================================================================
// Pure-Rust ESC/POS byte builder.
// No external dependencies. Covered by unit tests in `mod.rs`.
//
// The subset of ESC/POS we need for retail receipts:
//   ESC @            — initialise / reset
//   ESC t n          — select code page  (0 = CP437, 16 = WPC1252 for French)
//   ESC a n          — align (0 left, 1 center, 2 right)
//   ESC E n          — emphasised (bold) on/off
//   ESC - n          — underline (0 off, 1 1-dot, 2 2-dot)
//   GS ! n           — character size: high nibble = width, low nibble = height
//   ESC d n          — print and feed n lines
//   GS V m           — cut paper; m = 0 full, 1 partial, 66 partial w/ feed
//   GS k m d1..dk 0  — barcode print (m = 73 = CODE128)
//   GS h n           — barcode height in dots (default 162 ≈ 20mm)
//   GS w n           — barcode width (2..6)
//   GS H n           — HRI position (0 off, 1 above, 2 below, 3 both)
//   ESC p m t1 t2    — drawer-kick: m=0 pin2, m=1 pin5, t1/t2 pulse timings
// ============================================================================

pub const DEFAULT_LINE_WIDTH: u8 = 32;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Align {
    Left,
    Center,
    Right,
}

#[derive(Debug, Default)]
pub struct EscPos {
    buf: Vec<u8>,
}

impl EscPos {
    pub fn new() -> Self {
        Self { buf: Vec::with_capacity(512) }
    }

    pub fn into_bytes(self) -> Vec<u8> {
        self.buf
    }

    #[cfg(test)]
    pub fn bytes(&self) -> &[u8] {
        &self.buf
    }

    pub fn init(&mut self) {
        self.buf.extend_from_slice(&[0x1B, 0x40]); // ESC @
    }

    pub fn select_cp437(&mut self) {
        // ESC t 0  selects CP437 (the broadest ESC/POS baseline).
        self.buf.extend_from_slice(&[0x1B, 0x74, 0x00]);
    }

    pub fn align(&mut self, a: Align) {
        let n = match a { Align::Left => 0, Align::Center => 1, Align::Right => 2 };
        self.buf.extend_from_slice(&[0x1B, 0x61, n]);
    }

    pub fn bold(&mut self, on: bool) {
        self.buf.extend_from_slice(&[0x1B, 0x45, if on { 1 } else { 0 }]);
    }

    pub fn underline(&mut self, on: bool) {
        self.buf.extend_from_slice(&[0x1B, 0x2D, if on { 1 } else { 0 }]);
    }

    pub fn text_size(&mut self, double_width: bool, double_height: bool) {
        // High nibble: width (0 = x1, 1 = x2); low nibble: height (0 = x1, 1 = x2).
        let w = if double_width { 1u8 } else { 0 };
        let h = if double_height { 1u8 } else { 0 };
        let n = (w << 4) | h;
        self.buf.extend_from_slice(&[0x1D, 0x21, n]);
    }

    pub fn text(&mut self, s: &str) {
        // Map common Latin-1 characters that aren't valid CP437 into close
        // equivalents, so French receipts don't show up as `?` on the slip.
        for ch in s.chars() {
            let byte = latin_to_cp437(ch);
            self.buf.push(byte);
        }
    }

    pub fn feed(&mut self, lines: u8) {
        if lines == 0 { return; }
        self.buf.extend_from_slice(&[0x1B, 0x64, lines]); // ESC d n
    }

    pub fn partial_cut(&mut self) {
        // GS V 66 n → partial cut with n extra lines of feed (0 is fine).
        self.buf.extend_from_slice(&[0x1D, 0x56, 0x42, 0x00]);
    }

    pub fn drawer_kick(&mut self, pin: u8) {
        // ESC p m t1 t2  — m=0 pin2, m=1 pin5.
        let m = if pin == 5 { 1u8 } else { 0 };
        // Pulse: 25 × 2ms on, 250 × 2ms off = 50ms/500ms (safe on Epson, Star, Bixolon).
        self.buf.extend_from_slice(&[0x1B, 0x70, m, 25, 250]);
    }

    pub fn barcode_code128(&mut self, data: &str) {
        // Height and width for readability.
        self.buf.extend_from_slice(&[0x1D, 0x68, 80]); // GS h 80
        self.buf.extend_from_slice(&[0x1D, 0x77, 2]);  // GS w 2
        self.buf.extend_from_slice(&[0x1D, 0x48, 2]);  // GS H 2 (HRI below)
        // GS k 73 n d1..dn  — CODE128, length-prefixed form (function 73).
        let bytes: Vec<u8> = data.bytes().take(255).collect();
        self.buf.extend_from_slice(&[0x1D, 0x6B, 73]);
        self.buf.push(bytes.len() as u8);
        self.buf.extend_from_slice(&bytes);
    }
}

/// Cheap mapper from a subset of Latin-1 to CP437. Covers the accented
/// characters we actually print on receipts (French). Any char outside the
/// mapping is passed through as its first UTF-8 byte truncated to CP437's
/// ASCII range or replaced with '?' to avoid garbled slips.
fn latin_to_cp437(ch: char) -> u8 {
    match ch {
        // ASCII passthrough
        c if (c as u32) < 128 => c as u8,
        // French accented letters in CP437
        'ç' => 0x87, 'Ç' => 0x80,
        'é' => 0x82, 'É' => 0x90,
        'è' => 0x8A, 'È' => 0xD4,
        'ê' => 0x88, 'Ê' => 0xD2,
        'ë' => 0x89, 'Ë' => 0xD3,
        'à' => 0x85, 'À' => 0xB7,
        'â' => 0x83, 'Â' => 0xB6,
        'î' => 0x8C, 'Î' => 0xD7,
        'ï' => 0x8B, 'Ï' => 0xD8,
        'ô' => 0x93, 'Ô' => 0xE2,
        'û' => 0x96, 'Û' => 0xEA,
        'ù' => 0x97, 'Ù' => 0xEB,
        'ü' => 0x81, 'Ü' => 0x9A,
        'ö' => 0x94, 'Ö' => 0x99,
        'ä' => 0x84, 'Ä' => 0x8E,
        // Currency / punctuation
        '€' => 0x9E,
        '°' => 0xF8,
        '«' => 0xAE, '»' => 0xAF,
        '–' | '—' => b'-',
        '’' | '‘' => b'\'',
        '“' | '”' => b'"',
        '…' => b'.',
        '\u{00A0}' => b' ', // non-breaking space
        _ => b'?',
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn init_emits_esc_at() {
        let mut p = EscPos::new();
        p.init();
        assert_eq!(p.bytes(), &[0x1B, 0x40]);
    }

    #[test]
    fn align_center_emits_esc_a_1() {
        let mut p = EscPos::new();
        p.align(Align::Center);
        assert_eq!(p.bytes(), &[0x1B, 0x61, 1]);
    }

    #[test]
    fn bold_toggle_round_trip() {
        let mut p = EscPos::new();
        p.bold(true);
        p.bold(false);
        assert_eq!(p.bytes(), &[0x1B, 0x45, 1, 0x1B, 0x45, 0]);
    }

    #[test]
    fn text_maps_french_accents() {
        let mut p = EscPos::new();
        p.text("Café");
        // C a f é_cp437(0x82)
        assert_eq!(p.bytes(), &[0x43, 0x61, 0x66, 0x82]);
    }

    #[test]
    fn text_size_encodes_width_height_nibbles() {
        let mut p = EscPos::new();
        p.text_size(true, true);
        // (1 << 4) | 1 = 0x11
        assert_eq!(p.bytes(), &[0x1D, 0x21, 0x11]);
    }

    #[test]
    fn partial_cut_emits_gs_v_66_0() {
        let mut p = EscPos::new();
        p.partial_cut();
        assert_eq!(p.bytes(), &[0x1D, 0x56, 0x42, 0x00]);
    }

    #[test]
    fn drawer_kick_defaults_pin2() {
        let mut p = EscPos::new();
        p.drawer_kick(2);
        assert_eq!(p.bytes(), &[0x1B, 0x70, 0x00, 25, 250]);
    }

    #[test]
    fn drawer_kick_pin5_uses_m1() {
        let mut p = EscPos::new();
        p.drawer_kick(5);
        assert_eq!(p.bytes(), &[0x1B, 0x70, 0x01, 25, 250]);
    }

    #[test]
    fn barcode_code128_has_gs_k_73_and_length_prefix() {
        let mut p = EscPos::new();
        p.barcode_code128("AB");
        let b = p.bytes();
        // Find GS k 73 len 'A' 'B'
        let idx = b.windows(3).position(|w| w == [0x1D, 0x6B, 73]).expect("GS k 73 missing");
        assert_eq!(b[idx + 3], 2); // length
        assert_eq!(&b[idx + 4..idx + 6], b"AB");
    }

    #[test]
    fn unknown_char_becomes_question_mark() {
        assert_eq!(latin_to_cp437('漢'), b'?');
    }
}
