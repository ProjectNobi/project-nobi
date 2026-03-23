/**
 * Project Nobi — Privacy-Preserving Memory Sync
 * ===============================================
 * Orchestrates on-device memory extraction → encryption → server sync.
 * When privacy mode is enabled:
 *   1. User message → local regex extractor → extracted memories
 *   2. Extracted memories → AES-256-GCM encryption
 *   3. ONLY encrypted blobs are sent to server (raw text never transmitted separately)
 *   4. Server stores encrypted memories, can't read them
 * Falls back to standard server-side extraction when privacy mode is off.
 */

import { extractFromMessage, type ExtractionResult } from "./local-extractor";
import {
  encryptWithDeviceKey,
  encrypt,
  deriveKey,
  isCryptoAvailable,
  type EncryptedPayload,
  type CryptoKeySet,
} from "./client-crypto";
import { API_BASE_URL } from "./constants";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PrivacySettings {
  /** Is on-device privacy mode enabled? */
  enabled: boolean;
  /** Optional user passphrase for key derivation (uses device key if absent) */
  passphrase?: string;
}

export interface EncryptedChatRequest {
  /** Encrypted message text */
  message: EncryptedPayload;
  /** Encrypted extracted memories */
  memories: EncryptedPayload;
  /** Encrypted conversation history */
  conversation_history: EncryptedPayload;
  /** User ID (not encrypted — used for routing) */
  user_id: string;
  /** Signal that client has extracted memories locally */
  client_extracted: true;
}

export interface EncryptedMemorySyncRequest {
  /** Encrypted memory blob (JSON array of ExtractedMemory) */
  memories: EncryptedPayload;
  /** User ID */
  user_id: string;
  /** Number of memories in the encrypted blob (metadata, not sensitive) */
  count: number;
}

export interface SyncResult {
  /** Were memories synced successfully? */
  synced: boolean;
  /** Number of memories extracted */
  count: number;
  /** Privacy mode was active */
  private: boolean;
  /** Error if sync failed */
  error?: string;
}

// ─── Settings persistence ─────────────────────────────────────────────────────

const PRIVACY_SETTINGS_KEY = "nobi_privacy_settings_v1";

export function loadPrivacySettings(): PrivacySettings {
  if (typeof localStorage === "undefined") return { enabled: false };
  try {
    const raw = localStorage.getItem(PRIVACY_SETTINGS_KEY);
    if (raw) return JSON.parse(raw) as PrivacySettings;
  } catch {
    // ignore
  }
  return { enabled: false };
}

export function savePrivacySettings(settings: PrivacySettings): void {
  if (typeof localStorage === "undefined") return;
  // Never persist passphrase to localStorage
  const safe: PrivacySettings = { enabled: settings.enabled };
  localStorage.setItem(PRIVACY_SETTINGS_KEY, JSON.stringify(safe));
}

// ─── Capability check ─────────────────────────────────────────────────────────

export function isPrivacyModeSupported(): boolean {
  return isCryptoAvailable() && typeof TextEncoder !== "undefined";
}

// ─── Core: encrypt extraction result ─────────────────────────────────────────

async function encryptExtractionResult(
  result: ExtractionResult,
  keySet: CryptoKeySet
): Promise<EncryptedPayload> {
  const json = JSON.stringify(result);
  return encrypt(json, keySet);
}

// ─── Main: process a message with privacy mode ────────────────────────────────

/**
 * Process a user message with on-device privacy mode.
 * Extracts memories locally, encrypts everything, returns the encrypted payload
 * ready to send to /api/v1/chat/encrypted.
 *
 * @param message - The user's raw message
 * @param userId - The user's ID
 * @param conversationHistory - Recent conversation turns
 * @param settings - Current privacy settings
 * @returns EncryptedChatRequest ready to POST, plus the extraction result for local display
 */
export async function processMessagePrivately(
  message: string,
  userId: string,
  conversationHistory: Array<{ role: string; content: string }>,
  settings: PrivacySettings
): Promise<{
  request: EncryptedChatRequest;
  extraction: ExtractionResult;
  keySet: CryptoKeySet;
}> {
  // Step 1: Extract memories locally (browser only, no network)
  const extraction = extractFromMessage(message);

  // Step 2: Derive encryption key
  let keySet: CryptoKeySet;
  if (settings.passphrase) {
    keySet = await deriveKey(settings.passphrase);
  } else {
    const { getOrCreateDeviceKey } = await import("./client-crypto");
    keySet = await getOrCreateDeviceKey();
  }

  // Step 3: Encrypt everything
  const [encryptedMessage, encryptedMemories, encryptedHistory] = await Promise.all([
    encrypt(message, keySet),
    encryptExtractionResult(extraction, keySet),
    encrypt(JSON.stringify(conversationHistory), keySet),
  ]);

  const request: EncryptedChatRequest = {
    message: encryptedMessage,
    memories: encryptedMemories,
    conversation_history: encryptedHistory,
    user_id: userId,
    client_extracted: true,
  };

  return { request, extraction, keySet };
}

