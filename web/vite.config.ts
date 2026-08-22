import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  build: { outDir: "dist", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:18880", "/healthz": "http://127.0.0.1:18880", "/m": "http://127.0.0.1:18880" } },
});
