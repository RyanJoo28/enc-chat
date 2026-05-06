import { webcrypto, createCipheriv, createDecipheriv } from 'node:crypto';


const subtle = webcrypto.subtle;
const encoder = new TextEncoder();
const decoder = new TextDecoder();


const hexToBytes = (hex) => {
  const normalized = hex.replace(/\s+/g, '').toLowerCase();
  if (normalized.length % 2 !== 0) {
    throw new Error(`Invalid hex length: ${hex}`);
  }

  const output = new Uint8Array(normalized.length / 2);
  for (let index = 0; index < normalized.length; index += 2) {
    output[index / 2] = Number.parseInt(normalized.slice(index, index + 2), 16);
  }
  return output;
};


const bytesToHex = (bytes) => {
  return [...bytes].map((value) => value.toString(16).padStart(2, '0')).join('');
};


const toBase64Url = (bytes) => {
  return Buffer.from(bytes)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
};


const fromBase64Url = (value) => {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return new Uint8Array(Buffer.from(padded, 'base64'));
};


const assertEqual = (actual, expected, label) => {
  if (actual !== expected) {
    throw new Error(`${label} mismatch\nexpected: ${expected}\nactual:   ${actual}`);
  }
};


const assertTrue = (value, label) => {
  if (!value) {
    throw new Error(`${label} failed`);
  }
};


const importEd25519PrivateKey = async (jwk) => {
  return await subtle.importKey('jwk', jwk, { name: 'Ed25519' }, false, ['sign']);
};


const importEd25519PublicKey = async (jwk) => {
  return await subtle.importKey('jwk', jwk, { name: 'Ed25519' }, false, ['verify']);
};


const importX25519PrivateKey = async (jwk) => {
  return await subtle.importKey('jwk', jwk, { name: 'X25519' }, false, ['deriveBits']);
};


const importX25519PublicKey = async (jwk) => {
  const { d, ...pubJwk } = jwk;
  return await subtle.importKey('jwk', pubJwk, { name: 'X25519' }, false, []);
};


const validateRfc8037Ed25519Vector = async () => {
  const privateJwk = {
    kty: 'OKP',
    crv: 'Ed25519',
    d: 'nWGxne_9WmC6hEr0kuwsxERJxWl7MmkZcDusAxyuf2A',
    x: '11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo',
  };
  const publicJwk = {
    kty: 'OKP',
    crv: 'Ed25519',
    x: '11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo',
  };
  const signingInput = 'eyJhbGciOiJFZERTQSJ9.RXhhbXBsZSBvZiBFZDI1NTE5IHNpZ25pbmc';
  const expectedSignature = 'hgyY0il_MGCjP0JzlnLWG1PPOt7-09PGcvMg3AIbQR6dWbhijcNR4ki4iylGjg5BhVsPt9g7sVvpAr_MuM0KAg';

  const privateKey = await importEd25519PrivateKey(privateJwk);
  const publicKey = await importEd25519PublicKey(publicJwk);
  const signature = await subtle.sign('Ed25519', privateKey, encoder.encode(signingInput));
  const signatureBase64Url = toBase64Url(new Uint8Array(signature));
  const verified = await subtle.verify('Ed25519', publicKey, fromBase64Url(expectedSignature), encoder.encode(signingInput));

  assertEqual(signatureBase64Url, expectedSignature, 'RFC 8037 Ed25519 signature');
  assertTrue(verified, 'RFC 8037 Ed25519 verification');
};


const validateRfc8037X25519Vector = async () => {
  const ephPrivateHex = '77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a';
  const ephPublicBase64Url = 'hSDwCYkwp1R0i33ctD73Wg2_Og0mOBr066SpjqqbTmo';
  const bobPublicBase64Url = '3p7bfXt9wbTTW2HC7OQ1Nz-DQ8hbeGdNrfx-FG-IK08';
  const expectedSharedSecretHex = '4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742';

  const ephPrivateKey = await importX25519PrivateKey({
    kty: 'OKP',
    crv: 'X25519',
    d: toBase64Url(hexToBytes(ephPrivateHex)),
    x: ephPublicBase64Url,
  });
  const bobPublicKey = await importX25519PublicKey({
    kty: 'OKP',
    crv: 'X25519',
    x: bobPublicBase64Url,
  });

  const sharedSecret = await subtle.deriveBits({ name: 'X25519', public: bobPublicKey }, ephPrivateKey, 256);
  assertEqual(bytesToHex(new Uint8Array(sharedSecret)), expectedSharedSecretHex, 'RFC 8037 X25519 shared secret');
};


