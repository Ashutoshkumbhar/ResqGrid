import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendTarget = process.env.VITE_PROXY_TARGET || process.env.VITE_API_URL || 'http://127.0.0.1:8000'
const wsTarget = process.env.VITE_WS_URL || backendTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.VITE_FRONTEND_PORT || 5173),
    strictPort: false,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
      }
    }
  },
  build: {
    cssMinify: false
  }
})
