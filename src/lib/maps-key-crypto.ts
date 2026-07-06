import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12;

function getEncryptionKey(): Buffer {
  const secret =
    process.env.MAPS_KEY_ENCRYPTION_SECRET?.trim() ||
    process.env.AUTH_SECRET?.trim();

  if (!secret) {
    throw new Error(
      'MAPS_KEY_ENCRYPTION_SECRET (or AUTH_SECRET fallback) must be set.'
    );
  }

  return createHash('sha256').update(secret).digest();
}

export function encryptMapsApiKey(apiKey: string) {
  const iv = randomBytes(IV_LENGTH);
  const cipher = createCipheriv(ALGORITHM, getEncryptionKey(), iv);

  const encrypted = Buffer.concat([
    cipher.update(apiKey, 'utf8'),
    cipher.final(),
  ]);

  return {
    cipherText: encrypted.toString('base64'),
    iv: iv.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'),
  };
}

export function decryptMapsApiKey(payload: {
  cipherText: string;
  iv: string;
  tag: string;
}) {
  const decipher = createDecipheriv(
    ALGORITHM,
    getEncryptionKey(),
    Buffer.from(payload.iv, 'base64')
  );

  decipher.setAuthTag(Buffer.from(payload.tag, 'base64'));

  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(payload.cipherText, 'base64')),
    decipher.final(),
  ]);

  return decrypted.toString('utf8');
}

