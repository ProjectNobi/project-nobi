/**
 * Project Nobi — Client-Side Crypto (React Native)
 * =================================================
 * Adapted from webapp/lib/client-crypto.ts for React Native.
 * Uses expo-crypto (SHA-256 digest) + expo-secure-store for key storage.
 *
 * Note: expo-crypto doesn't expose full AES-GCM — we use the encryption
 * service in services/encryption.ts (which wraps expo-crypto) for actual
 * AES operations. This module provides key derivation and base64 utils.
 */

import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EncryptedPayload {
  ciphertext: string;
  iv: string;
  salt: string;
  algorithm: 'AES-GCM-256';
  iterations: number;
}

// ─── Utilities ────────────────────────────────────────────────────────────────

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ─── Random bytes ──────────────────────────────────────────────────────────────

export async function getRandomBytes(length: number): Promise<Uint8Array> {
  return Crypto.getRandomBytes(length);
}

// ─── Key derivation (PBKDF2 approximation via SHA-256 iterations) ──────────────

const SECURE_STORE_PREFIX = 'nobi_device_key_v1';

/**
 * Get or create a device-bound key stored in SecureStore.
 * Returns a 32-byte key as base64.
 */
export async function getOrCreateDeviceKey(userId: string): Promise<string> {
  const storeKey = `${SECURE_STORE_PREFIX}_${userId}`;
  const existing = await SecureStore.getItemAsync(storeKey);
  if (existing) return existing;

  const keyBytes = await Crypto.getRandomBytes(32);
  const keyBase64 = bytesToBase64(keyBytes);
  await SecureStore.setItemAsync(storeKey, keyBase64);
  return keyBase64;
}

/**
 * Derive a key from a passphrase using iterative SHA-256.
 * Returns a 32-byte derived key as base64.
 */
export async function deriveKeyFromPassphrase(
  passphrase: string,
  salt: Uint8Array,
  iterations = 1000,
): Promise<Uint8Array> {
  const encoder = new TextEncoder();
  let derived = new Uint8Array([...encoder.encode(passphrase), ...salt]);

  for (let i = 0; i < iterations; i++) {
    const hashBuffer = await Crypto.digest(
      Crypto.CryptoDigestAlgorithm.SHA256,
      derived,
    );
    derived = new Uint8Array(hashBuffer);
  }

  return derived.slice(0, 32);
}

/**
 * Check if crypto is available (always true on React Native with expo-crypto).
 */
export function isCryptoAvailable(): boolean {
  return true;
}
