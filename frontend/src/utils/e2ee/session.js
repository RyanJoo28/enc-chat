import {listStoredSessionStates, loadStoredSessionState, saveStoredSessionState} from './storage';

const encoder = new TextEncoder();
const decoder = new TextDecoder();

const emptySalt = new Uint8Array(32);
const MAX_SKIP = 1000;
const MAX_USED_MESSAGE_KEYS = 50;

const toBase64 = (buffer) => {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return btoa(binary);
};

const fromBase64 = (value) => {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
};

const concatUint8Arrays = (...parts) => {
  const totalLength = parts.reduce((sum, part) => sum + part.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  parts.forEach((part) => {
    output.set(part, offset);
    offset += part.length;
  });
  return output;
};

const importX25519PrivateKey = async (jwk) => {
  return await window.crypto.subtle.importKey('jwk', jwk, {name: 'X25519'}, false, ['deriveBits']);
};

const importX25519PublicKey = async (jwk) => {
  return await window.crypto.subtle.importKey('jwk', jwk, {name: 'X25519'}, false, []);
};

const importEd25519PublicKey = async (jwk) => {
  return await window.crypto.subtle.importKey('jwk', jwk, {name: 'Ed25519'}, false, ['verify']);
};

const generateEphemeralKeyPair = async () => {
  const keyPair = await window.crypto.subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
  return {
    publicJwk: await window.crypto.subtle.exportKey('jwk', keyPair.publicKey),
    privateJwk: await window.crypto.subtle.exportKey('jwk', keyPair.privateKey),
  };
};

const generateRatchetKeyPair = async () => {
  const keyPair = await window.crypto.subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
  return {
    publicJwk: await window.crypto.subtle.exportKey('jwk', keyPair.publicKey),
    privateJwk: await window.crypto.subtle.exportKey('jwk', keyPair.privateKey),
  };
};

const deriveDh = async (privateJwk, publicJwk) => {
  const privateKey = await importX25519PrivateKey(privateJwk);
  const publicKey = await importX25519PublicKey(publicJwk);
  const bits = await window.crypto.subtle.deriveBits({name: 'X25519', public: publicKey}, privateKey, 256);
  return new Uint8Array(bits);
};

const hkdfExpand = async (inputKeyMaterial, infoText, byteLength) => {
  const key = await window.crypto.subtle.importKey('raw', inputKeyMaterial, 'HKDF', false, ['deriveBits']);
  const bits = await window.crypto.subtle.deriveBits(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: emptySalt,
      info: encoder.encode(infoText),
    },
    key,
    byteLength * 8,
  );
  return new Uint8Array(bits);
};

const verifySignedPrekey = async (bundleDevice) => {
  const verifyKey = await importEd25519PublicKey(JSON.parse(bundleDevice.signing_key_public));
  return await window.crypto.subtle.verify(
    'Ed25519',
    verifyKey,
    fromBase64(bundleDevice.signed_prekey.signature),
    encoder.encode(bundleDevice.signed_prekey.public_key),
  );
};

const buildConversationKey = (myUserId, remoteUserId) => {
  const low = Math.min(Number(myUserId), Number(remoteUserId));
  const high = Math.max(Number(myUserId), Number(remoteUserId));
  return `${low}:${high}`;
};

const deriveInitialChains = async (rootKey, isInitiator) => {
  const material = await hkdfExpand(rootKey, 'enc-chat:session:init', 64);
  const initiatorSend = material.slice(0, 32);
  const responderSend = material.slice(32, 64);

  return {
    sendChainKey: toBase64(isInitiator ? initiatorSend : responderSend),
    recvChainKey: toBase64(isInitiator ? responderSend : initiatorSend),
    initialSendChainKey: toBase64(isInitiator ? initiatorSend : responderSend),
    initialRecvChainKey: toBase64(isInitiator ? responderSend : initiatorSend),
  };
};

