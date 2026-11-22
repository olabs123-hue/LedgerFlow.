import {defineConfig, devices} from '@playwright/test';

export default defineConfig({
  testDir: './interactive-tests',
  timeout: 40_000,
  retries: 1,
  reporter: 'line',
  use: {
    baseURL: 'https://localhost:8443',
    ignoreHTTPSErrors: true, // CI-only self-signed local HTTPS certificate
    trace: 'retain-on-failure',
  },
  projects: [
    {name:'desktop-cookie-demo', use:{...devices['Desktop Chrome']}},
  ],
});
