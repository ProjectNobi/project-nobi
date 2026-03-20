"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { STORAGE_KEYS } from "@/lib/constants";
import type { Memory } from "@/lib/types";

export function useMemories() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getUserId = (): string => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(STORAGE_KEYS.USER_ID) || "";
  };

  const fetchMemories = useCallback(async (search?: string) => {
    const userId = getUserId();
    if (!userId) return;

    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getMemories(userId, search);
      setMemories(data.memories);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memories");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteMemory = useCallback(async (memoryId: string) => {
    const userId = getUserId();
    if (!userId) return;

    try {
      await api.deleteMemory(memoryId, userId);
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete memory");
    }
  }, []);

  const exportMemories = useCallback(async () => {
    const userId = getUserId();
    if (!userId) return;

    try {
      const result = await api.exportMemories(userId);
      const blob = new Blob([JSON.stringify(result.data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nobi-memories-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export memories");
    }
  }, []);

  const forgetAll = useCallback(async () => {
    const userId = getUserId();
    if (!userId) return;

    try {
      await api.forgetAll(userId);
      setMemories([]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to forget memories"
      );
    }
  }, []);

  return {
    memories,
    isLoading,
    error,
    fetchMemories,
    deleteMemory,
    exportMemories,
    forgetAll,
  };
}
