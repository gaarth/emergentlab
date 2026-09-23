import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: vite on 5173 proxies data + API to server.py on 8000. Build: output served by server.py at /app/dist/.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    proxy: Object.fromEntries(["/tree.json", "/frames", "/api", "/paper.html", "/viewer.html"].map((p) => [p, "http://127.0.0.1:8000"])),
  },
});
