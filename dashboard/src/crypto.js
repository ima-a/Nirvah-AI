export async function generateKey() {
  return crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt', 'decrypt']
  );
}

export async function encryptRecord(data, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(JSON.stringify(data));
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    encoded
  );
  return {
    iv: Array.from(iv),
    ciphertext: Array.from(new Uint8Array(ciphertext)),
  };
}

export async function decryptRecord(encrypted, key) {
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: new Uint8Array(encrypted.iv) },
    key,
    new Uint8Array(encrypted.ciphertext)
  );
  return JSON.parse(new TextDecoder().decode(decrypted));
}

// Generate a key once per session and store in memory
// (for persistent storage across sessions, use the Credential Management API)
let _sessionKey = null;
export async function getSessionKey() {
  if (!_sessionKey) {
    _sessionKey = await generateKey();
  }
  return _sessionKey;
}
