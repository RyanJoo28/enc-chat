import { test, expect } from '../utils/fixtures';

test.describe('F9-05/06 Security & Device Management', () => {

  test('Multi-device login: both contexts reach chat', async ({ pageA1, pageA2 }) => {
    // Both pageA1 and pageA2 are logged in as the same user (playwrightA1)
    // via separate browser contexts (simulating two devices).
    // The fixture already handles login and waits for /chat.

    // Verify both pages are on the chat view
    await pageA1.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });
    await pageA2.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });

    // Both should show the sidebar with the user's profile
    const profileA1 = pageA1.locator('.my-profile .profile-name');
    const profileA2 = pageA2.locator('.my-profile .profile-name');

    await expect(profileA1).toBeVisible();
    await expect(profileA2).toBeVisible();

    // Both should display the same username
    const nameA1 = await profileA1.textContent();
    const nameA2 = await profileA2.textContent();
    expect(nameA1).toBe(nameA2);

    console.log(`✅ Both devices logged in as: ${nameA1}`);

    // TODO: Implement actual device kick logic once the UI supports it.
    // The flow would be:
    //   1. A1 navigates to Settings > Active Sessions
    //   2. A1 clicks "Revoke" on A2's session
    //   3. Assert A2 gets disconnected (redirected to login or shown modal)
    //   4. Assert new messages sent from A1 don't appear on A2
    test.info().annotations.push({
      type: 'TODO',
      description: 'Implement actual device kick assertions once UI supports session management.'
    });
  });
});
