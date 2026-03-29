import { test, expect } from '@playwright/test';
import { createLoadTestUser, bootstrapDevice, makeFriends, getWsTicket } from '../utils/backend-api';
import { WebSocket } from 'ws';

const API_URL = process.env.API_URL || 'https://localhost:8000';
const WS_URL = process.env.WS_URL || 'wss://localhost:8000';

test.describe('F9-09 Message Recall', () => {

    test('can recall a private message and notify both parties', async ({ request }) => {
        // Setup Users
        const prefix = `recall_${Date.now()}`;
        const uA = await createLoadTestUser(request, prefix + '_A', 1);
        const bootA = await bootstrapDevice(request, uA.token, 'dev_A');
        uA.token = bootA.new_token;
        (uA as any).device_id = bootA.device_id;

        const uB = await createLoadTestUser(request, prefix + '_B', 1);
        const bootB = await bootstrapDevice(request, uB.token, 'dev_B');
        uB.token = bootB.new_token;
        (uB as any).device_id = bootB.device_id;

        await makeFriends(request, uA, uB);

        // Connect Ws
        const ticketA = await getWsTicket(request, uA.token);
        const ticketB = await getWsTicket(request, uB.token);

        const wsA = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${ticketA}`, { rejectUnauthorized: false, headers: { 'Origin': 'https://localhost:3000' } });
        const wsA_open = new Promise<void>((resolve, reject) => { wsA.on('open', resolve); wsA.on('error', reject); wsA.on('close', reject); });

        const wsB = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${ticketB}`, { rejectUnauthorized: false, headers: { 'Origin': 'https://localhost:3000' } });
        const wsB_open = new Promise<void>((resolve, reject) => { wsB.on('open', resolve); wsB.on('error', reject); wsB.on('close', reject); });

        await Promise.all([wsA_open, wsB_open]);

        console.log(`[F9-09] WS connected for A and B. A sending message...`);

        // A sends Message to B
        let targetMessageId: number | null = null;
        let bReceivedMsg = new Promise<void>((resolve, reject) => {
            wsB.on('message', (data: string) => {
                const payload = JSON.parse(data.toString());
                if (payload.type === 'message.new' && payload.chat_type === 'private') {
                    // Extract DB message ID to recall it
                    targetMessageId = payload.message.id;
                    resolve();
                }
            });
            wsB.on('error', reject);
        });

        wsA.on('error', (e) => console.error(`[wsA err]`, e));

        const A_Payload = {
            type: 'message.send',
            chat_type: 'private',
            to: uB.user_id,
            client_message_id: 'recall_test_msg_x',
            msg_type: 'text',
            packets: [{
                recipient_user_id: uB.user_id,
                recipient_device_id: (uB as any).device_id,
                envelope_type: 'message',
                envelope: 'DUMMY_ENVELOPE'
            }, {
                recipient_user_id: uA.user_id,
                recipient_device_id: (uA as any).device_id,
                envelope_type: 'message',
                envelope: 'DUMMY_ENVELOPE'
            }]
        };
        wsA.send(JSON.stringify(A_Payload));

        await bReceivedMsg;
        expect(targetMessageId).not.toBeNull();

        console.log(`[F9-09] Message ${targetMessageId} received. Requesting recall...`);

        // Wait for both WS to receive the `message.recalled` event
        let aRecallEvent = new Promise<void>(resolve => {
            wsA.on('message', (d: string) => {
                const payload = JSON.parse(d.toString());
                if (payload.type === 'message.recalled' && payload.message.id === targetMessageId) resolve();
            });
        });

        let bRecallEvent = new Promise<void>(resolve => {
            wsB.on('message', (d: string) => {
                const payload = JSON.parse(d.toString());
                if (payload.type === 'message.recalled' && payload.message.id === targetMessageId) resolve();
            });
        });

        // A recalls the message
        const recallRes = await request.post(`${API_URL}/api/e2ee/messages/${targetMessageId}/recall`, {
            headers: { Authorization: `Bearer ${uA.token}` }
        });
        if (recallRes.status() !== 200) {
            console.error(`Recall failed: ${recallRes.status()} ${await recallRes.text()}`);
        }
        expect(recallRes.status()).toBe(200);

        await Promise.all([aRecallEvent, bRecallEvent]);
        console.log(`[F9-09] Recall broadcast verified!`);

        wsA.close();
        wsB.close();
    });
});
