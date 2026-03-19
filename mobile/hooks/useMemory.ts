/**
 * Memory CRUD hook — manages memories with local cache + server sync.
 */

import { useState, useCallback, useEffect } from 'react';
import { api, type Memory } from '../services/api';
import { memoryStore } from '../services/memory';
import { auth } from '../services/auth';

export function useMemory() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [filteredMemories, setFilteredMemories] = useState<Memory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<Memory['type'] | 'all'>('all');

  // ─── Fetch memories ────────────────────────────────────────────────────

  const fetchMemories = useCallback(async () => {
    const user = auth.getUser();
    if (!user) return;

    setIsLoading(true);
    setError(null);

    try {
      // Try server first
      const result = await api.getMemories(user.id);
      if (result.ok && result.data) {
        await memoryStore.saveLocal(user.id, result.data);
        setMemories(result.data);
      } else {
        // Fall back to local cache
        const local = await memoryStore.getLocal(user.id);
        setMemories(local);
      }
    } catch {
      // Offline — use local
      const user2 = auth.getUser();
      if (user2) {
        const local = await memoryStore.getLocal(user2.id);
        setMemories(local);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ─── Delete a memory ───────────────────────────────────────────────────

  const deleteMemory = useCallback(
    async (memoryId: string) => {
      const user = auth.getUser();
      if (!user) return;

      try {
        // Optimistic update
        setMemories((prev) => prev.filter((m) => m.id !== memoryId));
        await memoryStore.deleteLocal(user.id, memoryId);

        // Sync to server
        const result = await api.deleteMemory(user.id, memoryId);
        if (!result.ok) {
          setError('Failed to delete from server (removed locally)');
        }
      } catch {
        setError('Failed to delete memory');
      }
    },
    [],
  );

  // ─── Export memories ───────────────────────────────────────────────────

  const exportMemories = useCallback(async (): Promise<string | null> => {
    const user = auth.getUser();
    if (!user) return null;

    try {
      return await memoryStore.exportAsJson(user.id);
    } catch {
      setError('Failed to export memories');
      return null;
    }
  }, []);

  // ─── Delete all memories ───────────────────────────────────────────────

  const deleteAllMemories = useCallback(async () => {
    const user = auth.getUser();
    if (!user) return;

    try {
      setMemories([]);
      await memoryStore.clearLocal(user.id);

      const result = await api.deleteAllMemories(user.id);
      if (!result.ok) {
        setError('Failed to delete from server (removed locally)');
      }
    } catch {
      setError('Failed to delete all memories');
    }
  }, []);

  // ─── Search and filter ─────────────────────────────────────────────────

  const search = useCallback(
    (query: string) => {
      setSearchQuery(query);
    },
    [],
  );

  const setFilter = useCallback(
    (type: Memory['type'] | 'all') => {
      setFilterType(type);
    },
    [],
  );

  // Apply search + filter
  useEffect(() => {
    let result = [...memories];

    if (filterType !== 'all') {
      result = result.filter((m) => m.type === filterType);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (m) =>
          m.content.toLowerCase().includes(q) ||
          m.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }

    setFilteredMemories(result);
  }, [memories, searchQuery, filterType]);

  // ─── Init ──────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  return {
    memories: filteredMemories,
    allMemories: memories,
    isLoading,
    error,
    searchQuery,
    filterType,
    fetchMemories,
    deleteMemory,
    exportMemories,
    deleteAllMemories,
    search,
    setFilter,
  };
}