const performDhRatchet = async (rootKeyBytes, myPrivateJwk, theirPublicJwk) => {
  const dh = await deriveDh(myPrivateJwk, theirPublicJwk);
  const material = await hkdfExpand(
    concatUint8Arrays(dh, rootKeyBytes),
    'enc-chat:ratchet:v2',
    64,
  );
  return {
    rootKeyBase64: toBase64(material.slice(0, 32)),
    chainKeyBase64: toBase64(material.slice(32, 64)),
  };
};

const stepDHratchet = async (state, remoteRatchetPublicKey) => {
  state.recvCounter = 0;

  const remoteRatchetPubJwk = JSON.parse(remoteRatchetPublicKey);
  const result = await performDhRatchet(
    fromBase64(state.rootKey),
    state.sendingRatchetKeyPair.privateJwk,
    remoteRatchetPubJwk,
  );

  state.rootKey = result.rootKeyBase64;
  state.recvChainKey = result.chainKeyBase64;
  state.receivingRatchetPublic = remoteRatchetPublicKey;

  return state;
};

const skipReceiveChainKeys = async (state, targetCounter) => {
  while (state.recvCounter < targetCounter) {
    const step = await deriveNextStep(state.recvChainKey);
    const ratchetPrefix = (state.receivingRatchetPublic || 'initial').substring(0, 32);
    if (!state.skippedKeys) {
      state.skippedKeys = {};
    }
    if (!state.usedMessageKeys) {
      state.usedMessageKeys = {};
    }
    if (Object.keys(state.skippedKeys).length >= MAX_SKIP) {
      throw new Error('消息跳跃过多');
    }
    const keyB64 = toBase64(step.messageKey);
    state.skippedKeys[`${ratchetPrefix}:${state.recvCounter}`] = keyB64;
    state.usedMessageKeys[`${ratchetPrefix}:${state.recvCounter}`] = keyB64;
    state.recvChainKey = step.nextChainKey;
    state.recvCounter++;
  }
  return state;
};

const deriveNextStep = async (chainKeyBase64) => {
  const material = await hkdfExpand(fromBase64(chainKeyBase64), 'enc-chat:chain:step', 64);
  return {
    nextChainKey: toBase64(material.slice(0, 32)),
    messageKey: material.slice(32, 64),
  };
};

const tryUsedMessageKeys = async (state, envelope) => {
  const dhPrefix = (envelope.dh_ratchet_key || 'initial').substring(0, 32);
  const skipKey = `${dhPrefix}:${envelope.counter}`;
  
  if (state.usedPlaintexts && state.usedPlaintexts[skipKey]) {
    return state.usedPlaintexts[skipKey];
  }

  if (!state.usedMessageKeys) {
    return null;
  }
  const messageKeyBase64 = state.usedMessageKeys[skipKey];
  if (!messageKeyBase64) {
    return null;
  }
  try {
    return await decryptPayload(fromBase64(messageKeyBase64), envelope.nonce, envelope.ciphertext);
  } catch {
    return null;
  }
};

const trySkippedMessageKeys = async (state, envelope) => {
  if (!state.skippedKeys || !envelope) {
    return null;
  }
  const dhPrefix = (envelope.dh_ratchet_key || 'initial').substring(0, 32);
  const skipKey = `${dhPrefix}:${envelope.counter}`;
  const messageKeyBase64 = state.skippedKeys[skipKey];
  if (!messageKeyBase64) {
    return null;
  }
  if (!state.usedMessageKeys) state.usedMessageKeys = {};
  state.usedMessageKeys[skipKey] = messageKeyBase64;
  delete state.skippedKeys[skipKey];
  try {
    return await decryptPayload(fromBase64(messageKeyBase64), envelope.nonce, envelope.ciphertext);
  } catch {
    return null;
  }
};

const encryptPayload = async (messageKeyBytes, plaintext) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const aesKey = await window.crypto.subtle.importKey('raw', messageKeyBytes, {name: 'AES-GCM'}, false, ['encrypt']);
  const ciphertext = await window.crypto.subtle.encrypt(
    {name: 'AES-GCM', iv},
    aesKey,
    encoder.encode(plaintext),
  );
  return {
    nonce: toBase64(iv),
    ciphertext: toBase64(ciphertext),
  };
};

