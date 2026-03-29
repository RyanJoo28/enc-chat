import { APIRequestContext, expect } from '@playwright/test';

// Base API helper logic (using Playwright's APIRequestContext for direct speed)
const API_URL = '';

export async function createLoadTestUser(request: APIRequestContext, prefix: string, id: number): Promise<{ username: string, token: string, user_id: number }> {
    const rx = Math.random().toString(36).substring(2, 8);
    const username = `load_${prefix}_${id}_${Date.now()}_${rx}`;
    const password = 'TestPassword123!';

    // Register
    const regRes = await request.post(`${API_URL}/api/user/register`, {
        data: { username, password }
    });
    if (regRes.status() !== 200 && regRes.status() !== 201) {
        throw new Error(`Registration failed: ${regRes.status()} ${await regRes.text()}`);
    }
    
    // Login
    const loginRes = await request.post(`${API_URL}/api/user/login`, {
        data: { username, password }
    });
    expect(loginRes.status()).toBe(200);
    const body = await loginRes.json();
    return {
        username,
        token: body.access_token,
        user_id: body.user_id,
    };
}

export async function bootstrapDevice(request: APIRequestContext, token: string, deviceName: string) {
    // A dummy device identity key for E2EE load tests
    const payload = {
        device_id: `device_${deviceName}_${Date.now()}`,
        device_name: deviceName,
        platform: 'playwright_load',
        identity_key_public: 'dummy_ik_pub',
        signing_key_public: 'dummy_spk_pub',
        registration_id: 1234,
        signed_prekey: {
            public_key: 'dummy_spk',
            signature: 'dummy_sig',
            key_id: 1
        },
        one_time_prekeys: Array.from({ length: 5 }).map((_, i) => ({
            public_key: `dummy_otpk_${i + 1}`,
            key_id: i + 1
        }))
    };

    const res = await request.post(`${API_URL}/api/e2ee/devices/bootstrap`, {
        headers: { Authorization: `Bearer ${token}` },
        data: payload
    });
    if (res.status() !== 200) {
        const errorText = await res.text();
        throw new Error(`Bootstrap failed with status ${res.status()}: ${errorText}`);
    }
    
    // Immediately refresh the token because the session is now tied to the device,
    // and the old token doesn't have the device ID inside its JWT payload, causing 401s.
    const refreshRes = await request.post(`${API_URL}/api/user/refresh`);
    if (refreshRes.status() !== 200) {
        throw new Error(`Refresh failed after bootstrap! status: ${refreshRes.status()}`);
    }
    const refreshBody = await refreshRes.json();
    const resBody = await res.json();
    return { device_id: resBody.device.device_id, new_token: refreshBody.access_token };
}

export async function createGroup(request: APIRequestContext, token: string, groupName: string) {
    const res = await request.post(`${API_URL}/api/chat/group/create`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { name: groupName, members: [] }
    });
    if (res.status() !== 200 && res.status() !== 201) {
        const errorText = await res.text();
        throw new Error(`Create group failed with status ${res.status()}: ${errorText}`);
    }
    const body = await res.json();
    return body.group_id;
}

export async function addGroupMember(request: APIRequestContext, token: string, groupId: number, userId: number) {
    const inviteRes = await request.post(`${API_URL}/api/chat/group/${groupId}/invites`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { user_id: userId }
    });
    if (inviteRes.status() !== 200) {
        throw new Error(`addGroupMember failed: ${inviteRes.status()} ${await inviteRes.text()}`);
    }
    const inviteBody = await inviteRes.json();
    console.log(`[DEBUG] addGroupMember returned:`, inviteBody);
    return inviteBody.invite_id;
}

export async function acceptGroupInvite(request: APIRequestContext, token: string, inviteId: number) {
    const res = await request.post(`${API_URL}/api/chat/group/invites/${inviteId}/accept`, {
        headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status() !== 200) {
        const text = await res.text();
        console.error(`[FATAL] acceptGroupInvite failed with ${res.status()}: ${text}`);
        throw new Error(`acceptGroupInvite Failed: ${res.status()} ${text}`);
    }
}

export async function getWsTicket(request: APIRequestContext, token: string): Promise<string> {
    const res = await request.post(`${API_URL}/api/e2ee/ws-ticket`, {
        headers: { Authorization: `Bearer ${token}` }
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    return body.ticket;
}

// Generate an array of size length, filled using the factory.
export async function createNUsers(request: APIRequestContext, count: number, prefix: string) {
    const tasks = Array.from({ length: count }).map((_, i) => createLoadTestUser(request, prefix, i));
    return Promise.all(tasks);
}
export async function makeFriends(request: APIRequestContext, userA: any, userB: any) {
    // A requests B
    const sendReq = await request.post(`${API_URL}/api/user/friends/requests`, {
        headers: { Authorization: `Bearer ${userA.token}` },
        data: { user_id: userB.user_id }
    });
    if (sendReq.status() !== 200 && sendReq.status() !== 400 && sendReq.status() !== 409) {
        throw new Error(`Friend request failed: ${sendReq.status()}`);
    }
    if (sendReq.status() === 200) {
        const body = await sendReq.json();
        // B accepts A
        const acceptReq = await request.post(`${API_URL}/api/user/friends/requests/${body.request_id}/accept`, {
            headers: { Authorization: `Bearer ${userB.token}` }
        });
        if (acceptReq.status() !== 200) {
            throw new Error(`Friend accept failed: ${acceptReq.status()}`);
        }
    }
}
