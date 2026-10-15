/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        sky: { 300: "#7FC4EF", 500: "#3B9FE0" },
        amber: { 400: "#F2B33D", 500: "#E29A1F" },
        ink: { 800: "#1A1A1D", 950: "#0E0E10" },
        parchment: { 50: "#FBF7EE" },
        body: { 300: "#A8A8AE", 500: "#6B7280" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "hero-overlay":
          "linear-gradient(to bottom, rgba(14,14,16,0.30), rgba(14,14,16,0) 30%, #FBF7EE 92%)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
    },
  },
  plugins: [],
};
