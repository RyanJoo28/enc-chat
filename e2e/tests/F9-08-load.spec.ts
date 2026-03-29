import { test, expect } from '@playwright/test';
import WebSocket from 'ws';
import { 
    createLoadTestUser, 
    bootstrapDevice, 
    createGroup, 
    addGroupMember, 
    acceptGroupInvite, 
    getWsTicket,
    makeFriends
} from '../utils/backend-api';

const API_URL = '';
const WS_URL = process.env.WS_URL || 'wss://localhost:3000';

test.describe('F9-08 Performance Load Tests', () => {
    // Tests might be slow, especially with many crypto operations
    test.setTimeout(300000); // 5 minutes

    test('prekey-bundle fetch under concurrent load', async ({ request }) => {
        // Register 1 user with 5 devices
        const admin = await createLoadTestUser(request, 'prekey_admin', 1);
        
        // Users must login again to instantiate a unique session for each new device
        for (let i = 0; i < 5; i++) {
            const loginRes = await request.post(`${API_URL}/api/user/login`, {
                data: { username: admin.username, password: 'TestPassword123!' }
            });
            const body = await loginRes.json();
            const newTokenObj = await bootstrapDevice(request, body.access_token, `device_${i}`);
            // The last device becomes the active admin token for fetching
            if (i === 4) admin.token = newTokenObj.new_token;
        }

        // Register 50 clients that want to fetch the prekey simultaneously
        const clients = [];
        for (let i = 0; i < 50; i++) {
            const client = await createLoadTestUser(request, 'prekey_client', i);
            const bootRes = await bootstrapDevice(request, client.token, 'client_dev');
            client.token = bootRes.new_token;
            clients.push(client);
        }

        // 50 concurrent fetch operations (fetching own prekey bundle to avoid friendship checks)
        // Let's actually test fetching the ADMIN's prekey bundle, so we make them friends first
        await Promise.all(clients.map(c => makeFriends(request, admin, c)));
        const start = performance.now();
        const promises = clients.map(client => request.get(`${API_URL}/api/e2ee/users/${admin.user_id}/prekey-bundle`, {
            headers: { Authorization: `Bearer ${client.token}` },
            params: { peek: true }
        }));
        const responses = await Promise.all(promises);
        const end = performance.now();

        // Ensure all succeeded and calculate latency
        for (const res of responses) {
            expect(res.status()).toBe(200);
        }
        
        const latency = end - start;
        console.log(`[prekey-bundle] 50 concurrent fetches latency: ${latency.toFixed(2)} ms`);
        expect(latency).toBeLessThan(5000); // Wait time shouldn't be crazy
    });

    test('group fanout broadcast latency (50 members)', async ({ request }) => {
        const GROUP_SIZE = 50;
        
        // 1. Setup 1 Admin and (GROUP_SIZE) Members
        const admin = await createLoadTestUser(request, 'fanout_admin', 1);
        const adminBoot = await bootstrapDevice(request, admin.token, 'admin_dev');
        admin.token = adminBoot.new_token;
        
        const groupId = await createGroup(request, admin.token, 'Load Test Group');
        console.log(`[fanout] Group created (ID: ${groupId}). Bootstrapping ${GROUP_SIZE} users (sequential bounds)...`);

        const members: any[] = [];
        const prefix = `fanout_${Date.now()}`;
        for (let i = 0; i < GROUP_SIZE; i++) {
            const member = await createLoadTestUser(request, prefix, i);
            const memberBoot = await bootstrapDevice(request, member.token, 'member_dev');
            member.token = memberBoot.new_token;
            (member as any).device_id = memberBoot.device_id;
            await makeFriends(request, admin, member);
            
            // Invite & Accept
            const inviteId = await addGroupMember(request, admin.token, groupId, member.user_id);
            await acceptGroupInvite(request, member.token, inviteId);
            
            members.push(member);
        }

        // 2. Connect 50 Websockets
        console.log(`[fanout] Connecting ${GROUP_SIZE} websockets...`);
        const sockets: WebSocket[] = [];
        
        await Promise.all(members.map(async (member) => {
            const ticket = await getWsTicket(request, member.token);
            return new Promise<void>((resolve, reject) => {
                const ws = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${ticket}`, { 
                    rejectUnauthorized: false,
                    headers: { 'Origin': 'https://localhost:3000' }
                });
                ws.on('open', () => {
                    sockets.push(ws);
                    resolve();
                });
                ws.on('error', reject);
            });
        }));

        // 3. Admin sends a giant group message
        const adminTicket = await getWsTicket(request, admin.token);
        const adminWs = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${adminTicket}`, { 
            rejectUnauthorized: false,
            headers: { 'Origin': 'https://localhost:3000' }
        });
        
        await new Promise<void>((resolve) => adminWs.on('open', resolve));
        adminWs.on('message', (d) => console.log(`[adminWs] ${d.toString()}`));
        adminWs.on('error', (e) => console.error(`[adminWs Error]`, e));

        // Let members listen for "message.new"
        let receivedCount = 0;
        const start = performance.now();

        const waitAllReceived = new Promise<number>((resolve) => {
            sockets.forEach(ws => {
                ws.on('message', (data: string) => {
                    const payload = JSON.parse(data.toString());
                    if (payload.type === 'message.new' && payload.group_id === groupId) {
                        receivedCount++;
                        if (receivedCount === GROUP_SIZE) {
                            resolve(performance.now());
                        }
                    }
                });
            });
        });

        // 4. Dispatch the huge payload (e.g. 100kb payload envelope)
        console.log(`[fanout] Sending broadcast...`);
        const dummyEnvelope = "DUMMY_ENVELOPE_DATA_".repeat(50);
        
        // We need 'packets' specifically scoped to each member
        const packets = members.map(m => ({
            recipient_user_id: m.user_id,
            recipient_device_id: m.device_id,
            envelope_type: 'group_sender_key',
            envelope: dummyEnvelope
        }));

        adminWs.send(JSON.stringify({
            type: 'message.send',
            chat_type: 'group',
            to: groupId,
            group_epoch: GROUP_SIZE + 1, // Epoch increments per member added
            client_message_id: 'load_test_msg_x',
            msg_type: 'text',
            packets: packets
        }));

        const end = await waitAllReceived;
        const latency = end - start;
        console.log(`[fanout] 50 members received broadcast in ${latency.toFixed(2)} ms`);

        // Cleanup
        adminWs.close();
        sockets.forEach(ws => ws.close());

        expect(latency).toBeLessThan(10000); // We tolerate up to 10 seconds for 50 users sending full envelopes
    });

    test('attachment upload 5MB blob throughput', async ({ request }) => {
        const admin = await createLoadTestUser(request, 'upload_admin', 1);
        const adminBoot = await bootstrapDevice(request, admin.token, 'admin_dev');
        admin.token = adminBoot.new_token;

        const SIZE_5MB = 5 * 1024 * 1024;
        const blobData = Buffer.alloc(SIZE_5MB, 'x'); // 5MB payload
        const crypto = require('crypto');
        const hash = crypto.createHash('sha256').update(blobData).digest('hex');

        console.log('[attachment] Starting 5MB upload initialization...');
        const initStart = performance.now();
        const initRes = await request.post(`${API_URL}/api/e2ee/attachments/init`, {
            headers: { Authorization: `Bearer ${admin.token}` },
            data: {
                mime_type: 'image/jpeg',
                ciphertext_size: SIZE_5MB,
                ciphertext_sha256: hash
            }
        });
        const initTime = performance.now() - initStart;
        expect(initRes.status()).toBe(200);
        const { blob_id } = await initRes.json();
        console.log(`[attachment] Init took: ${initTime.toFixed(2)} ms, Blob ID: ${blob_id}`);

        // The endpoint uses streams/put
        console.log('[attachment] Uploading byte stream...');
        const uploadStart = performance.now();
        const uploadRes = await request.put(`${API_URL}/api/e2ee/attachments/${blob_id}`, {
            headers: { 
                Authorization: `Bearer ${admin.token}`,
                'Content-Type': 'application/octet-stream'
            },
            data: blobData
        });
        const uploadTime = performance.now() - uploadStart;
        expect(uploadRes.status()).toBe(200);
        console.log(`[attachment] Uploading 5MB took: ${uploadTime.toFixed(2)} ms`);
        
        console.log('[attachment] Marking complete...');
        const completeStart = performance.now();
        const completeRes = await request.post(`${API_URL}/api/e2ee/attachments/${blob_id}/complete`, {
            headers: { Authorization: `Bearer ${admin.token}` },
            data: { ciphertext_sha256: hash }
        });
        const completeTime = performance.now() - completeStart;
        expect(completeRes.status()).toBe(200);
        console.log(`[attachment] Complete took: ${completeTime.toFixed(2)} ms`);

        // Ensure total time is acceptable
        expect(uploadTime).toBeLessThan(20000); 
    });

    test('offline inbox retrieval throughput (200 messages)', async ({ request }) => {
        // 1. Register Receiver and bootstrap 1 device
        const receiver = await createLoadTestUser(request, 'inbox_receiver', 1);
        const receiverBoot = await bootstrapDevice(request, receiver.token, 'receiver_dev');
        receiver.token = receiverBoot.new_token;
        const receiverDevice = receiverBoot.device_id;

        // 2. Register Sender and bootstrap
        const sender = await createLoadTestUser(request, 'inbox_sender', 1);
        const senderBoot = await bootstrapDevice(request, sender.token, 'sender_dev');
        sender.token = senderBoot.new_token;

        await makeFriends(request, sender, receiver);

        // 3. Connect Sender WS
        const senderTicket = await getWsTicket(request, sender.token);
        const senderWs = new WebSocket(`${WS_URL}/api/e2ee/ws?ticket=${senderTicket}`, { 
            rejectUnauthorized: false,
            headers: { 'Origin': 'https://localhost:3000' }
        });
        await new Promise<void>((resolve) => senderWs.on('open', resolve));

        console.log('[inbox] Sending 200 offline messages via WebSocket...');
        // 4. Send 200 messages
        const MSG_COUNT = 200;
        for (let i = 0; i < MSG_COUNT; i++) {
            senderWs.send(JSON.stringify({
                type: 'message.send',
                chat_type: 'private',
                to: receiver.user_id,
                client_message_id: `inbox_load_${i}`,
                msg_type: 'text',
                packets: [{
                    recipient_user_id: receiver.user_id,
                    recipient_device_id: receiverDevice,
                    envelope_type: 'signal',
                    envelope: `DUMMY_ENVELOPE_INBOX_${i}`
                }]
            }));
        }

        // Delay briefly to allow backend to persist all 200 MySQL transactions
        await new Promise(r => setTimeout(r, 2000));
        senderWs.close();

        // 5. Receiver fetches inbox
        console.log('[inbox] Fetching inbox of 200 messages...');
        const fetchStart = performance.now();
        const res = await request.get(`${API_URL}/api/e2ee/inbox`, {
            headers: { Authorization: `Bearer ${receiver.token}` }
        });
        const fetchEnd = performance.now();
        
        expect(res.status()).toBe(200);
        const inboxData = await res.json();
        
        const latency = fetchEnd - fetchStart;
        console.log(`[inbox] Fetched ${inboxData.length} records in ${latency.toFixed(2)} ms`);
        
        // Assertions
        expect(inboxData.length).toBeGreaterThanOrEqual(MSG_COUNT);
        expect(latency).toBeLessThan(3000); // fetching 200 rows with joins should be < 3 seconds
    });
});
