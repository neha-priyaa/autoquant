/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Deploy targets with a base path (GitHub Pages under /autoquant/) must
  // pass --base=/autoquant/ to `vite build`; default build is root-relative
  // for Vercel.
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    globals: true,
  },
});
