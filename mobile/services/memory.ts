/**
 * Local memory cache using AsyncStorage.
 * Provides offline-first memory management with sync to server.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Memory } from './api';

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEYS = {
  MEMORIES: '@nobi/memories',
  LAST_SYNC: '@nobi/memories_last_sync',
} as const;

// ─── Local Memory Store ──────────────────────────────────────────────────────

class MemoryStore {
  private cache: Map<string, Memory[]> = new Map();

  /**
   * Load memories for a user from local cache.
   */
  async getLocal(userId: string): Promise<Memory[]> {
    if (this.cache.has(userId)) {
      return this.cache.get(userId)!;
    }

    try {
      const raw = await AsyncStorage.getItem(`${STORAGE_KEYS.MEMORIES}_${userId}`);
      const memories: Memory[] = raw ? JSON.parse(raw) : [];
      this.cache.set(userId, memories);
      return memories;
    } catch {
      return [];
    }
  }

  /**
   * Save memories locally.
   */
  async saveLocal(userId: string, memories: Memory[]): Promise<void> {
    this.cache.set(userId, memories);
    await AsyncStorage.setItem(
      `${STORAGE_KEYS.MEMORIES}_${userId}`,
      JSON.stringify(memories),
    );
    await AsyncStorage.setItem(STORAGE_KEYS.LAST_SYNC, new Date().toISOString());
  }

  /**
   * Add a memory locally.
   */
  async addLocal(userId: string, memory: Memory): Promise<void> {
    const memories = await this.getLocal(userId);
    // Avoid duplicates
    const existing = memories.findIndex((m) => m.id === memory.id);
    if (existing >= 0) {
      memories[existing] = memory;
    } else {
      memories.unshift(memory);
    }
    await this.saveLocal(userId, memories);
  }

  /**
   * Delete a memory locally.
   */
  async deleteLocal(userId: string, memoryId: string): Promise<void> {
    const memories = await this.getLocal(userId);
    const filtered = memories.filter((m) => m.id !== memoryId);
    await this.saveLocal(userId, filtered);
  }

  /**
   * Search memories locally by content.
   */
  async search(userId: string, query: string): Promise<Memory[]> {
    const memories = await this.getLocal(userId);
    const lowerQuery = query.toLowerCase();
    return memories.filter(
      (m) =>
        m.content.toLowerCase().includes(lowerQuery) ||
        m.tags.some((t) => t.toLowerCase().includes(lowerQuery)),
    );
  }

  /**
   * Filter memories by type.
   */
  async filterByType(userId: string, type: Memory['type']): Promise<Memory[]> {
    const memories = await this.getLocal(userId);
    return memories.filter((m) => m.type === type);
  }

  /**
   * Clear all local memories for a user.
   */
  async clearLocal(userId: string): Promise<void> {
    this.cache.delete(userId);
    await AsyncStorage.removeItem(`${STORAGE_KEYS.MEMORIES}_${userId}`);
  }

  /**
   * Export all memories as a JSON string.
   */
  async exportAsJson(userId: string): Promise<string> {
    const memories = await this.getLocal(userId);
    return JSON.stringify(memories, null, 2);
  }

  /**
   * Get last sync timestamp.
   */
  async getLastSync(): Promise<string | null> {
    return AsyncStorage.getItem(STORAGE_KEYS.LAST_SYNC);
  }
}

export const memoryStore = new MemoryStore();
