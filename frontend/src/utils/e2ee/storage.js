const DB_NAME = 'enc-chat-e2ee';
const DB_VERSION = 1;
const STORE_NAME = 'kv';

const buildCurrentDeviceKey = (scopeKey = 'default') => `current_device:${scopeKey}`;
const buildSessionKey = (scopeKey = 'default', remoteDeviceId = 'unknown') => `session:${scopeKey}:${remoteDeviceId}`;
const buildGroupSenderKeyKey = (scopeKey = 'default', groupId = 'unknown', epoch = '0', senderDeviceId = 'unknown') => `group_sender_key:${scopeKey}:${groupId}:${epoch}:${senderDeviceId}`;
const buildOutboxKey = (scopeKey = 'default', clientMessageId = 'unknown') => `outbox:${scopeKey}:${clientMessageId}`;

const normalizeForStorage = (value) => {
  if (value === null || value === undefined) {
    return value;
  }

  return JSON.parse(JSON.stringify(value));
};

const openDatabase = () => new Promise((resolve, reject) => {
  const request = indexedDB.open(DB_NAME, DB_VERSION);

  request.onupgradeneeded = () => {
    const db = request.result;
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME);
    }
  };

  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
});

const withStore = async (mode, callback) => {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, mode);
    const store = transaction.objectStore(STORE_NAME);
    const result = callback(store);

    transaction.oncomplete = () => {
      db.close();
      resolve(result?.result);
    };
    transaction.onerror = () => {
      db.close();
      reject(transaction.error || result?.error);
    };
    transaction.onabort = () => {
      db.close();
      reject(transaction.error || result?.error);
    };
  });
};

const getValue = async (key) => withStore('readonly', (store) => store.get(key));

const setValue = async (key, value) => withStore('readwrite', (store) => store.put(normalizeForStorage(value), key));

const deleteValue = async (key) => withStore('readwrite', (store) => store.delete(key));

const listValuesByPrefix = async (prefix) => {
  const db = await openDatabase();

  return await new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const values = [];
    const request = store.openCursor();

    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) {
        resolve(values);
        return;
      }

      if (String(cursor.key).startsWith(prefix)) {
        values.push(cursor.value);
      }
      cursor.continue();
    };

    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => db.close();
    transaction.onerror = () => {
      db.close();
      reject(transaction.error);
    };
    transaction.onabort = () => {
      db.close();
      reject(transaction.error);
    };
  });
};

const listEntriesByPrefix = async (prefix) => {
  const db = await openDatabase();

  return await new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const entries = [];
    const request = store.openCursor();

    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) {
        resolve(entries);
        return;
      }

      if (String(cursor.key).startsWith(prefix)) {
        entries.push({key: cursor.key, value: cursor.value});
      }
      cursor.continue();
    };

    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => db.close();
    transaction.onerror = () => {
      db.close();
      reject(transaction.error);
    };
    transaction.onabort = () => {
      db.close();
      reject(transaction.error);
    };
  });
};

const deleteValuesByPrefix = async (prefix) => {
  const entries = await listEntriesByPrefix(prefix);
  if (!entries.length) {
    return 0;
  }

  await withStore('readwrite', (store) => {
    entries.forEach((entry) => {
      store.delete(entry.key);
    });
  });
  return entries.length;
};

export const loadStoredDeviceState = async (scopeKey = 'default') => {
  return await getValue(buildCurrentDeviceKey(scopeKey)) || null;
};

export const saveStoredDeviceState = async (scopeKey = 'default', value) => {
  await setValue(buildCurrentDeviceKey(scopeKey), value);
  return value;
};

export const clearStoredDeviceState = async (scopeKey = 'default') => {
  await deleteValue(buildCurrentDeviceKey(scopeKey));
};

export const loadStoredSessionState = async (scopeKey = 'default', remoteDeviceId) => {
  const value = await getValue(buildSessionKey(scopeKey, remoteDeviceId)) || null;
  return value;
};

export const saveStoredSessionState = async (scopeKey = 'default', remoteDeviceId, value) => {
  await setValue(buildSessionKey(scopeKey, remoteDeviceId), value);
  return value;
};

export const clearStoredSessionState = async (scopeKey = 'default', remoteDeviceId) => {
  await deleteValue(buildSessionKey(scopeKey, remoteDeviceId));
};

export const listStoredSessionStates = async (scopeKey = 'default') => {
  return await listValuesByPrefix(`session:${scopeKey}:`);
};

export const clearStoredSessionStates = async (scopeKey = 'default') => {
  return await deleteValuesByPrefix(`session:${scopeKey}:`);
};

export const loadGroupSenderKeyState = async (scopeKey = 'default', groupId, epoch, senderDeviceId) => {
  return await getValue(buildGroupSenderKeyKey(scopeKey, groupId, epoch, senderDeviceId)) || null;
};

