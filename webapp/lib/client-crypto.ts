/**
 * Project Nobi — Client-Side Encryption Module
 * =============================================
 * AES-256-GCM encryption/decryption using the native Web Crypto API.
 * Keys are derived from user passphrase via PBKDF2. No external libraries needed.
 * Zero data leaves the browser unencrypted when privacy mode is enabled.
 */

// ─── Types ──────────────────────────────────────────────────────────────────

export interface EncryptedPayload {
  /** Base64-encoded ciphertext */
  ciphertext: string;
  /** Base64-encoded 12-byte IV */
  iv: string;
  /** Base64-encoded 16-byte salt (for PBKDF2) */
  salt: string;
  /** Algorithm identifier */
  algorithm: "AES-GCM-256";
  /** PBKDF2 iteration count */
  iterations: number;
}

export interface CryptoKeySet {
  /** Derived AES-GCM key for this session */
  key: CryptoKey;
  /** Salt used for key derivation (persist for decryption) */
  salt: Uint8Array<ArrayBuffer>;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const PBKDF2_ITERATIONS = 100_000;
const KEY_LENGTH = 256;
const IV_LENGTH = 12; // 96-bit IV for AES-GCM
const SALT_LENGTH = 16;
const ALGORITHM = "AES-GCM-256" as const;

// LocalStorage key for persisting the device key salt
const DEVICE_SALT_KEY = "nobi_device_salt_v1";

// ─── Utilities ───────────────────────────────────────────────────────────────

/**
 * TypeScript strict mode workaround: Web Crypto APIs require Uint8Array<ArrayBuffer>
 * but getRandomValues / TextEncoder return Uint8Array<ArrayBufferLike>.
 * This helper copies bytes into a fresh Uint8Array backed by a plain ArrayBuffer.
 */
function toArrayBuffer(data: Uint8Array): Uint8Array<ArrayBuffer> {
  const ab = new ArrayBuffer(data.byteLength);
  new Uint8Array(ab).set(data);
  return new Uint8Array(ab) as Uint8Array<ArrayBuffer>;
}

function toBase64(buffer: ArrayBuffer | Uint8Array<ArrayBuffer>): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(b64: string): Uint8Array<ArrayBuffer> {
  const bytes = atob(b64).split("").map((c) => c.charCodeAt(0));
  const ab = new ArrayBuffer(bytes.length);
  const view = new Uint8Array(ab) as Uint8Array<ArrayBuffer>;
  view.set(bytes);
  return view;
}

// ─── Key Derivation ──────────────────────────────────────────────────────────

/**
 * Derive an AES-256-GCM key from a passphrase using PBKDF2.
 * If no passphrase is provided, uses a device-bound key stored in localStorage.
 */
export async function deriveKey(
  passphrase: string,
  salt?: Uint8Array<ArrayBuffer>
): Promise<CryptoKeySet> {
  const rawSalt = salt ?? crypto.getRandomValues(new Uint8Array(SALT_LENGTH));
  // Ensure we have a plain ArrayBuffer-backed Uint8Array for Web Crypto compatibility
  const resolvedSalt = toArrayBuffer(rawSalt);

  const baseKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );

  const key = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: resolvedSalt,
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    baseKey,
    { name: "AES-GCM", length: KEY_LENGTH },
    false,
    ["encrypt", "decrypt"]
  );

  return { key, salt: resolvedSalt };
}

/**
 * Get or create a device-bound key derived from a stable device identifier.
 * Falls back to a random passphrase stored in localStorage.
 * This is used when no user passphrase is set (auto-mode).
 */
export async function getOrCreateDeviceKey(): Promise<CryptoKeySet> {
  let saltB64 = localStorage.getItem(DEVICE_SALT_KEY);
  let salt: Uint8Array<ArrayBuffer>;

  if (saltB64) {
    salt = fromBase64(saltB64);
  } else {
    salt = toArrayBuffer(crypto.getRandomValues(new Uint8Array(SALT_LENGTH)));
    localStorage.setItem(DEVICE_SALT_KEY, toBase64(salt.buffer));
  }

  // Derive from a device fingerprint (stable but not secret)
  const deviceId = [
    navigator.userAgent,
    navigator.language,
    screen.width,
    screen.height,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
  ].join("|");

  return deriveKey(deviceId, salt);
}

// ─── Encrypt ─────────────────────────────────────────────────────────────────

/**
 * Encrypt a plaintext string using AES-256-GCM.
 *
 * @param plaintext - Raw string to encrypt
 * @param keySet - Key set from deriveKey() or getOrCreateDeviceKey()
 * @returns EncryptedPayload with all needed data for decryption
 */
export async function encrypt(
  plaintext: string,
  keySet: CryptoKeySet
): Promise<EncryptedPayload> {
  const iv = toArrayBuffer(crypto.getRandomValues(new Uint8Array(IV_LENGTH)));
  const encoded = toArrayBuffer(new TextEncoder().encode(plaintext));

  const ciphertextBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    keySet.key,
    encoded
  );

  return {
    ciphertext: toBase64(ciphertextBuffer),
    iv: toBase64(iv),
    salt: toBase64(keySet.salt),
    algorithm: ALGORITHM,
    iterations: PBKDF2_ITERATIONS,
  };
}

// ─── Decrypt ─────────────────────────────────────────────────────────────────

/**
 * Decrypt an EncryptedPayload back to plaintext.
 *
 * @param payload - The encrypted payload (from encrypt())
 * @param passphrase - The passphrase used during encryption
 * @returns Decrypted plaintext string
 */
export async function decrypt(
  payload: EncryptedPayload,
  passphrase: string
): Promise<string> {
  if (payload.algorithm !== ALGORITHM) {
    throw new Error(`Unsupported algorithm: ${payload.algorithm}`);
  }

  const salt = fromBase64(payload.salt);
  const iv = fromBase64(payload.iv);
  const ciphertext = fromBase64(payload.ciphertext);

  const { key } = await deriveKey(passphrase, salt);

  const decryptedBuffer = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    ciphertext
  );

  return new TextDecoder().decode(decryptedBuffer);
}

/**
 * Decrypt using the device key (auto-mode, no user passphrase).
 */
export async function decryptWithDeviceKey(
  payload: EncryptedPayload
): Promise<string> {
  const salt = fromBase64(payload.salt);
  const iv = fromBase64(payload.iv);
  const ciphertext = fromBase64(payload.ciphertext);

  const keySet = await getOrCreateDeviceKey();

  const decryptedBuffer = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    keySet.key,
    ciphertext
  );

  return new TextDecoder().decode(decryptedBuffer);
}

// ─── Convenience ─────────────────────────────────────────────────────────────

/**
 * One-shot encrypt with device key (auto-mode).
 */
export async function encryptWithDeviceKey(
  plaintext: string
): Promise<EncryptedPayload> {
  const keySet = await getOrCreateDeviceKey();
  return encrypt(plaintext, keySet);
}

/**
 * Check if the Web Crypto API is available in this environment.
 */
export function isCryptoAvailable(): boolean {
  return (
    typeof crypto !== "undefined" &&
    typeof crypto.subtle !== "undefined" &&
    typeof crypto.getRandomValues === "function"
  );
}
