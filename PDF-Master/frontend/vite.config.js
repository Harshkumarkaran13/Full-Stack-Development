import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/react/',
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/download': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
      '/tool': 'http://127.0.0.1:8000',
      '/history': 'http://127.0.0.1:8000'
    }
  },
  build: {
    outDir: '../static/react',
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'chunks/[name].js',
        assetFileNames: (assetInfo) => assetInfo.name?.endsWith('.css') ? 'app.css' : 'assets/[name][extname]'
      }
    }
  }
})
