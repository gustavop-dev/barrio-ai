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
        name: '0ff1ce',
        short_name: '0ff1ce',
        description: 'La oficina de 0ff1ce: el equipo de agentes de IA que trabaja tu LinkedIn, y sus avisos.',
        lang: 'es',
        dir: 'ltr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any',
        theme_color: '#fffef8',
        background_color: '#f7f6f0',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // App shell, fonts, brand and the office artwork. Nothing under /api/ is ever precached.
        globPatterns: ['**/*.{js,css,html,png,svg,woff2,json,txt}'],
        globIgnores: ['**/node_modules/**'],
      },
      devOptions: { enabled: false },
    }),
  ],
  build: {
    // `/static/` belongs to Django; the app's bundles go to `/_app/`.
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
    // Generous limits: the suite renders the whole app and runs on shared, sometimes busy machines.
    testTimeout: 20_000,
  },
});