const decryptPayload = async (messageKeyBytes, nonceBase64, ciphertextBase64) => {
  const iv = fromBase64(nonceBase64);
  const ciphertext = fromBase64(ciphertextBase64);
  const aesKey = await window.crypto.subtle.importKey('raw', messageKeyBytes, {name: 'AES-GCM'}, false, ['decrypt']);
  const plaintext = await window.crypto.subtle.decrypt(
    {name: 'AES-GCM', iv},
    aesKey,
    ciphertext,
  );
  return decoder.decode(plaintext);
};

const deriveLocalMessageKey = async (deviceState) => {
  return await hkdfExpand(
    encoder.encode(JSON.stringify(deviceState.identityKeyPair.privateJwk)),
    'enc-chat:local-envelope',
    32,
  );
};

export const deriveCacheEncryptionKey = async (deviceState) => {
  return await hkdfExpand(
    encoder.encode(JSON.stringify(deviceState.identityKeyPair.privateJwk)),
    'enc-chat:plaintext-cache-key',
    32,
  );
};

const trimSessionState = (state) => {
  delete state.usedPlaintexts;
  if (state.usedMessageKeys) {
    const keys = Object.keys(state.usedMessageKeys);
    if (keys.length > MAX_USED_MESSAGE_KEYS) {
      const toRemove = keys.slice(0, keys.length - MAX_USED_MESSAGE_KEYS);
      for (const key of toRemove) {
        delete state.usedMessageKeys[key];
      }
    }
  }
};

// Removed replay functions that violate forward secrecy / ratchet state continuity

export const buildStoredSession = async ({
  deviceState,
  myUserId,
  remoteUserId,
  remoteDeviceId,
  remoteIdentityKey,
  remoteSignedPrekeyId,
  remoteOneTimePrekeyId,
  sessionId,
  isInitiator,
  rootKey,
  ephemeralKeyPair = null,
  initialReceivingRatchetPublic = null,
}) => {
  const chains = await deriveInitialChains(rootKey, isInitiator);
  const rootKeyBase64 = toBase64(rootKey);

  let sendingRatchetKeyPair;
  if (isInitiator && ephemeralKeyPair) {
    sendingRatchetKeyPair = {
      privateJwk: ephemeralKeyPair.privateJwk,
      publicJwk: ephemeralKeyPair.publicJwk,
    };
  } else if (ephemeralKeyPair) {
    sendingRatchetKeyPair = {
      privateJwk: ephemeralKeyPair.privateJwk,
      publicJwk: ephemeralKeyPair.publicJwk,
    };
  }

  const session = {
    version: 2,
    sessionId,
    myDeviceId: deviceState.deviceId,
    myUserId,
    remoteUserId,
    remoteDeviceId,
    conversationKey: buildConversationKey(myUserId, remoteUserId),
    remoteIdentityKey,
    localIdentityKeyPublic: deviceState.identityKeyPair.publicJwk,
    remoteSignedPrekeyId,
    remoteOneTimePrekeyId: remoteOneTimePrekeyId || null,
    isInitiator,
    sendCounter: 0,
    recvCounter: 0,
    previousSendCounter: 0,
    rootKey: rootKeyBase64,
    initialRootKey: rootKeyBase64,
    sendingRatchetKeyPair,
    initialSendingRatchetKeyPair: sendingRatchetKeyPair
      ? {privateJwk: sendingRatchetKeyPair.privateJwk, publicJwk: sendingRatchetKeyPair.publicJwk}
      : null,
    receivingRatchetPublic: initialReceivingRatchetPublic,
    initialReceivingRatchetPublic: initialReceivingRatchetPublic,
    lastAckedReceivingRatchetPublic: null,
    skippedKeys: {},
    usedMessageKeys: {},
    ...chains,
    ephemeralKeyPair,
  };
  
  return session;
};