// ─── Encrypted Chat Response ──────────────────────────────────────────────────

export interface EncryptedChatResponse {
  /** Plaintext response from Nori */
  response: string;
  /** Memories used in context */
  memories_used: string[];
  /** Optional encrypted response blob (Phase 4: TEE path) */
  encrypted_response?: EncryptedPayload;
}

// ─── Send encrypted chat request ──────────────────────────────────────────────

/**
 * Send an encrypted chat request to the server and decrypt the response.
 *
 * Phase 4 TEE Passthrough flow:
 *   1. Browser encrypts message + memories → sends to /api/v1/chat/encrypted
 *   2. Server calls TEE LLM, may re-encrypt response
 *   3. If `encrypted_response` is present in server reply, decrypt it client-side
 *   4. Return decrypted (or plaintext) response to caller
 *
 * @param request - Encrypted payload from processMessagePrivately()
 * @param keySet - Key set used to encrypt the request (for response decryption)
 * @returns Server response text (decrypted if encrypted_response was returned)
 */
export async function sendEncryptedChat(
  request: EncryptedChatRequest,
  keySet?: CryptoKeySet
): Promise<{ response: string; memories_used: string[] }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/chat/encrypted`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  const data = (await res.json()) as EncryptedChatResponse;

  // Phase 4: If the server returned an encrypted response blob, decrypt it
  if (data.encrypted_response && keySet) {
    try {
      const { decrypt } = await import("./client-crypto");
      const decryptedResponse = await decrypt(data.encrypted_response, keySet);
      return {
        response: decryptedResponse,
        memories_used: data.memories_used,
      };
    } catch (e) {
      console.warn(
        "[Privacy] Failed to decrypt encrypted_response, using plaintext fallback:",
        e
      );
    }
  }

  return {
    response: data.response,
    memories_used: data.memories_used,
  };
}

// ─── Sync extracted memories to server (encrypted) ────────────────────────────

/**
 * Sync locally-extracted memories to the server in encrypted form.
 * Used for background memory persistence without going through the chat endpoint.
 *
 * @param result - Extraction result from extractFromMessage()
 * @param userId - User ID
 * @param settings - Privacy settings
 * @returns SyncResult
 */
export async function syncMemoriesPrivately(
  result: ExtractionResult,
  userId: string,
  settings: PrivacySettings
): Promise<SyncResult> {
  if (result.memories.length === 0) {
    return { synced: true, count: 0, private: true };
  }

  try {
    let keySet: CryptoKeySet;
    if (settings.passphrase) {
      keySet = await deriveKey(settings.passphrase);
    } else {
      const { getOrCreateDeviceKey } = await import("./client-crypto");
      keySet = await getOrCreateDeviceKey();
    }

    const encryptedMemories = await encryptExtractionResult(result, keySet);

    const syncRequest: EncryptedMemorySyncRequest = {
      memories: encryptedMemories,
      user_id: userId,
      count: result.memories.length,
    };

    const res = await fetch(`${API_BASE_URL}/api/v1/memories/encrypted`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(syncRequest),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    return { synced: true, count: result.memories.length, private: true };
  } catch (e) {
    return {
      synced: false,
      count: 0,
      private: true,
      error: e instanceof Error ? e.message : "Unknown error",
    };
  }
}

// ─── LocalStorage memory cache (IndexedDB fallback to localStorage) ────────────

const LOCAL_MEMORIES_KEY = "nobi_local_memories_v1";

export interface LocalMemoryEntry {
  id: string;
  content: string;
  memory_type: string;
  importance: number;
  tags: string[];
  extracted_at: string;
}

/**
 * Save extracted memories to localStorage for local persistence.
 * This is the local cache — not encrypted since it's already on the device.
 */
export function saveLocalMemories(memories: ExtractionResult["memories"]): void {
  if (typeof localStorage === "undefined" || memories.length === 0) return;

  try {
    const existing = loadLocalMemories();
    const existingContents = new Set(existing.map((m) => m.content.toLowerCase().trim()));

    const newEntries: LocalMemoryEntry[] = memories
      .filter((m) => !existingContents.has(m.content.toLowerCase().trim()))
      .map((m) => ({
        id: `local_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
        content: m.content,
        memory_type: m.memory_type,
        importance: m.importance,
        tags: m.tags,
        extracted_at: new Date().toISOString(),
      }));

    if (newEntries.length === 0) return;

    const all = [...existing, ...newEntries].slice(-500); // keep last 500
    localStorage.setItem(LOCAL_MEMORIES_KEY, JSON.stringify(all));
  } catch {
    // localStorage full or unavailable — silently skip
  }
}

/**
 * Load locally cached memories.
 */
export function loadLocalMemories(): LocalMemoryEntry[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(LOCAL_MEMORIES_KEY);
    if (raw) return JSON.parse(raw) as LocalMemoryEntry[];
  } catch {
    // ignore
  }
  return [];
}

/**
 * Clear all locally cached memories.
 */
export function clearLocalMemories(): void {
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(LOCAL_MEMORIES_KEY);
  }
}
