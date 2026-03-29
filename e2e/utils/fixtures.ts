import { test as base, Page } from '@playwright/test';

export type E2EFixtures = {
  pageA1: Page;
  pageA2: Page;
  pageB: Page;
  pageC: Page;
};

/**
 * Log in via the browser UI with automatic rate-limit retry.
 *
 * The backend rate-limits POST /api/user/login to 5 requests/minute.
 * When running all tests sequentially, we exceed this limit.
 * This helper detects login failure (page doesn't redirect to /chat)
 * and waits for the rate window to reset before retrying.
 */
async function setupUserContext(browser: any, username: string): Promise<Page> {
  const MAX_ATTEMPTS = 3;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    const page = await context.newPage();

    try {
      // Navigate to login page (route '/')
      await page.goto('/', { waitUntil: 'networkidle' });

      // Wait for Element Plus to render the login form
      await page.waitForSelector('.tg-input', { state: 'visible', timeout: 10_000 });

      // Fill username and password
      await page.locator('.tg-input input.el-input__inner').first().fill(username);
      await page.locator('.tg-input input[type="password"]').first().fill('Test1234!');

      // Click login button
      await page.click('button.tg-btn');

      // Wait for redirect to /chat (Login.vue uses window.location.replace)
      await page.waitForURL('**/chat', { timeout: 10_000 });

      // Wait for the chat layout to be fully rendered
      await page.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });

      return page; // ✅ Success
    } catch (err) {
      await context.close();

      if (attempt < MAX_ATTEMPTS) {
        const waitSec = 30 * attempt; // 30s, 60s
        console.log(
          `⏳ [${username}] Login attempt ${attempt}/${MAX_ATTEMPTS} failed. ` +
          `Waiting ${waitSec}s for rate limit reset...`
        );
        await new Promise(r => setTimeout(r, waitSec * 1000));
      } else {
        throw new Error(
          `❌ [${username}] Login failed after ${MAX_ATTEMPTS} attempts. ` +
          `Last error: ${(err as Error).message}`
        );
      }
    }
  }

  throw new Error('Unreachable');
}

export const test = base.extend<E2EFixtures>({
  pageA1: async ({ browser }, use) => {
    const page = await setupUserContext(browser, 'playwrightA1');
    await use(page);
    await page.context().close();
  },
  pageA2: async ({ browser }, use) => {
    const page = await setupUserContext(browser, 'playwrightA1');
    await use(page);
    await page.context().close();
  },
  pageB: async ({ browser }, use) => {
    const page = await setupUserContext(browser, 'playwrightB');
    await use(page);
    await page.context().close();
  },
  pageC: async ({ browser }, use) => {
    const page = await setupUserContext(browser, 'playwrightC');
    await use(page);
    await page.context().close();
  }
});

export { expect } from '@playwright/test';