const hasIdentityMismatch = (sessionState, identityKeyPublic) => {
  return Boolean(
    sessionState
    && identityKeyPublic
    && sessionState.remoteIdentityKey
    && sessionState.remoteIdentityKey !== identityKeyPublic
  );
};

const shouldRebuildIncomingSession = (sessionState, envelope) => {
  if (!sessionState || envelope?.mode !== 'prekey') {
    return false;
  }

  if (hasIdentityMismatch(sessionState, envelope.sender_identity_key)) {
    return true;
  }

  return Boolean(
    envelope.session_id
    && sessionState.sessionId
    && sessionState.sessionId !== envelope.session_id
  );
};

export const loadDeviceSession = async (scopeKey, remoteDeviceId) => {
  return await loadStoredSessionState(scopeKey, remoteDeviceId);
};

export const saveDeviceSession = async (scopeKey, remoteDeviceId, sessionState) => {
  return await saveStoredSessionState(scopeKey, remoteDeviceId, sessionState);
};

export const listDeviceSessions = async (scopeKey) => {
  return await listStoredSessionStates(scopeKey);
};

export const createInitiatorSession = async ({scopeKey, deviceState, remoteUserId, bundleDevice}) => {
  const isValidSignature = await verifySignedPrekey(bundleDevice);
  if (!isValidSignature) {
    throw new Error('对方设备 prekey 签名校验失败');
  }

  const ephemeralKeyPair = await generateEphemeralKeyPair();
  const remoteIdentityJwk = JSON.parse(bundleDevice.identity_key_public);
  const remoteSignedPrekeyJwk = JSON.parse(bundleDevice.signed_prekey.public_key);
  const remoteOneTimePrekeyJwk = bundleDevice.one_time_prekey ? JSON.parse(bundleDevice.one_time_prekey.public_key) : null;

  const secretParts = [
    await deriveDh(deviceState.identityKeyPair.privateJwk, remoteSignedPrekeyJwk),
    await deriveDh(ephemeralKeyPair.privateJwk, remoteIdentityJwk),
    await deriveDh(ephemeralKeyPair.privateJwk, remoteSignedPrekeyJwk),
  ];

  if (remoteOneTimePrekeyJwk) {
    secretParts.push(await deriveDh(ephemeralKeyPair.privateJwk, remoteOneTimePrekeyJwk));
  }

  const rootKey = await hkdfExpand(concatUint8Arrays(...secretParts), 'enc-chat:x3dh', 32);
  const sessionState = await buildStoredSession({
    deviceState,
    myUserId: deviceState.userId,
    remoteUserId,
    remoteDeviceId: bundleDevice.device_id,
    remoteIdentityKey: bundleDevice.identity_key_public,
    remoteSignedPrekeyId: bundleDevice.signed_prekey.key_id,
    remoteOneTimePrekeyId: bundleDevice.one_time_prekey?.key_id || null,
    sessionId: window.crypto.randomUUID(),
    isInitiator: true,
    rootKey,
    ephemeralKeyPair,
    initialReceivingRatchetPublic: null,
  });

  await saveDeviceSession(scopeKey, bundleDevice.device_id, sessionState);
  return sessionState;
};

