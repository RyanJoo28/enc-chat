import { test, expect } from '@playwright/test';
import { createLoadTestUser, bootstrapDevice, getWsTicket } from '../utils/backend-api';
import { WebSocket } from 'ws';

const API_URL = process.env.API_URL || 'https://localhost:8000';
const WS_URL = process.env.WS_URL || 'wss://localhost:8000';

test.describe('F9-09 Device Revocation', () => {

    test('can revoke secondary device and force websocket disconnect', async ({ request }) => {
        const prefix = `revoke_${Date.now()}`;
        // 1. Create a user (Logs in automatically)
        const u = await createLoadTestUser(request, prefix, 1);
        
        // 2. Bootstrap Device 1 (representing phone)
        const boot1 = await bootstrapDevice(request, u.token, 'phone_device');
        const token1 = boot1.new_token;
        const deviceId1 = boot1.device_id;

        // 3. Login again to get a new session for Device 2
        const loginRes = await request.post(`${API_URL}/api/user/login`, {
            data: { username: u.username, password: 'TestPassword123!' }
        });
        const loginBody = await loginRes.json();
        const rawToken2 = loginBody.access_token;
        
        // 4. Bootstrap Device 2 (representing pc)
        const boot2 = await bootstrapDevice(request, rawToken2, 'pc_device');
        const token2 = boot2.new_token;
        const deviceId2 = boot2.device_id;

        // 5. Connect WebSocket using Device 2's token
        console.log(`[F9-09] Connecting Device 2 Websocket...`);
        const ticket2 = await getWsTicket(request, token2);
        const ws2 = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${ticket2}`, { rejectUnauthorized: false, headers: { 'Origin': 'https://localhost:3000' } });
        
        await new Promise<void>(resolve => ws2.on('open', resolve));
        
        // Listen for close event
        let closedCode: number | null = null;
        let closedReason: string = '';
        const wsClosedPromise = new Promise<void>(resolve => {
            ws2.on('close', (code, reason) => {
                closedCode = code;
                closedReason = reason.toString();
                resolve();
            });
        });

        // 6. Device 1 revokes Device 2
        console.log(`[F9-09] Device 1 revoking Device 2 (${deviceId2})...`);
        const revokeRes = await request.post(`${API_URL}/api/e2ee/devices/${deviceId2}/revoke`, {
            headers: { Authorization: `Bearer ${token1}` }
        });
        expect(revokeRes.status()).toBe(200);

        // 7. Assert Device 2 gets disconnected with code 4001
        await wsClosedPromise;
        console.log(`[F9-09] Device 2 disconnected: code ${closedCode}, reason "${closedReason}"`);
        expect(closedCode).toBe(4001);
        expect(closedReason).toContain('device_revoked');
    });
});
