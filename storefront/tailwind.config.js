/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        emerald: {
          deep: "#063D2E",
          forest: "#02291F"
        },
        gold: {
          reflective: "#D4AF62",
          light: "#E8D4A5"
        },
        cream: "#F8F6F0",
        charcoal: "#202923"
      },
      fontFamily: {
        serif: ["Playfair Display", "Georgia", "serif"],
        sans: ["Montserrat", "Cairo", "sans-serif"]
      }
    }
  },
  plugins: []
};
