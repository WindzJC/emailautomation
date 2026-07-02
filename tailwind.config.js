/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./web_dashboard/index.html",
    "./web_dashboard/src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#080b10",
        surface: "#0e141c",
        elevated: "#121a24",
        ink: "#f3f6fa",
        muted: "#9ca9ba",
        accent: "#dfba69",
      },
      boxShadow: {
        console: "0 18px 48px rgba(0, 0, 0, 0.24)",
      },
    },
  },
  plugins: [],
};