export const encryptOutgoingMessage = async ({scopeKey, sessionState, plaintext}) => {
  const isFirstPrekeyMessage = sessionState.sendCounter === 0
    && sessionState.previousSendCounter === 0
    && sessionState.isInitiator
    && Boolean(sessionState.ephemeralKeyPair);


  let nextState = {...sessionState};
  let didDhRatchet = false;

  if (!isFirstPrekeyMessage && nextState.ephemeralKeyPair) {
    delete nextState.ephemeralKeyPair;
  }

  // Only perform a DH ratchet when the remote ratchet public key has changed
  // since we last ratcheted (i.e., we received a new key from the remote party).
  const needsDhRatchet = !isFirstPrekeyMessage
    && nextState.receivingRatchetPublic
    && nextState.receivingRatchetPublic !== nextState.lastAckedReceivingRatchetPublic;

  if (needsDhRatchet) {
    // Generate a new sending ratchet key pair
    const newRatchetKeyPair = await generateRatchetKeyPair();
    const theirPubJwk = JSON.parse(nextState.receivingRatchetPublic);

    // Perform DH ratchet to derive a new send chain
    const result = await performDhRatchet(
      fromBase64(nextState.rootKey),
      newRatchetKeyPair.privateJwk,
      theirPubJwk,
    );

    nextState.rootKey = result.rootKeyBase64;
    nextState.sendChainKey = result.chainKeyBase64;
    nextState.sendingRatchetKeyPair = newRatchetKeyPair;
    nextState.previousSendCounter = nextState.sendCounter;
    nextState.sendCounter = 0;
    nextState.lastAckedReceivingRatchetPublic = nextState.receivingRatchetPublic;
    didDhRatchet = true;
  }

  const step = await deriveNextStep(nextState.sendChainKey);
  const encrypted = await encryptPayload(step.messageKey, plaintext);

  const envelope = {
    version: 'e2ee_v1',
    mode: isFirstPrekeyMessage ? 'prekey' : 'message',
    session_id: nextState.sessionId,
    counter: nextState.sendCounter,
    previous_counter: nextState.previousSendCounter || 0,
    dh_ratchet_key: JSON.stringify(nextState.sendingRatchetKeyPair.publicJwk),
    sender_device_id: nextState.myDeviceId,
    recipient_device_id: nextState.remoteDeviceId,
    nonce: encrypted.nonce,
    ciphertext: encrypted.ciphertext,
  };

  if (isFirstPrekeyMessage) {
    envelope.sender_identity_key = JSON.stringify(nextState.localIdentityKeyPublic || {});
    envelope.sender_ephemeral_key = JSON.stringify(nextState.ephemeralKeyPair.publicJwk);
    envelope.recipient_signed_prekey_id = nextState.remoteSignedPrekeyId;
    envelope.recipient_one_time_prekey_id = nextState.remoteOneTimePrekeyId;
  }

  nextState.sendChainKey = step.nextChainKey;
  nextState.sendCounter = nextState.sendCounter + 1;

  if (isFirstPrekeyMessage) {
    delete nextState.ephemeralKeyPair;
  }

  await saveDeviceSession(scopeKey, nextState.remoteDeviceId, nextState);
  return {envelope, sessionState: nextState};
};

export const attachLocalIdentityToSession = (sessionState, deviceState) => ({
  ...sessionState,
  localIdentityKeyPublic: deviceState.identityKeyPair.publicJwk,
});

export const encryptLocalEnvelope = async (deviceState, plaintext) => {
  const messageKey = await deriveLocalMessageKey(deviceState);
  const encrypted = await encryptPayload(messageKey, plaintext);
  return {
    version: 'e2ee_v1',
    mode: 'local',
    nonce: encrypted.nonce,
    ciphertext: encrypted.ciphertext,
  };
};

export const decryptLocalEnvelope = async (deviceState, envelope) => {
  const messageKey = await deriveLocalMessageKey(deviceState);
  return await decryptPayload(messageKey, envelope.nonce, envelope.ciphertext);
};

