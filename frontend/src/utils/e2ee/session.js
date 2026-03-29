import {listStoredSessionStates, loadStoredSessionState, saveStoredSessionState} from './storage';

const encoder = new TextEncoder();
const decoder = new TextDecoder();

const emptySalt = new Uint8Array(32);

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

const deriveNextStep = async (chainKeyBase64) => {
  const material = await hkdfExpand(fromBase64(chainKeyBase64), 'enc-chat:chain:step', 64);
  return {
    nextChainKey: toBase64(material.slice(0, 32)),
    messageKey: material.slice(32, 64),
  };
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

const cloneSessionForReplay = (sessionState) => ({
  ...sessionState,
  sendChainKey: sessionState.initialSendChainKey,
  recvChainKey: sessionState.initialRecvChainKey,
  sendCounter: 0,
  recvCounter: 0,
});

const buildStoredSession = async ({
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
}) => {
  const chains = await deriveInitialChains(rootKey, isInitiator);
  return {
    version: 1,
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
    ...chains,
  ephemeralKeyPair,
  };
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
  });

  await saveDeviceSession(scopeKey, bundleDevice.device_id, sessionState);
  return sessionState;
};

export const encryptOutgoingMessage = async ({scopeKey, sessionState, plaintext}) => {
  const step = await deriveNextStep(sessionState.sendChainKey);
  const encrypted = await encryptPayload(step.messageKey, plaintext);

  const envelope = {
    version: 'e2ee_v1',
    mode: sessionState.sendCounter === 0 && sessionState.isInitiator && sessionState.ephemeralKeyPair ? 'prekey' : 'message',
    session_id: sessionState.sessionId,
    counter: sessionState.sendCounter,
    sender_device_id: sessionState.myDeviceId,
    recipient_device_id: sessionState.remoteDeviceId,
    nonce: encrypted.nonce,
    ciphertext: encrypted.ciphertext,
  };

  const nextState = {
    ...sessionState,
    sendChainKey: step.nextChainKey,
    sendCounter: sessionState.sendCounter + 1,
  };

  if (envelope.mode === 'prekey') {
    envelope.sender_identity_key = JSON.stringify(sessionState.localIdentityKeyPublic || {});
    envelope.sender_ephemeral_key = JSON.stringify(sessionState.ephemeralKeyPair.publicJwk);
    envelope.recipient_signed_prekey_id = sessionState.remoteSignedPrekeyId;
    envelope.recipient_one_time_prekey_id = sessionState.remoteOneTimePrekeyId;
  }

  await saveDeviceSession(scopeKey, sessionState.remoteDeviceId, nextState);
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
  });
};

const advanceReceiveChain = async (sessionState, targetCounter) => {
  let state = {...sessionState};
  while (state.recvCounter <= targetCounter) {
    const step = await deriveNextStep(state.recvChainKey);
    if (state.recvCounter === targetCounter) {
      return {
        state: {
          ...state,
          recvChainKey: step.nextChainKey,
          recvCounter: state.recvCounter + 1,
        },
        messageKey: step.messageKey,
      };
    }

    state = {
      ...state,
      recvChainKey: step.nextChainKey,
      recvCounter: state.recvCounter + 1,
    };
  }

  throw new Error('消息计数器无效');
};

export const decryptEnvelopeForHistory = async ({deviceState, sessionState, envelope, metadata}) => {
  if (envelope.mode === 'local') {
    return {
      sessionState,
      plaintext: await decryptLocalEnvelope(deviceState, envelope),
    };
  }

  let workingSession = sessionState;
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

  const replaySession = cloneSessionForReplay(workingSession);
  const result = await advanceReceiveChain(replaySession, envelope.counter);
  const plaintext = await decryptPayload(result.messageKey, envelope.nonce, envelope.ciphertext);
  return {
    sessionState: result.state,
    plaintext,
  };
};

export const decryptIncomingEnvelope = async ({scopeKey, deviceState, envelope, metadata}) => {
  if (envelope.mode === 'local') {
    return {
      sessionState: null,
      plaintext: await decryptLocalEnvelope(deviceState, envelope),
    };
  }

  let sessionState = await loadDeviceSession(scopeKey, envelope.sender_device_id);
  if (shouldRebuildIncomingSession(sessionState, envelope)) {
    sessionState = null;
  }
  if (!sessionState && envelope.mode === 'prekey') {
    sessionState = await rebuildIncomingSession(deviceState, {
      ...envelope,
      sender_user_id: metadata.sender_user_id,
    });
  }
  if (!sessionState) {
    throw new Error(`缺少会话状态 (mode=${envelope.mode}, sender_device=${envelope.sender_device_id}, has_stored=false)`);
  }

  const result = await advanceReceiveChain(sessionState, envelope.counter);
  const plaintext = await decryptPayload(result.messageKey, envelope.nonce, envelope.ciphertext);
  await saveDeviceSession(scopeKey, envelope.sender_device_id, result.state);
  return {
    sessionState: result.state,
    plaintext,
  };
};
