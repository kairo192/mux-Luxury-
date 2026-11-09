/** @type {import('tailwindcss').Config} */
export default {
  // Scan index.html and every React file in src/ so JIT emits only classes
  // actually used by the live boutique.
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx,html}"],
  theme: {
    extend: {
      colors: {
        emerald: {
          deep: "#063D2E",
          forest: "#02291F",
          mid: "#0A523E",
          soft: "#0D4A3A",
        },
        gold: {
          reflective: "#D4AF62",
          light: "#E8D4A5",
          dark: "#B68F40",
          muted: "#C8A96E",
        },
        cream: {
          DEFAULT: "#F8F6F0",
          warm: "#F2EFE7",
          card: "#FAF9F5",
        },
        charcoal: "#202923",
      },
      fontFamily: {
        serif: ['"Playfair Display"', "Georgia", "serif"],
        sans: ["Montserrat", "Cairo", "sans-serif"],
      },
      boxShadow: {
        luxury: "0 10px 30px -10px rgba(2, 41, 31, 0.12)",
        "luxury-hover": "0 20px 40px -12px rgba(2, 41, 31, 0.22)",
        "gold-ring": "0 0 0 1px rgba(212, 175, 98, 0.35)",
      },
    },
  },
  plugins: [],
};
