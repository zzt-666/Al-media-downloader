import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      // Keep /api prefix — FastAPI routes are mounted under /api
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Keep SSE / long summarize streams from buffering or timing out
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
})
