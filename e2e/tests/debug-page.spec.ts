/**
 * Diagnostic script — run with: npx playwright test tests/debug-page.spec.ts
 *
 * Navigates to /login and dumps:
 *   1. Console messages / errors
 *   2. Page HTML
 *   3. Screenshot
 */
import { test, expect } from '@playwright/test';

test('Diagnose login page rendering', async ({ browser }) => {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();

  // Collect all console messages
  const consoleLogs: string[] = [];
  page.on('console', msg => {
    consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  });

  // Collect page errors (uncaught exceptions)
  const pageErrors: string[] = [];
  page.on('pageerror', err => {
    pageErrors.push(err.message);
  });

  // Navigate
  await page.goto('https://localhost:3000/', {
    waitUntil: 'networkidle',
    timeout: 15000,
  });

  // Wait a bit for Vue to mount
  await page.waitForTimeout(3000);

  // Dump page title
  const title = await page.title();
  console.log('=== PAGE TITLE ===');
  console.log(title);

  // Dump page URL
  console.log('\n=== PAGE URL ===');
  console.log(page.url());

  // Dump inner HTML of body
  const bodyHTML = await page.evaluate(() => document.body.innerHTML);
  console.log('\n=== BODY HTML (first 2000 chars) ===');
  console.log(bodyHTML.substring(0, 2000));

  // Dump console logs
  console.log('\n=== CONSOLE LOGS ===');
  for (const log of consoleLogs) {
    console.log(log);
  }

  // Dump page errors
  console.log('\n=== PAGE ERRORS (uncaught) ===');
  for (const err of pageErrors) {
    console.log(err);
  }

  // Take a screenshot for visual inspection
  await page.screenshot({ path: 'debug-login.png', fullPage: true });
  console.log('\n=== Screenshot saved to e2e/debug-login.png ===');

  // Check if any input elements exist at all
  const inputCount = await page.locator('input').count();
  console.log(`\n=== Input elements on page: ${inputCount} ===`);

  // Check if .tg-input exists
  const tgInputCount = await page.locator('.tg-input').count();
  console.log(`=== .tg-input elements: ${tgInputCount} ===`);

  // Check if el-input__inner exists
  const elInputCount = await page.locator('.el-input__inner').count();
  console.log(`=== .el-input__inner elements: ${elInputCount} ===`);

  // Check #app mount point
  const appHTML = await page.evaluate(() => {
    const app = document.getElementById('app');
    return app ? app.innerHTML.substring(0, 500) : '(#app not found)';
  });
  console.log(`\n=== #app content (first 500 chars) ===`);
  console.log(appHTML);

  await context.close();
});
