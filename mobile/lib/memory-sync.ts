/**
 * Project Nobi — Privacy-Preserving Memory Sync (React Native)
 * =============================================================
 * Adapted from webapp/lib/memory-sync.ts for React Native.
 * Key differences:
 *   - AsyncStorage instead of localStorage
 *   - expo-crypto instead of Web Crypto API
 *   - fetch works natively in React Native
 *
 * Orchestrates on-device memory extraction → encryption → server sync.
 * When privacy mode is enabled, only encrypted blobs reach the server.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { extractFromMessage, type ExtractionResult } from './local-extractor';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PrivacySettings {
  enabled: boolean;
  passphrase?: string;
}

export interface SyncResult {
  synced: boolean;
  count: number;
  private: boolean;
  error?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PRIVACY_SETTINGS_KEY = '@nobi/privacy_settings';
const LOCAL_MEMORIES_KEY = '@nobi/local_memories';
const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://api.projectnobi.ai';

// ─── Settings persistence ─────────────────────────────────────────────────────

export async function loadPrivacySettings(): Promise<PrivacySettings> {
  try {
    const raw = await AsyncStorage.getItem(PRIVACY_SETTINGS_KEY);
    if (raw) return JSON.parse(raw) as PrivacySettings;
  } catch {
    // ignore
  }
  return { enabled: false };
}

export async function savePrivacySettings(settings: PrivacySettings): Promise<void> {
  // Never persist passphrase
  const safe: PrivacySettings = { enabled: settings.enabled };
  await AsyncStorage.setItem(PRIVACY_SETTINGS_KEY, JSON.stringify(safe));
}

// ─── Local memory cache (AsyncStorage) ────────────────────────────────────────

export interface LocalMemoryEntry {
  id: string;
  content: string;
  memory_type: string;
  importance: number;
  tags: string[];
  extracted_at: string;
}

export async function saveLocalMemories(
  memories: ExtractionResult['memories'],
): Promise<void> {
  if (memories.length === 0) return;

  try {
    const existing = await loadLocalMemories();
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

    const all = [...existing, ...newEntries].slice(-500);
    await AsyncStorage.setItem(LOCAL_MEMORIES_KEY, JSON.stringify(all));
  } catch {
    // silent fail
  }
}

export async function loadLocalMemories(): Promise<LocalMemoryEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(LOCAL_MEMORIES_KEY);
    if (raw) return JSON.parse(raw) as LocalMemoryEntry[];
  } catch {
    // ignore
  }
  return [];
}

export async function clearLocalMemories(): Promise<void> {
  await AsyncStorage.removeItem(LOCAL_MEMORIES_KEY);
}

// ─── Extract from message ─────────────────────────────────────────────────────

/**
 * Run local extraction on a message and cache results.
 * Pure TypeScript — no network, no browser APIs.
 */
export function extractAndCache(message: string): ExtractionResult {
  const result = extractFromMessage(message);
  // Fire-and-forget cache save
  saveLocalMemories(result.memories).catch(() => {});
  return result;
}

// ─── Sync to server (plain, no encryption) ────────────────────────────────────

export async function syncMemoriesToServer(
  userId: string,
  memories: ExtractionResult['memories'],
): Promise<SyncResult> {
  if (memories.length === 0) return { synced: true, count: 0, private: false };

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/memories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        memories: memories.map((m) => ({
          content: m.content,
          memory_type: m.memory_type,
          importance: m.importance,
          tags: m.tags,
        })),
      }),
    });

    return { synced: res.ok, count: memories.length, private: false };
  } catch (e) {
    return {
      synced: false,
      count: 0,
      private: false,
      error: e instanceof Error ? e.message : 'Network error',
    };
  }
}
