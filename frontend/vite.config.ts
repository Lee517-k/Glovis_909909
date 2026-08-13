import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 외부 IP로 접속하려면 localhost가 아니라 모든 인터페이스에 바인딩해야 함
    host: true,
    proxy: {
      // 브라우저는 자기가 접속한 origin(:5173)으로만 요청하고, dev server가 서버 내부에서
      // 백엔드로 넘긴다. API 주소에 IP를 박을 필요가 없고 CORS도 발생하지 않는다.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    // maplibre-gl은 내부 워커 파일을 esbuild 사전번들링이 못 다뤄서 지도가 검게 나온다.
    exclude: ["maplibre-gl"],
  },
});

