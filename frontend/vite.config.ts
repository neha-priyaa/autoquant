/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Deploy targets with a base path (GitHub Pages under /autoquant/) must
  // pass --base=/autoquant/ to `vite build`; default build is root-relative
  // for Vercel.
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        // Keep the entry (landing) chunk small (#39) by splitting the
        // framework bundle and the generated snapshot data it shares.
        manualChunks(id) {
          if (id.includes("node_modules")) return "vendor";
          if (id.includes("snapshot.json")) return "snapshot";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    globals: true,
  },
});
