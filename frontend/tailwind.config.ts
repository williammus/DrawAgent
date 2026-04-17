import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: "#111315",
        panel: "#17191c",
        ink: "#f8fafc",
        mist: "#94a3b8",
        tide: "#10a37f",
      },
    },
  },
  plugins: [],
} satisfies Config;
