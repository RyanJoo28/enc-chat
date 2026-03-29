import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// Load database credentials from the backend .env
dotenv.config({ path: path.resolve(__dirname, '../backend/.env') });

/**
 * The frontend Vite server uses HTTPS when certs exist at ../certs/.
 * Since the certs directory is present in this project, the dev server
 * listens on https://localhost:3000.
 */
const FRONTEND_URL = 'https://localhost:3000';

export default defineConfig({
  /* Register test accounts (playwrightA1, playwrightB, playwrightC) before tests */
  globalSetup: require.resolve('./global-setup'),

  testDir: './tests',

  /* Each test file runs serially inside, but different files can run in parallel */
  fullyParallel: false,

  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : 1,
  reporter: 'html',

  /* Generous timeout: fixtures may wait up to 60s for rate-limit reset */
  timeout: 120_000,

  use: {
    baseURL: FRONTEND_URL,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    /* Accept the self-signed TLS certificate used by the Vite dev server */
    ignoreHTTPSErrors: true,
    /* Slow down actions slightly for reliability in local testing */
    actionTimeout: 15_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /**
   * Automatically start the frontend dev server before tests begin.
   * Playwright will wait until FRONTEND_URL responds before running any test.
   * This removes the need to manually run `npm run dev` in a separate terminal.
   */
  webServer: {
    command: 'npm run dev',
    cwd: path.resolve(__dirname, '../frontend'),
    url: FRONTEND_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    /* The Vite dev server uses a self-signed cert; ignore the TLS error when probing */
    ignoreHTTPSErrors: true,
  },
});
