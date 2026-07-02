import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  base: "/static/build/",
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "web_dashboard/build"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "web_dashboard/src/main.jsx"),
      output: {
        entryFileNames: "dashboard.js",
        chunkFileNames: "[name]-[hash].js",
        assetFileNames: ({ names }) =>
          names?.some((name) => name.endsWith(".css")) ? "dashboard.css" : "[name]-[hash][extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./web_dashboard/src/test/setup.js"],
  },
});