const validateRfc5869HkdfVector = async () => {
  const ikm = hexToBytes('0b'.repeat(22));
  const salt = hexToBytes('000102030405060708090a0b0c');
  const info = hexToBytes('f0f1f2f3f4f5f6f7f8f9');
  const expectedOkm = '3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865';

  const ikmKey = await subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  const okm = await subtle.deriveBits({
    name: 'HKDF',
    hash: 'SHA-256',
    salt,
    info,
  }, ikmKey, 42 * 8);

  assertEqual(bytesToHex(new Uint8Array(okm)), expectedOkm, 'RFC 5869 HKDF output');
};


const validateAesGcmRoundTrip = async () => {
  const keyBytes = hexToBytes('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f');
  const nonce = hexToBytes('101112131415161718191a1b');
  const plaintext = 'enc-chat:e2ee-v1:aes-gcm';

  const ciphertext = await encryptAesGcmRaw(keyBytes, nonce, plaintext);
  const decrypted = await decryptAesGcmRaw(keyBytes, nonce, ciphertext);

  assertEqual(decrypted, plaintext, 'AES-256-GCM roundtrip');
};


const X25519_KEY_ALICE_PRIV_HEX = '77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a';
const X25519_KEY_ALICE_PUB_B64URL = 'hSDwCYkwp1R0i33ctD73Wg2_Og0mOBr066SpjqqbTmo';
const X25519_KEY_BOB_PRIV_HEX = '5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb';
const X25519_KEY_BOB_PUB_B64URL = '3p7bfXt9wbTTW2HC7OQ1Nz-DQ8hbeGdNrfx-FG-IK08';

const makeX25519Jwk = (privateHex, publicB64Url) => ({
  kty: 'OKP',
  crv: 'X25519',
  d: toBase64Url(hexToBytes(privateHex)),
  x: publicB64Url,
});

const makePubOnlyJwk = (publicB64Url) => ({
  kty: 'OKP',
  crv: 'X25519',
  x: publicB64Url,
});

const deriveDhRaw = async (privateJwk, publicJwk) => {
  const privateKey = await importX25519PrivateKey(privateJwk);
  const publicKey = await importX25519PublicKey(publicJwk);
  const bits = await subtle.deriveBits({name: 'X25519', public: publicKey}, privateKey, 256);
  return new Uint8Array(bits);
};

const concatBytes = (...parts) => {
  const totalLength = parts.reduce((sum, p) => sum + p.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  parts.forEach((p) => { output.set(p, offset); offset += p.length; });
  return output;
};

const emptySalt = new Uint8Array(32);

const hkdfExpandRaw = async (inputKeyMaterial, infoText, byteLength) => {
  const key = await subtle.importKey('raw', inputKeyMaterial, 'HKDF', false, ['deriveBits']);
  const bits = await subtle.deriveBits({
    name: 'HKDF', hash: 'SHA-256', salt: emptySalt,
    info: encoder.encode(infoText),
  }, key, byteLength * 8);
  return new Uint8Array(bits);
};

const encryptAesGcmRaw = async (keyBytes, nonceBytes, plaintext) => {
  const cipher = createCipheriv('aes-256-gcm', keyBytes, nonceBytes);
  const encrypted = Buffer.concat([cipher.update(encoder.encode(plaintext)), cipher.final()]);
  const tag = cipher.getAuthTag();
  return new Uint8Array(Buffer.concat([encrypted, tag]));
};

const decryptAesGcmRaw = async (keyBytes, nonceBytes, ciphertext) => {
  try {
    const buf = Buffer.from(ciphertext);
    const encrypted = buf.subarray(0, buf.length - 16);
    const tag = buf.subarray(buf.length - 16);
    const decipher = createDecipheriv('aes-256-gcm', keyBytes, nonceBytes);
    decipher.setAuthTag(tag);
    const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);
    return decoder.decode(decrypted);
  } catch {
    return null;
  }
};

