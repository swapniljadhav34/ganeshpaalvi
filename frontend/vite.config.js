// Vite config. In development the website runs here (:5173); /api and /media are forwarded to Django (:8000).
// Studio and the Designer run on Django (:8000), so opening them here redirects there.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const DJANGO = process.env.DJANGO_URL || 'http://127.0.0.1:8000';
const ADMIN = `/${(process.env.ADMIN_URL || 'admin').replace(/^\/+|\/+$/g, '')}`;
const STAFF_PATHS = ['/studio', ADMIN, '/static'];

const staffOnDjango = {
  name: 'staff-on-django',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const path = (req.url || '').split('?')[0];
      if (STAFF_PATHS.some((p) => path === p || path.startsWith(`${p}/`))) {
        res.statusCode = 302;
        res.setHeader('Location', DJANGO + req.url);
        res.end();
        return;
      }
      next();
    });
  },
};

export default defineConfig({
  plugins: [react(), staffOnDjango],
  server: {
    port: 5173,
    proxy: {
      '/api': DJANGO,
      '/media': DJANGO,
      '/sitemap.xml': DJANGO,
      '/robots.txt': DJANGO,
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
