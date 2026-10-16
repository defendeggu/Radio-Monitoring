import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

// During `npm run dev` the API is proxied like nginx does in production.
// Set API_TARGET to your API (e.g. a running stack: http://localhost:8080/api).
const apiTarget = process.env.API_TARGET ?? 'http://localhost:8080/api';

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
});