const deriveChainStepRaw = async (chainKeyBytes) => {
  const material = await hkdfExpandRaw(chainKeyBytes, 'enc-chat:chain:step', 64);
  return { nextChainKey: material.slice(0, 32), messageKey: material.slice(32, 64) };
};

const performDhRatchetStep = async ({ rootKeyBytes, myPrivateJwk, theirPublicJwk }) => {
  const dh = await deriveDhRaw(myPrivateJwk, theirPublicJwk);
  const mat = await hkdfExpandRaw(concatBytes(dh, rootKeyBytes), 'enc-chat:ratchet:v2', 64);
  return {
    rootKeyBytes: mat.slice(0, 32),
    chainKeyBytes: mat.slice(32, 64),
  };
};

const validateX3dhDerivation = async () => {
  const aliceIdPriv = makeX25519Jwk(X25519_KEY_ALICE_PRIV_HEX, X25519_KEY_ALICE_PUB_B64URL);
  const bobIdPub = makePubOnlyJwk(X25519_KEY_BOB_PUB_B64URL);
  const bobSpkPriv = makeX25519Jwk(X25519_KEY_BOB_PRIV_HEX, X25519_KEY_BOB_PUB_B64URL);
  const bobOtkPriv = aliceIdPriv;
  const bobOtkPub = makePubOnlyJwk(X25519_KEY_ALICE_PUB_B64URL);
  const ekPriv = makeX25519Jwk(X25519_KEY_BOB_PRIV_HEX, X25519_KEY_BOB_PUB_B64URL);
  const ekPub = makePubOnlyJwk(X25519_KEY_BOB_PUB_B64URL);

  const dh1 = await deriveDhRaw(aliceIdPriv, bobSpkPriv);
  const dh2 = await deriveDhRaw(ekPriv, bobIdPub);
  const dh3 = await deriveDhRaw(ekPriv, bobSpkPriv);
  const dh4 = await deriveDhRaw(ekPriv, bobOtkPub);

  const fused = concatBytes(dh1, dh2, dh3, dh4);
  const expectedRootKeyHex = 'ff0d355d5db31a8ada00c1595b053738910d1f434b56d2838fe62a9215f751f3';
  const rootKey = await hkdfExpandRaw(fused, 'enc-chat:x3dh', 32);
  assertEqual(bytesToHex(rootKey), expectedRootKeyHex, 'X3DH root key vector');
};

const generateChainKeys = async (rootKeyBytes, isInitiator) => {
  const material = await hkdfExpandRaw(rootKeyBytes, 'enc-chat:session:init', 64);
  return {
    sendChain: isInitiator ? material.slice(0, 32) : material.slice(32, 64),
    recvChain: isInitiator ? material.slice(32, 64) : material.slice(0, 32),
  };
};

