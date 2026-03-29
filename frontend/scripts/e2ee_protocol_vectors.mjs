import { webcrypto } from 'node:crypto';


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
  return await subtle.importKey('jwk', jwk, { name: 'X25519' }, false, []);
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

  const key = await subtle.importKey('raw', keyBytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
  const ciphertext = await subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, encoder.encode(plaintext));
  const decrypted = await subtle.decrypt({ name: 'AES-GCM', iv: nonce }, key, ciphertext);

  assertEqual(decoder.decode(decrypted), plaintext, 'AES-256-GCM roundtrip');
};


const main = async () => {
  await validateRfc8037Ed25519Vector();
  await validateRfc8037X25519Vector();
  await validateRfc5869HkdfVector();
  await validateAesGcmRoundTrip();
  console.log('E2EE protocol vectors validated: Ed25519, X25519, HKDF-SHA256, AES-256-GCM');
};


main().catch((error) => {
  console.error(error);
  process.exit(1);
});
