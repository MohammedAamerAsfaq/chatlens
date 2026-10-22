import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // Production build is served by Django under STATIC_URL + 'frontend/' (see
  // core/settings.py STATIC_URL and apps/chatlens_core/views.py _load_frontend_bundle),
  // not from site root. Without this, Vite bakes root-relative asset URLs
  // (e.g. "/assets/chatlens-icon-<hash>.png") into the built JS, which the SPA
  // catch-all route (core/urls.py) then serves index.html for instead of 404ing —
  // browser gets HTML where it expected an image, so it renders as broken.
  // Dev server (`npm run dev`) must stay at '/' since it's proxied directly, not via Django static.
  // Checked via NODE_ENV (not the defineConfig callback form) so vitest.config.ts's
  // mergeConfig(viteConfig, ...) keeps working — it requires a plain object, not a function.
  base: process.env.NODE_ENV === 'production' ? '/static/frontend/' : '/',
  plugins: [vue(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/worker-media': {
        target: 'http://localhost:3001',
        changeOrigin: false,
        rewrite: (p) => p.replace(/^\/worker-media/, '/media'),
      },
    },
  },
  build: {
    outDir: '../static/frontend',
    assetsDir: 'assets',
    manifest: 'manifest.json',
    emptyOutDir: true,
  },
})
