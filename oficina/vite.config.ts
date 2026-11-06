import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { defineConfig } from 'vitest/config';

// Django runs on 8787 in development. The host header is kept (changeOrigin
// false) so Django's CSRF origin check sees the same origin as the browser.
const BACKEND = 'http://127.0.0.1:8787';
const proxy = {
  '/api': { target: BACKEND, changeOrigin: false },
  '/admin': { target: BACKEND, changeOrigin: false },
  '/static': { target: BACKEND, changeOrigin: false },
  '/health': { target: BACKEND, changeOrigin: false },
};

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      injectRegister: false,
      // Icons are already matched by globPatterns; avoid duplicate precache entries.
      includeManifestIcons: false,
      manifest: {
        id: '/',
        name: 'Barrio AI',
        short_name: 'Barrio',
        description: 'La oficina de Barrio AI: supervisa la máquina autónoma y recibe sus alertas.',
        lang: 'es',
        dir: 'ltr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any',
        theme_color: '#263c33',
        background_color: '#f7f6f0',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // App shell and the office artwork. Nothing under /api/ is ever precached.
        globPatterns: ['**/*.{js,css,html,png,json,txt}'],
        globIgnores: ['**/node_modules/**'],
      },
      devOptions: { enabled: false },
    }),
  ],
  build: {
    // `/assets/` holds the LimeZu sprites and `/static/` belongs to Django.
    assetsDir: '_app',
    sourcemap: false,
  },
  server: { proxy },
  preview: { proxy },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
    unstubGlobals: true,
  },
});
