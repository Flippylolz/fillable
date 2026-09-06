import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  cacheDir: '/tmp/fillable-vite',
  plugins: [react()],
  server: { allowedHosts: ['gateway'], proxy: { '/api': 'http://api:8000' } },
  test: {
    globals: true,
    include: ['tests/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      reporter: ['text', 'json', 'json-summary'],
      thresholds: { lines: 90, branches: 90 },
    },
  },
});
