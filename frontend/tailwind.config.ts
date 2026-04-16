import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        mist: "#edf2f7",
        tide: "#0f766e",
      },
    },
  },
  plugins: [],
} satisfies Config;
