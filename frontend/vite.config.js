// Vite config. In development, /api and /media are forwarded to Django on :8000,
// so the React app and the API feel like one website.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
      '/sitemap.xml': 'http://127.0.0.1:8000',
      '/robots.txt': 'http://127.0.0.1:8000',
    },
  },
  build: {
    target: 'es2019',
    cssCodeSplit: true,
    // The 3D viewer (three.js) is ~1 MB but lives in its own lazy chunk, downloaded only when a model is shown.
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Split big libraries into their own cached files.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
        },
      },
    },
  },
});
