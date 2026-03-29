const textEncoder = new TextEncoder();

const ensureSubtleCrypto = () => {
  if (!window.crypto?.subtle) {
    throw new Error('当前浏览器不支持 Web Crypto');
  }
};

const toBase64 = (buffer) => {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((item) => {
    binary += String.fromCharCode(item);
  });
  return btoa(binary);
};

const exportPublicJwk = async (key) => await window.crypto.subtle.exportKey('jwk', key);

const exportPrivateJwk = async (key) => await window.crypto.subtle.exportKey('jwk', key);

const generateX25519Pair = async () => {
  return await window.crypto.subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
};

const generateEd25519Pair = async () => {
  return await window.crypto.subtle.generateKey({name: 'Ed25519'}, true, ['sign', 'verify']);
};

const signPayload = async (privateKey, payloadText) => {
  const signature = await window.crypto.subtle.sign('Ed25519', privateKey, textEncoder.encode(payloadText));
  return toBase64(signature);
};

const exportKeyPair = async (keyPair) => {
  return {
    publicJwk: await exportPublicJwk(keyPair.publicKey),
    privateJwk: await exportPrivateJwk(keyPair.privateKey),
  };
};

const buildOneTimePrekey = async (keyId) => {
  const keyPair = await generateX25519Pair();
  const exported = await exportKeyPair(keyPair);
  return {
    keyId,
    publicKey: JSON.stringify(exported.publicJwk),
    privateKey: exported.privateJwk,
  };
};

export const createDefaultDeviceName = () => {
  const platform = navigator.platform || 'Browser';
  return `${platform} Browser`;
};

export const generateDeviceState = async (existingState = null) => {
  ensureSubtleCrypto();

  const deviceId = existingState?.deviceId || window.crypto.randomUUID();
  const deviceName = existingState?.deviceName || createDefaultDeviceName();
  const platform = navigator.userAgentData?.platform || navigator.platform || 'unknown';
  const registrationId = existingState?.registrationId || Math.floor(Math.random() * 2147483647);
  const nextSignedPrekeyId = existingState?.nextSignedPrekeyId || 1;
  const nextOneTimePrekeyId = existingState?.nextOneTimePrekeyId || 1;

  const identityKeyPair = await exportKeyPair(await generateX25519Pair());
  const signingKeyPair = await exportKeyPair(await generateEd25519Pair());
  const signedPrekeyPair = await exportKeyPair(await generateX25519Pair());
  const signedPrekeyPublic = JSON.stringify(signedPrekeyPair.publicJwk);
  const signedPrekeySignature = await (async () => {
    const importedSigningPrivateKey = await window.crypto.subtle.importKey(
      'jwk',
      signingKeyPair.privateJwk,
      {name: 'Ed25519'},
      true,
      ['sign']
    );
    return await signPayload(importedSigningPrivateKey, signedPrekeyPublic);
  })();

  const oneTimePrekeys = [];
  for (let keyId = nextOneTimePrekeyId; keyId < nextOneTimePrekeyId + 20; keyId += 1) {
    oneTimePrekeys.push(await buildOneTimePrekey(keyId));
  }

  return {
    version: 1,
    deviceId,
    deviceName,
    platform,
    registrationId,
    identityKeyPair,
    signingKeyPair,
    signedPrekey: {
      keyId: nextSignedPrekeyId,
      publicKey: signedPrekeyPublic,
      privateKey: signedPrekeyPair.privateJwk,
      signature: signedPrekeySignature,
    },
    oneTimePrekeys,
    nextSignedPrekeyId: nextSignedPrekeyId + 1,
    nextOneTimePrekeyId: nextOneTimePrekeyId + oneTimePrekeys.length,
    registeredAt: existingState?.registeredAt || null,
  };
};

export const buildBootstrapPayload = (deviceState) => {
  return {
    device_id: deviceState.deviceId,
    device_name: deviceState.deviceName,
    platform: deviceState.platform,
    registration_id: deviceState.registrationId,
    identity_key_public: JSON.stringify(deviceState.identityKeyPair.publicJwk),
    signing_key_public: JSON.stringify(deviceState.signingKeyPair.publicJwk),
    signed_prekey: {
      key_id: deviceState.signedPrekey.keyId,
      public_key: deviceState.signedPrekey.publicKey,
      signature: deviceState.signedPrekey.signature,
    },
    one_time_prekeys: deviceState.oneTimePrekeys.map((prekey) => ({
      key_id: prekey.keyId,
      public_key: prekey.publicKey,
    })),
  };
};

export const buildPrekeyRefreshPayload = async (deviceState, count = 20) => {
  const oneTimePrekeys = [];
  for (let keyId = deviceState.nextOneTimePrekeyId; keyId < deviceState.nextOneTimePrekeyId + count; keyId += 1) {
    oneTimePrekeys.push(await buildOneTimePrekey(keyId));
  }

  return {
    payload: {
      one_time_prekeys: oneTimePrekeys.map((prekey) => ({
        key_id: prekey.keyId,
        public_key: prekey.publicKey,
      })),
    },
    updatedState: {
      ...deviceState,
      oneTimePrekeys: [...deviceState.oneTimePrekeys, ...oneTimePrekeys],
      nextOneTimePrekeyId: deviceState.nextOneTimePrekeyId + oneTimePrekeys.length,
    },
  };
};
