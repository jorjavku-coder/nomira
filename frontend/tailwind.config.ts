import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        marino: { DEFAULT: "#12305A", 700: "#0D2444", 50: "#EEF3FA", 100: "#DCE6F4" },
        turquesa: { DEFAULT: "#14B8A6", 700: "#0F8F82", 50: "#E6FAF7" },
      },
    },
  },
  plugins: [],
};
export default config;