const rebuildIncomingSession = async (deviceState, envelope) => {
  const senderIdentityJwk = JSON.parse(envelope.sender_identity_key);
  const senderEphemeralJwk = JSON.parse(envelope.sender_ephemeral_key);
  const signedPrekey = deviceState.signedPrekey;

  if (!signedPrekey?.privateKey) {
    throw new Error('rebuildIncomingSession: signedPrekey.privateKey is missing from device state');
  }
  if (!deviceState.identityKeyPair?.privateJwk) {
    throw new Error('rebuildIncomingSession: identityKeyPair.privateJwk is missing from device state');
  }

  const oneTimePrekey = envelope.recipient_one_time_prekey_id
    ? deviceState.oneTimePrekeys.find((item) => item.keyId === envelope.recipient_one_time_prekey_id)
    : null;

  if (envelope.recipient_one_time_prekey_id && !oneTimePrekey) {
    console.warn('[E2EE] One-time prekey not found locally:',
      'requested_key_id:', envelope.recipient_one_time_prekey_id,
      'available_key_ids:', (deviceState.oneTimePrekeys || []).map((item) => item.keyId).slice(0, 10),
      'sender_device_id:', envelope.sender_device_id);
  }

  const secretParts = [
    await deriveDh(signedPrekey.privateKey, senderIdentityJwk),
    await deriveDh(deviceState.identityKeyPair.privateJwk, senderEphemeralJwk),
    await deriveDh(signedPrekey.privateKey, senderEphemeralJwk),
  ];
  if (oneTimePrekey) {
    secretParts.push(await deriveDh(oneTimePrekey.privateKey, senderEphemeralJwk));
  }

  const rootKey = await hkdfExpand(concatUint8Arrays(...secretParts), 'enc-chat:x3dh', 32);
  const newRatchetKeyPair = await generateRatchetKeyPair();
  const initiatorRatchetPublic = envelope.sender_ephemeral_key;

  return await buildStoredSession({
    deviceState,
    myUserId: deviceState.userId,
    remoteUserId: Number(envelope.sender_user_id || 0),
    remoteDeviceId: envelope.sender_device_id,
    remoteIdentityKey: envelope.sender_identity_key,
    remoteSignedPrekeyId: envelope.recipient_signed_prekey_id,
    remoteOneTimePrekeyId: envelope.recipient_one_time_prekey_id,
    sessionId: envelope.session_id,
    isInitiator: false,
    rootKey,
    ephemeralKeyPair: newRatchetKeyPair,
    initialReceivingRatchetPublic: initiatorRatchetPublic,
  });
};

const advanceReceiveChain = async (sessionState, targetCounter) => {
  if (sessionState.recvCounter > targetCounter) {
    throw new Error('消息计数器过期');
  }
  if (targetCounter - sessionState.recvCounter > MAX_SKIP) {
    throw new Error('消息跳跃过大');
  }

  let state = {...sessionState};
  state = await skipReceiveChainKeys(state, targetCounter);

  const step = await deriveNextStep(state.recvChainKey);
  const ratchetPrefix = (state.receivingRatchetPublic || 'initial').substring(0, 32);
  if (!state.usedMessageKeys) {
    state.usedMessageKeys = {};
  }
  state.usedMessageKeys[`${ratchetPrefix}:${state.recvCounter}`] = toBase64(step.messageKey);

  return {
    state: {
      ...state,
      recvChainKey: step.nextChainKey,
      recvCounter: state.recvCounter + 1,
    },
    messageKey: step.messageKey,
  };
};

const isSessionVersionValid = (sessionState) => {
  if (!sessionState) return false;
  return sessionState.version >= 2 && sessionState.rootKey && sessionState.sendingRatchetKeyPair;
};

