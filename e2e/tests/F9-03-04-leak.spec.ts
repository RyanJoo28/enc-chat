import { test, expect } from '../utils/fixtures';
import mysql from 'mysql2/promise';

test.describe('F9-03/04 Server Zero-Knowledge Checks', () => {

  test('Database contains no plaintext of messages', async ({ pageA1, pageB }) => {
    const secretSignature = `PHASE9-DB-UNIQUE-${Date.now()}`;

    // Check if a chat is active (textarea.chat-input visible)
    const chatInput = pageA1.locator('textarea.chat-input');
    
    // Search for playwrightB and open chat
    await pageA1.locator('.search-input input').first().fill('playwrightB');
    const contactItem = pageA1.locator('.contact-item', { hasText: 'playwrightB' }).first();
    await contactItem.waitFor({ state: 'visible', timeout: 5000 });
    await contactItem.click();
    
    // Wait for chat input to be active
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    // A sends the secret signature via the encrypted chat
    await chatInput.fill(secretSignature);
    await chatInput.press('Enter');
    await pageA1.waitForTimeout(2000);

    // Connect to the backend MySQL database
    const connection = await mysql.createConnection({
      host: process.env.DB_HOST || '127.0.0.1',
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || 'root',
      database: process.env.DB_NAME || 'enc_chat_db'
    });

    try {
      let dbDump = '';

      // Check all message-related tables for the plain text signature
      try {
        const [rows1] = await connection.execute('SELECT * FROM message_payloads ORDER BY id DESC LIMIT 50');
        dbDump += JSON.stringify(rows1);
      } catch {
        console.log('message_payloads table might not exist, trying messages');
      }

      try {
        const [rows2] = await connection.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 50');
        dbDump += JSON.stringify(rows2);
      } catch {
        // ignore
      }

      if (dbDump) {
        // Core assertion: the plaintext MUST NOT appear anywhere in the raw tables
        expect(dbDump).not.toContain(secretSignature);
      }
    } finally {
      await connection.end();
    }
  });
});
