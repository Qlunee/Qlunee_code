import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_BACKEND_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
