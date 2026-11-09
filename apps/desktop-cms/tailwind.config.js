/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        luxe: {
          emerald: "#063D2E",
          dark: "#02291F",
          emeraldLight: "#0B5843",
          gold: "#D4AF62",
          goldLight: "#E8D4A5",
          goldMuted: "#C59E50",
          cream: "#F8F6F0",
          stone: "#EFECE6",
          charcoal: "#1A2421",
        },
      },
      fontFamily: {
        // Cairo + Noto Sans Arabic are the two broadly-available web fonts
        // with strong Arabic glyph coverage. The CSS stack lets the system
        // pick whichever is installed (we do not bundle web fonts, so the
        // Tauri WebView falls back to the OS Arabic UI font — fine in Windows).
        serif: ["Cinzel", "Playfair Display", "Georgia", "serif"],
        sans: ["'Plus Jakarta Sans'", "Inter", "Cairo", "'Noto Sans Arabic'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        luxe: "0 10px 30px -5px rgba(6, 61, 46, 0.12)",
        "luxe-gold": "0 10px 25px -5px rgba(212, 175, 98, 0.22)",
        glow: "0 0 25px rgba(212, 175, 98, 0.25)",
      },
    },
  },
  plugins: [
    // Enable `rtl:` + `ltr:` variants driven by the `dir` attribute on any
    // ancestor. The i18n provider in src/i18n/index.tsx sets this on
    // <html>, so `className="pl-4 rtl:pl-0 rtl:pr-4"` gives us direction-
    // aware styling without a second utility pass.
    function ({ addVariant }) {
      addVariant("rtl", '&:where([dir="rtl"], [dir="rtl"] *)');
      addVariant("ltr", '&:where([dir="ltr"], [dir="ltr"] *)');
    },
  ],
};
