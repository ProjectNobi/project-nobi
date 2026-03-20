"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import MemoryCard from "@/components/MemoryCard";
import { useMemories } from "@/hooks/useMemories";

export default function MemoriesPage() {
  const {
    memories,
    isLoading,
    error,
    fetchMemories,
    deleteMemory,
    exportMemories,
  } = useMemories();
  const [search, setSearch] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    fetchMemories();
  }, [fetchMemories]);

  const handleSearch = () => {
    fetchMemories(search || undefined);
  };

  const handleDelete = async (id: string) => {
    if (confirm("Delete this memory?")) {
      await deleteMemory(id);
    }
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              🧠 Memories
            </h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              Everything Nori remembers about you
            </p>
          </div>
          <button
            onClick={exportMemories}
            className="btn-secondary text-sm"
          >
            📥 Export JSON
          </button>
        </div>

        {/* Search */}
        <div className="flex gap-2 mb-6">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search memories..."
            className="input-field"
          />
          <button onClick={handleSearch} className="btn-primary px-4">
            🔍
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="text-center py-12">
            <div className="w-8 h-8 border-2 border-nori-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-3 text-gray-500">Loading memories...</p>
          </div>
        )}

        {/* Memories list */}
        {!isLoading && memories.length === 0 && (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🧠</div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No memories yet
            </h3>
            <p className="text-gray-500 dark:text-gray-400">
              Start chatting with Nori and memories will appear here!
            </p>
          </div>
        )}

        <div className="space-y-3">
          {memories.map((memory) => (
            <MemoryCard
              key={memory.id}
              memory={memory}
              onDelete={handleDelete}
            />
          ))}
        </div>

        {/* Count */}
        {memories.length > 0 && (
          <p className="text-center text-sm text-gray-400 mt-6">
            {memories.length} {memories.length === 1 ? "memory" : "memories"}
          </p>
        )}
      </div>
    </div>
  );
}
