/**
 * Nobi API Client — Handles communication with the Nobi subnet/bot API.
 * Features: retry with exponential backoff, offline queue, configurable endpoints.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface Message {
  id: string;
  role: 'user' | 'nori';
  content: string;
  timestamp: number;
  imageUri?: string;
  imageDescription?: string;
  status: 'sending' | 'sent' | 'error' | 'queued';
}

export interface Memory {
  id: string;
  type: 'fact' | 'preference' | 'event' | 'context' | 'emotion';
  content: string;
  importance: number;
  tags: string[];
  createdAt: string;
  expiresAt?: string;
}

export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: string;
}

export interface SendMessageResponse {
  response: string;
  confidence: number;
  memoryContext?: Record<string, unknown>[];
}

// ─── Config ──────────────────────────────────────────────────────────────────

const STORAGE_KEYS = {
  OFFLINE_QUEUE: '@nobi/offline_queue',
  BASE_URL: '@nobi/base_url',
} as const;

const DEFAULT_BASE_URL = 'https://api.projectnobi.ai';
const TESTNET_BASE_URL = 'https://testnet.projectnobi.ai';

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

// ─── Offline Queue ───────────────────────────────────────────────────────────

interface QueuedMessage {
  userId: string;
  message: string;
  memoryContext?: string;
  timestamp: number;
}

async function getOfflineQueue(): Promise<QueuedMessage[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.OFFLINE_QUEUE);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function addToOfflineQueue(item: QueuedMessage): Promise<void> {
  const queue = await getOfflineQueue();
  queue.push(item);
  await AsyncStorage.setItem(STORAGE_KEYS.OFFLINE_QUEUE, JSON.stringify(queue));
}

async function clearOfflineQueue(): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.OFFLINE_QUEUE, JSON.stringify([]));
}

// ─── Retry Logic ─────────────────────────────────────────────────────────────

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retries = MAX_RETRIES,
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(30000),
      });

      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        const delayMs = retryAfter
          ? parseInt(retryAfter, 10) * 1000
          : BASE_DELAY_MS * Math.pow(2, attempt);
        await sleep(delayMs);
        continue;
      }

      return response;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < retries) {
        await sleep(BASE_DELAY_MS * Math.pow(2, attempt));
      }
    }
  }

  throw lastError ?? new Error('Request failed after retries');
}

// ─── API Client ──────────────────────────────────────────────────────────────

class NobiApiClient {
  private baseUrl: string = DEFAULT_BASE_URL;

  async init(): Promise<void> {
    const stored = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
    if (stored) this.baseUrl = stored;
  }

  async setNetwork(network: 'mainnet' | 'testnet'): Promise<void> {
    this.baseUrl = network === 'testnet' ? TESTNET_BASE_URL : DEFAULT_BASE_URL;
    await AsyncStorage.setItem(STORAGE_KEYS.BASE_URL, this.baseUrl);
  }

  getNetwork(): 'mainnet' | 'testnet' {
    return this.baseUrl === TESTNET_BASE_URL ? 'testnet' : 'mainnet';
  }

  // ─── Send Message ──────────────────────────────────────────────────────

  async sendMessage(
    userId: string,
    message: string,
    memoryContext?: string,
  ): Promise<ApiResponse<SendMessageResponse>> {
    try {
      const response = await fetchWithRetry(`${this.baseUrl}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          message,
          memory_context: memoryContext,
        }),
      });

      if (!response.ok) {
        return { ok: false, error: `Server error: ${response.status}` };
      }

      const data = await response.json();
      return { ok: true, data };
    } catch {
      // Offline — queue the message
      await addToOfflineQueue({ userId, message, memoryContext, timestamp: Date.now() });
      return { ok: false, error: 'offline' };
    }
  }

  // ─── Send Image ────────────────────────────────────────────────────────

  async sendImage(
    userId: string,
    imageBase64: string,
    caption: string,
    imageFormat = 'jpg',
  ): Promise<ApiResponse<{ description: string; response: string; extractedMemories: string[] }>> {
    try {
      const response = await fetchWithRetry(`${this.baseUrl}/v1/image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          image_data: imageBase64,
          image_format: imageFormat,
          caption,
        }),
      });

      if (!response.ok) {
        return { ok: false, error: `Server error: ${response.status}` };
      }

      const data = await response.json();
      return { ok: true, data };
    } catch {
      return { ok: false, error: 'Failed to send image' };
    }
  }

  // ─── Voice ─────────────────────────────────────────────────────────────

  async sendVoice(
    audioBase64: string,
    audioFormat = 'wav',
    language = 'en',
  ): Promise<ApiResponse<{ transcription: string; responseText: string; responseAudio: string }>> {
    try {
      const response = await fetchWithRetry(`${this.baseUrl}/v1/voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audio_data: audioBase64,
          audio_format: audioFormat,
          language,
        }),
      });

      if (!response.ok) {
        return { ok: false, error: `Server error: ${response.status}` };
      }

      const data = await response.json();
      return { ok: true, data };
    } catch {
      return { ok: false, error: 'Voice processing failed' };
    }
  }

  // ─── Memories ──────────────────────────────────────────────────────────

  async getMemories(userId: string): Promise<ApiResponse<Memory[]>> {
    try {
      const response = await fetchWithRetry(
        `${this.baseUrl}/v1/memories?user_id=${encodeURIComponent(userId)}`,
        { method: 'GET' },
      );

      if (!response.ok) {
        return { ok: false, error: `Server error: ${response.status}` };
      }

      const data = await response.json();
      return { ok: true, data: data.memories ?? [] };
    } catch {
      return { ok: false, error: 'Failed to fetch memories' };
    }
  }

  async deleteMemory(userId: string, memoryId: string): Promise<ApiResponse<void>> {
    try {
      const response = await fetchWithRetry(`${this.baseUrl}/v1/memories/${memoryId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      });

      return { ok: response.ok, error: response.ok ? undefined : `Error: ${response.status}` };
    } catch {
      return { ok: false, error: 'Failed to delete memory' };
    }
  }

  async exportMemories(userId: string): Promise<ApiResponse<Memory[]>> {
    try {
      const response = await fetchWithRetry(
        `${this.baseUrl}/v1/memories/export?user_id=${encodeURIComponent(userId)}`,
        { method: 'GET' },
      );

      if (!response.ok) {
        return { ok: false, error: `Server error: ${response.status}` };
      }

      const data = await response.json();
      return { ok: true, data: data.memories ?? [] };
    } catch {
      return { ok: false, error: 'Failed to export memories' };
    }
  }

  async deleteAllMemories(userId: string): Promise<ApiResponse<void>> {
    try {
      const response = await fetchWithRetry(`${this.baseUrl}/v1/memories/all`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      });

      return { ok: response.ok, error: response.ok ? undefined : `Error: ${response.status}` };
    } catch {
      return { ok: false, error: 'Failed to delete all memories' };
    }
  }

  // ─── Offline Queue Processing ──────────────────────────────────────────

  async processOfflineQueue(): Promise<number> {
    const queue = await getOfflineQueue();
    if (queue.length === 0) return 0;

    let processed = 0;
    const failed: QueuedMessage[] = [];

    for (const item of queue) {
      try {
        const response = await fetch(`${this.baseUrl}/v1/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: item.userId,
            message: item.message,
            memory_context: item.memoryContext,
          }),
          signal: AbortSignal.timeout(15000),
        });

        if (response.ok) {
          processed++;
        } else {
          failed.push(item);
        }
      } catch {
        failed.push(item);
      }
    }

    await AsyncStorage.setItem(STORAGE_KEYS.OFFLINE_QUEUE, JSON.stringify(failed));
    return processed;
  }

  async getQueuedCount(): Promise<number> {
    const queue = await getOfflineQueue();
    return queue.length;
  }
}

export const api = new NobiApiClient();
export { clearOfflineQueue };
