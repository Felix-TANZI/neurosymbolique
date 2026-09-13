import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const racine = dirname(fileURLToPath(import.meta.url));

// Chaque construction porte une empreinte distincte: le guide s'en sert pour
// se presenter de nouveau apres un deploiement. En developpement, elle reste
// fixe afin que le guide ne reapparaisse pas a chaque relance du serveur.
export default defineConfig(({ command }) => ({
  define: {
    "import.meta.env.VITE_CONSTRUCTION": JSON.stringify(
      command === "build" ? new Date().toISOString() : "developpement",
    ),
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": resolve(racine, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (chemin) => chemin.replace(/^\/api/, ""),
      },
    },
  },
}));