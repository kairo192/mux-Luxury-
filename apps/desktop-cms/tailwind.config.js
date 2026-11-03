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
        serif: ["Cinzel", "Playfair Display", "Georgia", "serif"],
        sans: ["'Plus Jakarta Sans'", "Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        luxe: "0 10px 30px -5px rgba(6, 61, 46, 0.12)",
        "luxe-gold": "0 10px 25px -5px rgba(212, 175, 98, 0.22)",
        glow: "0 0 25px rgba(212, 175, 98, 0.25)",
      },
    },
  },
  plugins: [],
};
