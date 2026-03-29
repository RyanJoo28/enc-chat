import { test, expect } from '../utils/fixtures';

test.describe('F9-02 Chat Workflows', () => {

  test('Offline send and reconnect receive with decryption', async ({ pageA1, pageB }) => {
    pageA1.on('console', msg => console.log('A1:', msg.text()));
    pageA1.on('pageerror', error => console.error('A1 Error:', error.message));
    pageB.on('console', msg => console.log('B:', msg.text()));
    pageB.on('pageerror', error => console.error('B Error:', error.message));

    const uniqueMarker = `PHASE9-PRIVATE-${Date.now()}`;

    // Both pages should be on /chat after fixture login.
    // The top-level container is div.telegram-layout
    await pageA1.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });
    await pageB.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });

    // Give SPA enough time to complete E2EE bootstrapping/socket connection
    await pageB.waitForTimeout(3000);

    // 1. Force B offline. This keeps IndexedDB intact but disconnects WebSockets/fetch
    await pageB.context().setOffline(true);

    // 2. The chat input is a <textarea class="chat-input">
    //    Ensure A has a conversation with B open.
    const chatInput = pageA1.locator('textarea.chat-input');
    
    // Search for playwrightB and open chat
    await pageA1.locator('.search-input input').first().fill('playwrightB');
    const contactItem = pageA1.locator('.contact-item', { hasText: 'playwrightB' }).first();
    await contactItem.waitFor({ state: 'visible', timeout: 5000 });
    await contactItem.click();
    
    // Wait for chat input to be active
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    await chatInput.fill(uniqueMarker);
    await chatInput.press('Enter');

    // Ensure A's UI shows the message
    await expect(pageA1.locator('.message-bubble').last()).toContainText(uniqueMarker, { timeout: 5000 });
    
    // Give A1's E2EE outgoing queue enough time to encrypt and send off the envelope
    await pageA1.waitForTimeout(2000);

    // 3. Restore B's network. Reloading simulates opening the app after being offline
    await pageB.context().setOffline(false);
    await pageB.reload();
    await pageB.waitForSelector('.telegram-layout', { state: 'visible', timeout: 10_000 });

    // B opens the chat with A1 from the sidebar (which is now populated with the new conversation)
    const contactItemB = pageB.locator('.contact-list .contact-item', { hasText: 'playwrightA1' }).first();
    await contactItemB.waitFor({ state: 'visible', timeout: 5000 });
    await contactItemB.click();
    await expect(pageB.locator('textarea.chat-input')).toBeVisible({ timeout: 5000 });

    // Wait for the message to appear in B's view
    await expect(pageB.locator('.message-bubble').last()).toContainText(uniqueMarker, { timeout: 10000 });
  });

  test('WebSocket traffic does not contain plain text payload', async ({ pageA1 }) => {
    let plainTextFound = false;

    pageA1.on('websocket', ws => {
      ws.on('framesent', data => {
        const payload = data.payload.toString();
        if (payload.includes('PHASE9-WS-CHECK')) {
          plainTextFound = true;
        }
      });
    });

    const chatInput = pageA1.locator('textarea.chat-input');
    
    // Ensure chat is open
    await pageA1.locator('.search-input input').first().fill('playwrightB');
    const contactItem = pageA1.locator('.contact-item', { hasText: 'playwrightB' }).first();
    await contactItem.waitFor({ state: 'visible', timeout: 5000 });
    await contactItem.click();
    
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    await chatInput.fill('PHASE9-WS-CHECK');
    await chatInput.press('Enter');
    await pageA1.waitForTimeout(1000);

    expect(plainTextFound).toBe(false);
  });
});
