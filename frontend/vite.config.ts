import { readFileSync } from 'node:fs';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

// During `npm run dev` the API is proxied like nginx does in production.
// Set API_TARGET to your API (e.g. a running stack: http://localhost:8080/api).
const apiTarget = process.env.API_TARGET ?? 'http://localhost:8080/api';

// Version shown in the sidebar (package.json is kept in step by scripts/version.py)
const version = (
  JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string }
).version;

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  define: { __APP_VERSION__: JSON.stringify(version) },
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
