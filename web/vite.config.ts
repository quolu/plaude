import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  publicDir: "public",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:18880",
      "/healthz": "http://127.0.0.1:18880",
      "/m": {
        target: "http://127.0.0.1:18880",
        bypass(req) {
          const url = req.url || "";
          if (/^\/m\/[^/]+\/audio(?:\?|$)/.test(url)) return;
          return "/index.html";
        },
      },
    },
  },
});
