import { request } from '@playwright/test';

/**
 * Playwright Global Setup — runs ONCE before all test files.
 *
 * 1. Registers test accounts.
 * 2. If accounts are newly created, immediately sets up a friend relationship
 *    between playwrightA1 and playwrightB so tests can start messaging directly.
 */

const TEST_ACCOUNTS = [
  { username: 'playwrightA1', password: 'Test1234!' },
  { username: 'playwrightB',  password: 'Test1234!' },
  { username: 'playwrightC',  password: 'Test1234!' },
];

const FRONTEND_URL = 'https://localhost:3000';

async function globalSetup() {
  const apiContext = await request.newContext({
    baseURL: FRONTEND_URL,
    ignoreHTTPSErrors: true,
  });

  let needFriendSetup = false;

  console.log('\n🔧 [global-setup] Phase 1: Registering test accounts...');
  for (const account of TEST_ACCOUNTS) {
    try {
      const response = await apiContext.post('/api/user/register', {
        data: { username: account.username, password: account.password },
      });
      if (response.ok()) {
        const body = await response.json();
        console.log(`  ✅ Registered: ${account.username} (ID: ${body.user_id})`);
        needFriendSetup = true; // At least one new account exists
      } else {
        const body = await response.json().catch(() => ({}));
        if (response.status() === 400) {
          console.log(`  ⏭️  Already exists: ${account.username}`);
        } else {
          console.warn(`  ⚠️  ${response.status()} for ${account.username}: ${body.detail || ''}`);
        }
      }
    } catch (err) {
      console.error(`  ❌ Register failed for ${account.username}:`, (err as Error).message);
    }
  }

  // Phase 2: Setup friendship API calls unconditionally
  // If they are already friends, the API will return 400 and we ignore it.
  console.log('\n🔧 [global-setup] Phase 2: Setting up initial friendships (A1 <-> B)...');
  try {
    // Login B to get B's user_id and token
    const loginB = await apiContext.post('/api/user/login', {
      data: { username: 'playwrightB', password: 'Test1234!' }
    });
    const cookieB = loginB.headers()['set-cookie'] || '';
    const dataB = await loginB.json();
    const tokenB = dataB.token || dataB.access_token;
    const bUserId = dataB.user_id || (dataB.user && dataB.user.id);

    // Login A1 to get token
    const loginA = await apiContext.post('/api/user/login', {
      data: { username: 'playwrightA1', password: 'Test1234!' }
    });
    const cookieA = loginA.headers()['set-cookie'] || '';
    const dataA = await loginA.json();
    const tokenA = dataA.token || dataA.access_token;

    // --- NEW: Clear stuck pending requests (B checks incoming from A1) ---
    const getReqs = await apiContext.get('/api/user/friends/requests', {
      headers: { 'Authorization': `Bearer ${tokenB}`, 'Cookie': cookieB }
    });
    
    let isAlreadyFriendsOrPendingResolved = false;

    if (getReqs.ok()) {
      const pendingData = await getReqs.json();
      const a1Request = (pendingData.incoming || []).find(
        (req: any) => req.user.username === 'playwrightA1' && req.status === 'pending'
      );
      
      if (a1Request) {
        console.log(`  ✅ Found STUCK pending request from A1 (ID: ${a1Request.id}). Accepting it...`);
        const acceptReq = await apiContext.post(`/api/user/friends/requests/${a1Request.id}/accept`, {
            headers: { 'Authorization': `Bearer ${tokenB}`, 'Cookie': cookieB }
        });
        if (acceptReq.ok()) {
           console.log(`  ✅ B accepted the stuck friend request from A1`);
        } else {
           console.warn(`  ⚠️ B failed to accept stuck request:`, await acceptReq.text());
        }
        isAlreadyFriendsOrPendingResolved = true; // Handled
      }
    }
    
    // Check if they are already friends by calling /api/user/friends as well just to be safe
    // But we can just rely on the existing 400 logic if they are.
    
    if (!isAlreadyFriendsOrPendingResolved) {
      // A1 sends friend request to B
      const sendReq = await apiContext.post('/api/user/friends/requests', {
        headers: { 'Authorization': `Bearer ${tokenA}`, 'Cookie': cookieA },
        data: { user_id: bUserId }
      });
      
      if (sendReq.ok()) {
        const sendData = await sendReq.json();
        const requestId = sendData.request_id;
        console.log(`  ✅ A1 sent friend request to B (Request ID: ${requestId})`);
        
        // B accepts friend request
        const acceptReq = await apiContext.post(`/api/user/friends/requests/${requestId}/accept`, {
            headers: { 'Authorization': `Bearer ${tokenB}`, 'Cookie': cookieB }
        });
        if (acceptReq.ok()) {
           console.log(`  ✅ B accepted new friend request from A1`);
        } else {
           console.warn(`  ⚠️ B failed to accept:`, await acceptReq.text());
        }
      } else {
        const resp = await sendReq.json().catch(() => ({}));
        console.log(`  ⏭️  Friendship setup skipped/handled: ${resp.detail || sendReq.status()}`);
      }
    }
  } catch (err) {
    console.error(`  ❌ Friendship setup failed:`, (err as Error).message);
  }

  await apiContext.dispose();
  console.log('🔧 [global-setup] Done.\n');
}

export default globalSetup;