export const decryptEnvelopeForHistory = async ({deviceState, sessionState, envelope, metadata}) => {
  if (envelope.mode === 'local') {
    return {
      sessionState,
      plaintext: await decryptLocalEnvelope(deviceState, envelope),
    };
  }

  let workingSession = sessionState && isSessionVersionValid(sessionState) ? sessionState : null;
  
  if (shouldRebuildIncomingSession(workingSession, envelope)) {
    workingSession = null;
  }
  if (!workingSession && envelope.mode === 'prekey') {
    workingSession = await rebuildIncomingSession(deviceState, {
      ...envelope,
      sender_user_id: metadata.sender_user_id,
    });
  }
  if (!workingSession) {
    throw new Error(`缺少会话状态 (mode=${envelope.mode}, sender_device=${envelope.sender_device_id}, has_existing=${Boolean(sessionState)})`);
  }

  if (workingSession.ephemeralKeyPair && (workingSession.sendCounter > 0 || workingSession.previousSendCounter > 0)) {
    delete workingSession.ephemeralKeyPair;
  }

  let plaintext = await tryUsedMessageKeys(workingSession, envelope);
  if (plaintext !== null) {
    return {
      sessionState: workingSession,
      plaintext,
    };
  } else {
    console.warn(`[E2EE-DEBUG] tryUsedMessageKeys returned null for msg_counter=${envelope.counter}`);
  }

  plaintext = await trySkippedMessageKeys(workingSession, envelope);
  if (plaintext !== null) {
    return {
      sessionState: workingSession,
      plaintext,
    };
  }

  if (envelope.dh_ratchet_key && envelope.dh_ratchet_key !== workingSession.receivingRatchetPublic) {
    const pn = envelope.previous_counter || 0;
    if (workingSession.recvCounter < pn) {
      console.error(`[E2EE-DEBUG] skipReceiveChainKeys called in history: current=${workingSession.recvCounter}, target=${pn}`);
      await skipReceiveChainKeys(workingSession, pn);
    }
    await stepDHratchet(workingSession, envelope.dh_ratchet_key);
  }

  try {
    const result = await advanceReceiveChain(workingSession, envelope.counter);
    try {
      plaintext = await decryptPayload(result.messageKey, envelope.nonce, envelope.ciphertext);
    } catch (err) {
      console.error(`[E2EE-DEBUG] decryptPayload failed in history. counter=${envelope.counter}`);
      throw err;
    }
    return {
      sessionState: result.state,
      plaintext,
    };
  } catch (err) {
    console.error(`[E2EE-DEBUG] decryptEnvelopeForHistory failed entirely:`, err);
    throw err;
  }
};

export const decryptIncomingEnvelope = async ({scopeKey, deviceState, envelope, metadata}) => {
  if (envelope.mode === 'local') {
    return {
      sessionState: null,
      plaintext: await decryptLocalEnvelope(deviceState, envelope),
    };
  }

  let sessionState = await loadDeviceSession(scopeKey, envelope.sender_device_id);
  const sessionExists = isSessionVersionValid(sessionState);
  if (!sessionExists) {
    sessionState = null;
  }
  
  let didRebuild = false;
  if (shouldRebuildIncomingSession(sessionState, envelope)) {
    sessionState = null;
  }
  if (!sessionState && envelope.mode === 'prekey') {
    sessionState = await rebuildIncomingSession(deviceState, {
      ...envelope,
      sender_user_id: metadata.sender_user_id,
    });
    didRebuild = true;
  }
  if (!sessionState) {
    throw new Error(`缺少会话状态 (mode=${envelope.mode}, sender_device=${envelope.sender_device_id}, has_stored=false)`);
  }

  if (sessionState.ephemeralKeyPair && (sessionState.sendCounter > 0 || sessionState.previousSendCounter > 0)) {
    delete sessionState.ephemeralKeyPair;
    await saveDeviceSession(scopeKey, envelope.sender_device_id, sessionState);
  }

  let workingState = {...sessionState};

  let plaintext = await tryUsedMessageKeys(workingState, envelope);
  if (plaintext !== null) {
    return {
      sessionState: workingState,
      plaintext,
    };
  }

  plaintext = await trySkippedMessageKeys(workingState, envelope);
  if (plaintext !== null) {
    await saveDeviceSession(scopeKey, envelope.sender_device_id, workingState);
    return {
      sessionState: workingState,
      plaintext,
    };
  }

  if (workingState && envelope.dh_ratchet_key && envelope.dh_ratchet_key !== workingState.receivingRatchetPublic) {
    const pn = envelope.previous_counter || 0;
    if (workingState.recvCounter < pn) {
      await skipReceiveChainKeys(workingState, pn);
    }
    await stepDHratchet(workingState, envelope.dh_ratchet_key);
  }

  const result = await advanceReceiveChain(workingState, envelope.counter);
  plaintext = await decryptPayload(result.messageKey, envelope.nonce, envelope.ciphertext);

  trimSessionState(result.state);
  await saveDeviceSession(scopeKey, envelope.sender_device_id, result.state);
  return {
    sessionState: result.state,
    plaintext,
  };
};