export const saveGroupSenderKeyState = async (scopeKey = 'default', groupId, epoch, senderDeviceId, value) => {
  await setValue(buildGroupSenderKeyKey(scopeKey, groupId, epoch, senderDeviceId), value);
  return value;
};

export const listGroupSenderKeyStates = async (scopeKey = 'default', groupId) => {
  return await listValuesByPrefix(`group_sender_key:${scopeKey}:${groupId}:`);
};

export const clearGroupSenderKeyStates = async (scopeKey = 'default', groupId = '') => {
  const groupPrefix = groupId === '' ? '' : `${groupId}:`;
  return await deleteValuesByPrefix(`group_sender_key:${scopeKey}:${groupPrefix}`);
};

export const loadOutboxMessage = async (scopeKey = 'default', clientMessageId) => {
  return await getValue(buildOutboxKey(scopeKey, clientMessageId)) || null;
};

export const saveOutboxMessage = async (scopeKey = 'default', clientMessageId, value) => {
  await setValue(buildOutboxKey(scopeKey, clientMessageId), value);
  return value;
};

export const removeOutboxMessage = async (scopeKey = 'default', clientMessageId) => {
  await deleteValue(buildOutboxKey(scopeKey, clientMessageId));
};

export const listOutboxMessages = async (scopeKey = 'default') => {
  const items = await listValuesByPrefix(`outbox:${scopeKey}:`);
  return items.sort((left, right) => {
    const leftTs = new Date(left?.createdAt || 0).getTime();
    const rightTs = new Date(right?.createdAt || 0).getTime();
    return leftTs - rightTs;
  });
};

export const clearOutboxMessages = async (scopeKey = 'default') => {
  return await deleteValuesByPrefix(`outbox:${scopeKey}:`);
};

// ---------------------------------------------------------------------------
// Plaintext cache – AES-GCM encrypted at rest
// ---------------------------------------------------------------------------

const buildPlaintextCacheKey = (scopeKey = 'default', messageId = '0') => `plaintext_cache:${scopeKey}:${messageId}`;

const importCacheKey = async (rawKeyBytes) => {
  return await crypto.subtle.importKey('raw', rawKeyBytes, {name: 'AES-GCM'}, false, ['encrypt', 'decrypt']);
};

const encryptCacheEntry = async (aesKey, plaintext) => {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, aesKey, encoded);
  return {iv: Array.from(iv), ct: Array.from(new Uint8Array(ciphertext))};
};

const decryptCacheEntry = async (aesKey, entry) => {
  const iv = new Uint8Array(entry.iv);
  const ct = new Uint8Array(entry.ct);
  const plainBuffer = await crypto.subtle.decrypt({name: 'AES-GCM', iv}, aesKey, ct);
  return new TextDecoder().decode(plainBuffer);
};

export const saveCachedPlaintext = async (scopeKey, messageId, plaintext, cacheKeyBytes) => {
  const aesKey = await importCacheKey(cacheKeyBytes);
  const encrypted = await encryptCacheEntry(aesKey, plaintext);
  await setValue(buildPlaintextCacheKey(scopeKey, messageId), encrypted);
};

export const saveCachedPlaintextBatch = async (scopeKey, entries, cacheKeyBytes) => {
  if (!entries.length) return;

  const aesKey = await importCacheKey(cacheKeyBytes);
  const prepared = [];
  for (const entry of entries) {
    const enc = await encryptCacheEntry(aesKey, entry.plaintext);
    prepared.push({key: buildPlaintextCacheKey(scopeKey, entry.messageId), value: enc});
  }

  const db = await openDatabase();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    for (const item of prepared) {
      store.put(normalizeForStorage(item.value), item.key);
    }
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
    tx.onabort = () => { db.close(); reject(tx.error); };
  });
};

export const loadCachedPlaintextBatch = async (scopeKey, messageIds, cacheKeyBytes) => {
  if (!messageIds.length) return new Map();

  const db = await openDatabase();
  const rawEntries = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const collected = new Map();
    for (const msgId of messageIds) {
      const req = store.get(buildPlaintextCacheKey(scopeKey, msgId));
      req.onsuccess = () => { if (req.result) collected.set(msgId, req.result); };
    }
    tx.oncomplete = () => { db.close(); resolve(collected); };
    tx.onerror = () => { db.close(); reject(tx.error); };
    tx.onabort = () => { db.close(); reject(tx.error); };
  });

  const aesKey = await importCacheKey(cacheKeyBytes);
  const results = new Map();
  for (const [msgId, entry] of rawEntries) {
    try {
      results.set(msgId, await decryptCacheEntry(aesKey, entry));
    } catch {
      // skip corrupted entries silently
    }
  }
  return results;
};

export const removeCachedPlaintext = async (scopeKey, messageId) => {
  await deleteValue(buildPlaintextCacheKey(scopeKey, messageId));
};

export const clearCachedPlaintexts = async (scopeKey = 'default') => {
  return await deleteValuesByPrefix(`plaintext_cache:${scopeKey}:`);
};
