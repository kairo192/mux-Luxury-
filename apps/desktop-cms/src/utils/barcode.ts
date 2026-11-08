// ---------------------------------------------------------------------------
// Minimal, dependency-free barcode renderer → SVG markup.
// Supports Code 128 (set B) for alphanumeric SKUs and EAN-13 for numeric retail
// codes. Returns an <svg> string; callers inject it (dangerouslySetInnerHTML)
// or print it. Not a scanner — rendering only.
// ---------------------------------------------------------------------------

// Code 128 width patterns (values 0..106), 6 module-widths each; stop is 7.
const CODE128_PATTERNS = [
  "212222","222122","222221","121223","121322","131222","122213","122312","132212","221213",
  "221312","231212","112232","122132","122231","113222","123122","123221","223211","221132",
  "221231","213212","223112","312131","311222","321122","321221","312212","322112","322211",
  "212123","212321","232121","111323","131123","131321","112313","132113","132311","211313",
  "231113","231311","112133","112331","132131","113123","113321","133121","313121","211331",
  "231131","213113","213311","213131","311123","311321","331121","312113","312311","332111",
  "314111","221411","431111","111224","111422","121124","121421","141122","141221","112214",
  "112412","122114","122411","142112","142211","241211","221114","413111","241112","134111",
  "111242","121142","121241","114212","124112","124211","411212","421112","421211","212141",
  "214121","412121","111143","111341","131141","114113","114311","411113","411311","113141",
  "114131","311141","411131","211412","211214","211232","2331112",
];
const CODE128_START_B = 104;
const CODE128_STOP = 106;

// EAN-13 7-bit encodings (1=bar, 0=space).
const EAN_L = ["0001101","0011001","0010011","0111101","0100011","0110001","0101111","0111011","0110111","0001011"];
const EAN_G = ["0100111","0110011","0011011","0100001","0011101","0111001","0000101","0010001","0001001","0010111"];
const EAN_R = ["1110010","1100110","1101100","1000010","1011100","1001110","1010000","1000100","1001000","1110100"];
const EAN_PARITY = ["LLLLLL","LLGLGG","LLGGLG","LLGGGL","LGLLGG","LGGLLG","LGGGLL","LGLGLG","LGLGGL","LGGLGL"];

export type Symbology = "ean13" | "code128";

export function detectSymbology(code: string): Symbology {
  const c = (code || "").trim();
  return /^\d{13}$/.test(c) ? "ean13" : "code128";
}

// Returns an array of {x, w} bar rectangles (space runs omitted) plus total module width.
function code128Modules(value: string): { bars: Array<[number, number]>; width: number } {
  const chars = Array.from(value);
  const codes: number[] = [CODE128_START_B];
  for (const ch of chars) {
    const v = ch.charCodeAt(0) - 32; // Set B: ASCII 32..126 → 0..94
    if (v < 0 || v > 94) throw new Error(`Caractère non supporté en Code 128: ${ch}`);
    codes.push(v);
  }
  let sum = CODE128_START_B;
  codes.slice(1).forEach((v, i) => (sum += v * (i + 1)));
  codes.push(sum % 103); // checksum
  codes.push(CODE128_STOP);

  const bars: Array<[number, number]> = [];
  let x = 0;
  for (const code of codes) {
    const pattern = CODE128_PATTERNS[code];
    for (let i = 0; i < pattern.length; i++) {
      const w = parseInt(pattern[i], 10);
      if (i % 2 === 0) bars.push([x, w]); // even index = bar
      x += w;
    }
  }
  return { bars, width: x };
}

function ean13Bits(code: string): string {
  if (!/^\d{13}$/.test(code)) throw new Error("EAN-13 requiert 13 chiffres");
  const digits = code.split("").map((d) => parseInt(d, 10));
  const parity = EAN_PARITY[digits[0]];
  let bits = "101"; // start guard
  for (let i = 1; i <= 6; i++) {
    bits += parity[i - 1] === "L" ? EAN_L[digits[i]] : EAN_G[digits[i]];
  }
  bits += "01010"; // center guard
  for (let i = 7; i <= 12; i++) bits += EAN_R[digits[i]];
  bits += "101"; // end guard
  return bits;
}

interface BarcodeOptions {
  moduleWidth?: number; // px per module
  height?: number; // bar height px
  showText?: boolean;
  color?: string;
}

export function renderBarcodeSvg(value: string, symbology?: Symbology, opts: BarcodeOptions = {}): string {
  const sym = symbology || detectSymbology(value);
  const mw = opts.moduleWidth ?? 2;
  const h = opts.height ?? 60;
  const color = opts.color ?? "#000000";
  const showText = opts.showText ?? true;
  const quiet = 10; // quiet-zone modules
  const textH = showText ? 16 : 0;

  let rects = "";
  let totalModules = 0;

  if (sym === "ean13") {
    const bits = ean13Bits(value);
    totalModules = bits.length;
    let run = 0;
    for (let i = 0; i <= bits.length; i++) {
      if (bits[i] === "1") {
        run++;
      } else {
        if (run > 0) {
          const x = (quiet + i - run) * mw;
          rects += `<rect x="${x}" y="0" width="${run * mw}" height="${h}" fill="${color}"/>`;
        }
        run = 0;
      }
    }
  } else {
    const { bars, width } = code128Modules(value);
    totalModules = width;
    for (const [x, w] of bars) {
      rects += `<rect x="${(quiet + x) * mw}" y="0" width="${w * mw}" height="${h}" fill="${color}"/>`;
    }
  }

  const svgW = (totalModules + quiet * 2) * mw;
  const svgH = h + textH;
  const text = showText
    ? `<text x="${svgW / 2}" y="${h + 13}" font-family="monospace" font-size="13" text-anchor="middle" fill="${color}">${value}</text>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}">${rects}${text}</svg>`;
}
