import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const dashboardRoot = resolve(__dirname, "web_dashboard");

export function contentFingerprint(content) {
  return createHash("sha256").update(content).digest("hex").slice(0, 16);
}

export function fingerprintedAssetUrl(publicPath, content) {
  return `${publicPath}?v=${contentFingerprint(content)}`;
}

const legacyAppPath = resolve(dashboardRoot, "app.js");
const legacyAppAssetUrl = fingerprintedAssetUrl(
  "/static/app.js",
  readFileSync(legacyAppPath),
);

export default defineConfig({
  root: dashboardRoot,
  base: "/static/build/",
  plugins: [react()],
  define: {
    __LEGACY_APP_ASSET_URL__: JSON.stringify(legacyAppAssetUrl),
  },
  build: {
    outDir: resolve(dashboardRoot, "build"),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: resolve(dashboardRoot, "index.html"),
      output: {
        entryFileNames: "assets/dashboard-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
  },
});
