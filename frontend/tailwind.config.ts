import type { Config } from "tailwindcss";

// Paleta tomada del logo de Nomira.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        marino: { DEFAULT: "#123048", 700: "#0F263C", 900: "#0A1B2B", 50: "#EFF4F8", 100: "#DCE6EE", 300: "#8FA6B8" },
        turquesa: { DEFAULT: "#01B2A6", 700: "#047A72", 50: "#E5F8F6", 100: "#C2EFEA", brillante: "#01E9CD" },
        crema: { DEFAULT: "#FCF9F4", 200: "#F3EEE5", 300: "#E7E1D6" },
      },
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        marca: ['"Montserrat Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        suave: "0 1px 2px rgba(18,48,72,.04), 0 8px 24px -12px rgba(18,48,72,.12)",
        flotante: "0 24px 60px -20px rgba(10,27,43,.35)",
      },
    },
  },
  plugins: [],
};
export default config;
