import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// VITE_BASE lets us deploy under a sub-path (e.g. GitHub Pages: /Hackaton-NASA/).
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: { port: 5173 },
  // three.js (~500 kB) lives in its own lazily-loaded chunk (3D pages only), so the warning is expected.
  build: { chunkSizeWarningLimit: 600 },
  test: { environment: 'node' },
});