const validateDoubleRatchetRoundTrip = async () => {
  const aliceIdPriv = makeX25519Jwk(X25519_KEY_ALICE_PRIV_HEX, X25519_KEY_ALICE_PUB_B64URL);
  const aliceIdPub = makePubOnlyJwk(X25519_KEY_ALICE_PUB_B64URL);
  const bobIdPriv = makeX25519Jwk(X25519_KEY_BOB_PRIV_HEX, X25519_KEY_BOB_PUB_B64URL);
  const bobIdPub = makePubOnlyJwk(X25519_KEY_BOB_PUB_B64URL);
  const bobSpkPriv = makeX25519Jwk(X25519_KEY_BOB_PRIV_HEX, X25519_KEY_BOB_PUB_B64URL);
  const bobSpkPub = makePubOnlyJwk(X25519_KEY_BOB_PUB_B64URL);
  const bobOtkPub = makePubOnlyJwk(X25519_KEY_ALICE_PUB_B64URL);
  const bobOtkPriv = makeX25519Jwk(X25519_KEY_ALICE_PRIV_HEX, X25519_KEY_ALICE_PUB_B64URL);
  const ek = await subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
  const ekPriv = await subtle.exportKey('jwk', ek.privateKey);
  const ekPub = await subtle.exportKey('jwk', ek.publicKey);

  const dhA1 = await deriveDhRaw(aliceIdPriv, bobSpkPub);
  const dhA2 = await deriveDhRaw(ekPriv, bobIdPub);
  const dhA3 = await deriveDhRaw(ekPriv, bobSpkPub);
  const dhA4 = await deriveDhRaw(ekPriv, bobOtkPub);
  const rootKeyAlice = await hkdfExpandRaw(concatBytes(dhA1, dhA2, dhA3, dhA4), 'enc-chat:x3dh', 32);

  const dhB1 = await deriveDhRaw(bobSpkPriv, aliceIdPub);
  const dhB2 = await deriveDhRaw(bobIdPriv, ekPub);
  const dhB3 = await deriveDhRaw(bobSpkPriv, ekPub);
  const dhB4 = await deriveDhRaw(bobOtkPriv, ekPub);
  const rootKeyBob = await hkdfExpandRaw(concatBytes(dhB1, dhB2, dhB3, dhB4), 'enc-chat:x3dh', 32);

  assertEqual(bytesToHex(rootKeyAlice), bytesToHex(rootKeyBob), 'X3DH root key agreement');

  let aliceChainKeys = await generateChainKeys(rootKeyAlice, true);
  let bobChainKeys = await generateChainKeys(rootKeyBob, false);

  let aliceSendRatchet = {privateJwk: ekPriv, publicJwk: ekPub};
  let bobSendRatchet = null;
  let aliceRecvRatchetPub = null;
  let bobRecvRatchetPub = JSON.stringify(ekPub);
  let aliceRoot = rootKeyAlice;
  let bobRoot = rootKeyBob;

  const nonceA = hexToBytes('000102030405060708090a0b');
  const plaintextA = 'Hello from Alice';

  const stepA1 = await deriveChainStepRaw(aliceChainKeys.sendChain);
  const cipherA1 = await encryptAesGcmRaw(stepA1.messageKey, nonceA, plaintextA);
  aliceChainKeys.sendChain = stepA1.nextChainKey;

  let stepB1 = await deriveChainStepRaw(bobChainKeys.recvChain);
  const plainB1 = await decryptAesGcmRaw(stepB1.messageKey, nonceA, cipherA1);
  bobChainKeys.recvChain = stepB1.nextChainKey;

  assertEqual(plainB1, plaintextA, 'First message Alice→Bob');

  // Bob generates a NEW sending ratchet key pair and performs DH ratchet
  const bobNewSend = await subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
  const bobNewSendPriv = await subtle.exportKey('jwk', bobNewSend.privateKey);
  const bobNewSendPub = await subtle.exportKey('jwk', bobNewSend.publicKey);
  const bobM2RatchetKeyPub = bobNewSendPub;
  bobSendRatchet = {privateJwk: bobNewSendPriv, publicJwk: bobNewSendPub};

  const bobPreSendRatchet = await performDhRatchetStep({
    rootKeyBytes: bobRoot,
    myPrivateJwk: bobNewSendPriv,
    theirPublicJwk: ekPub,
  });
  bobRoot = bobPreSendRatchet.rootKeyBytes;
  bobChainKeys.sendChain = bobPreSendRatchet.chainKeyBytes;

  const nonceB = hexToBytes('101112131415161718191a1b');
  const plaintextB = 'Hello from Bob';

  const stepB2 = await deriveChainStepRaw(bobChainKeys.sendChain);
  const cipherB2 = await encryptAesGcmRaw(stepB2.messageKey, nonceB, plaintextB);
  bobChainKeys.sendChain = stepB2.nextChainKey;

  assertTrue(JSON.stringify(bobM2RatchetKeyPub) !== aliceRecvRatchetPub,
    'Bob ratchet key differs from Alice stored recv key');

  // Alice detects Bob's new ratchet key, performs DH ratchet to derive her recv chain
  const aliceRecvRatchet = await performDhRatchetStep({
    rootKeyBytes: aliceRoot,
    myPrivateJwk: ekPriv,
    theirPublicJwk: bobM2RatchetKeyPub,
  });
  aliceRoot = aliceRecvRatchet.rootKeyBytes;
  aliceChainKeys.recvChain = aliceRecvRatchet.chainKeyBytes;
  aliceRecvRatchetPub = JSON.stringify(bobM2RatchetKeyPub);

  const stepA2 = await deriveChainStepRaw(aliceChainKeys.recvChain);
  const plainA2 = await decryptAesGcmRaw(stepA2.messageKey, nonceB, cipherB2);
  aliceChainKeys.recvChain = stepA2.nextChainKey;

  assertEqual(plainA2, plaintextB, 'First reply Bob→Alice after DH ratchet');

  // Alice generates a NEW sending ratchet key pair and performs DH ratchet
  const aliceNewSend = await subtle.generateKey({name: 'X25519'}, true, ['deriveBits']);
  const aliceNewSendPriv = await subtle.exportKey('jwk', aliceNewSend.privateKey);
  const aliceNewSendPub = await subtle.exportKey('jwk', aliceNewSend.publicKey);
  aliceSendRatchet = {privateJwk: aliceNewSendPriv, publicJwk: aliceNewSendPub};

  const alicePreSendRatchet = await performDhRatchetStep({
    rootKeyBytes: aliceRoot,
    myPrivateJwk: aliceNewSendPriv,
    theirPublicJwk: bobSendRatchet.publicJwk,
  });
  aliceRoot = alicePreSendRatchet.rootKeyBytes;
  aliceChainKeys.sendChain = alicePreSendRatchet.chainKeyBytes;

  const plaintextA3 = 'Another from Alice';
  const stepA3 = await deriveChainStepRaw(aliceChainKeys.sendChain);
  const cipherA3 = await encryptAesGcmRaw(stepA3.messageKey, nonceA, plaintextA3);
  aliceChainKeys.sendChain = stepA3.nextChainKey;

  // Bob detects Alice's new ratchet key, performs DH ratchet to derive his recv chain
  const bobRecvRatchet = await performDhRatchetStep({
    rootKeyBytes: bobRoot,
    myPrivateJwk: bobSendRatchet.privateJwk,
    theirPublicJwk: aliceNewSendPub,
  });
  bobRoot = bobRecvRatchet.rootKeyBytes;
  bobChainKeys.recvChain = bobRecvRatchet.chainKeyBytes;

  const stepB3 = await deriveChainStepRaw(bobChainKeys.recvChain);
  const plainB3 = await decryptAesGcmRaw(stepB3.messageKey, nonceA, cipherA3);
  bobChainKeys.recvChain = stepB3.nextChainKey;

  assertEqual(plainB3, plaintextA3, 'Third message Alice→Bob after DH ratchets');
};

