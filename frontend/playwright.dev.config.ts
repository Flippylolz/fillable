import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e-dev',
  outputDir: '/tmp/fillable-dev-results/run',
  reporter: 'list',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  use: { baseURL: 'http://gateway:8080', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
});
