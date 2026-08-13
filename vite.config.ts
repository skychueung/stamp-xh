import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { inspectAttr } from 'plugin-inspect-react-code'

// https://vite.dev/config/
export default defineConfig({
  base: '/',
  plugins: [inspectAttr(), react()],
  server: {
    host: true,
    port: 12823,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.STAMP_PROXY_TARGET || "http://127.0.0.1:12824",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 12823,
    host: true,
    proxy: {
      "/api": {
        target: process.env.STAMP_PROXY_TARGET || "http://127.0.0.1:12824",
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
