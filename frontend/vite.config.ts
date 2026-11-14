import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// VITE_BASE lets us deploy under a sub-path (e.g. GitHub Pages: /Hackaton-NASA/).
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    port: 5173,
    // Remote previews (cloud sessions, Codespaces, phones on the LAN) reach the dev server with a
    // non-localhost Host header, which Vite blocks by default. Opt in with VITE_ALLOW_ALL_HOSTS=1.
    ...(process.env.VITE_ALLOW_ALL_HOSTS === '1' ? { host: true, allowedHosts: true as const } : {}),
  },
  // three.js (~500 kB) lives in its own lazily-loaded chunk (3D pages only), so the warning is expected.
  build: { chunkSizeWarningLimit: 600 },
  test: { environment: 'node' },
});
