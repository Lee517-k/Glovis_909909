import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  optimizeDeps: {
    // maplibre-gl은 내부 워커 파일을 esbuild 사전번들링이 못 다뤄서 지도가 검게 나온다.
    exclude: ["maplibre-gl"],
  },
});

