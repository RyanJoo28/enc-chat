import {loadGroupSenderKeyState, saveGroupSenderKeyState} from './storage';

const encoder = new TextEncoder();
const decoder = new TextDecoder();

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

export const createGroupSenderKeyState = async ({scopeKey, groupId, epoch, senderDeviceId}) => {
  const keyBytes = window.crypto.getRandomValues(new Uint8Array(32));
  const state = {
    groupId,
    epoch,
    senderDeviceId,
    senderKeyBase64: toBase64(keyBytes),
  };
  await saveGroupSenderKeyState(scopeKey, groupId, epoch, senderDeviceId, state);
  return state;
};

export const saveReceivedGroupSenderKeyState = async ({scopeKey, groupId, epoch, senderDeviceId, senderKeyBase64}) => {
  const state = {groupId, epoch, senderDeviceId, senderKeyBase64};
  await saveGroupSenderKeyState(scopeKey, groupId, epoch, senderDeviceId, state);
  return state;
};

export const loadGroupSenderKey = async ({scopeKey, groupId, epoch, senderDeviceId}) => {
  return await loadGroupSenderKeyState(scopeKey, groupId, epoch, senderDeviceId);
};

export const buildSenderKeyDistributionPayload = ({groupId, epoch, senderDeviceId, senderKeyBase64}) => {
  return JSON.stringify({
    kind: 'group_sender_key_distribution',
    version: 'e2ee_v1',
    group_id: groupId,
    epoch,
    sender_device_id: senderDeviceId,
    sender_key: senderKeyBase64,
  });
};

export const parseSenderKeyDistributionPayload = (value) => {
  const parsed = typeof value === 'string' ? JSON.parse(value) : value;
  if (parsed?.kind !== 'group_sender_key_distribution') {
    return null;
  }
  return parsed;
};

const importAesKey = async (senderKeyBase64, usage) => {
  return await window.crypto.subtle.importKey('raw', fromBase64(senderKeyBase64), 'AES-GCM', false, [usage]);
};

export const encryptGroupSenderKeyMessage = async ({groupId, epoch, senderDeviceId, senderKeyBase64, plaintext}) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const aesKey = await importAesKey(senderKeyBase64, 'encrypt');
  const ciphertext = await window.crypto.subtle.encrypt({name: 'AES-GCM', iv}, aesKey, encoder.encode(plaintext));
  return {
    version: 'e2ee_v1',
    mode: 'group_sender_key',
    group_id: groupId,
    epoch,
    sender_device_id: senderDeviceId,
    nonce: toBase64(iv),
    ciphertext: toBase64(ciphertext),
  };
};

export const decryptGroupSenderKeyMessage = async ({senderKeyBase64, envelope}) => {
  const aesKey = await importAesKey(senderKeyBase64, 'decrypt');
  const plaintext = await window.crypto.subtle.decrypt(
    {name: 'AES-GCM', iv: fromBase64(envelope.nonce)},
    aesKey,
    fromBase64(envelope.ciphertext),
  );
  return decoder.decode(plaintext);
};
