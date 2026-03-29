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
  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index);
  }
  return output;
};

const arrayBufferToHex = (buffer) => {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, '0')).join('');
};

export const buildEncryptedAttachmentDescriptor = ({blobId, file, fileKeyBase64, nonceBase64}) => ({
  kind: 'e2ee_attachment',
  version: 'e2ee_v1',
  blob_id: blobId,
  file_name: file.name,
  mime_type: file.type || 'application/octet-stream',
  file_size: file.size,
  file_key: fileKeyBase64,
  file_nonce: nonceBase64,
});

export const parseEncryptedAttachmentDescriptor = (value) => {
  if (!value || typeof value !== 'string') return null;

  try {
    const parsed = JSON.parse(value);
    if (parsed?.kind !== 'e2ee_attachment' || !parsed.blob_id || !parsed.file_key || !parsed.file_nonce) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

export const encryptAttachmentFile = async (file) => {
  const plaintext = await file.arrayBuffer();
  const fileKey = window.crypto.getRandomValues(new Uint8Array(32));
  const nonce = window.crypto.getRandomValues(new Uint8Array(12));
  const cryptoKey = await window.crypto.subtle.importKey('raw', fileKey, 'AES-GCM', false, ['encrypt']);
  const ciphertext = await window.crypto.subtle.encrypt({name: 'AES-GCM', iv: nonce}, cryptoKey, plaintext);
  const ciphertextBytes = new Uint8Array(ciphertext);
  const ciphertextHash = await window.crypto.subtle.digest('SHA-256', ciphertextBytes);

  return {
    ciphertextBytes,
    ciphertextSha256: arrayBufferToHex(ciphertextHash),
    ciphertextSize: ciphertextBytes.byteLength,
    fileKeyBase64: toBase64(fileKey),
    nonceBase64: toBase64(nonce),
    mimeType: file.type || 'application/octet-stream',
  };
};

export const decryptAttachmentCiphertext = async ({ciphertextBytes, fileKeyBase64, nonceBase64}) => {
  const keyBytes = fromBase64(fileKeyBase64);
  const nonceBytes = fromBase64(nonceBase64);
  const cryptoKey = await window.crypto.subtle.importKey('raw', keyBytes, 'AES-GCM', false, ['decrypt']);
  const plaintext = await window.crypto.subtle.decrypt(
    {name: 'AES-GCM', iv: nonceBytes},
    cryptoKey,
    ciphertextBytes,
  );
  return new Uint8Array(plaintext);
};