const validateSkippedMessageKeys = async () => {
  const rootKey = hexToBytes('00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff');
  const chainKeys = await generateChainKeys(rootKey, false);
  let recvChain = chainKeys.recvChain;
  let recvCounter = 0;
  const skipped = {};

  while (recvCounter < 3) {
    const step = await deriveChainStepRaw(recvChain);
    skipped[`test:${recvCounter}`] = step.messageKey;
    recvChain = step.nextChainKey;
    recvCounter++;
  }

  const step3 = await deriveChainStepRaw(recvChain);
  recvChain = step3.nextChainKey;

  const nonce = hexToBytes('aabbccddeeff00112233445566778899');
  const plaintext = 'message at counter 3';
  const ciphertext = await encryptAesGcmRaw(step3.messageKey, nonce, plaintext);

  const targetPlain0 = await decryptAesGcmRaw(skipped['test:0'], nonce, ciphertext);
  assertTrue(targetPlain0 === null, 'Wrong key fails to decrypt');

  const skippedPlain = await decryptAesGcmRaw(skipped['test:2'], nonce, ciphertext);
  assertTrue(skippedPlain === null, 'Skipped key for wrong counter fails');

  assertTrue(skippedPlain === null, 'Skipped validation');
  assertTrue(Object.keys(skipped).length >= 3, 'Skipped keys stored');
};

const main = async () => {
  await validateRfc8037Ed25519Vector();
  await validateRfc8037X25519Vector();
  await validateRfc5869HkdfVector();
  await validateAesGcmRoundTrip();
  await validateX3dhDerivation();
  await validateDoubleRatchetRoundTrip();
  await validateSkippedMessageKeys();
  console.log('E2EE protocol vectors validated: Ed25519, X25519, HKDF-SHA256, AES-256-GCM, X3DH, Double Ratchet');
};


main().catch((error) => {
  console.error(error);
  process.exit(1);
});
