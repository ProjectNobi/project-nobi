"use client";

import { MEMORY_TYPE_LABELS, MEMORY_TYPE_COLORS } from "@/lib/constants";
import type { Memory } from "@/lib/types";

interface MemoryCardProps {
  memory: Memory;
  onDelete: (id: string) => void;
}

export default function MemoryCard({ memory, onDelete }: MemoryCardProps) {
  const typeLabel = MEMORY_TYPE_LABELS[memory.memory_type] || "📝 Memory";
  const typeColor =
    MEMORY_TYPE_COLORS[memory.memory_type] ||
    "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300";

  const date = new Date(memory.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const importancePercent = Math.round(memory.importance * 100);

  return (
    <div className="card p-4 animate-fade-in group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Type badge */}
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${typeColor}`}
            >
              {typeLabel}
            </span>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {date}
            </span>
          </div>

          {/* Content */}
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {memory.content}
          </p>

          {/* Footer */}
          <div className="flex items-center gap-3 mt-3">
            {/* Importance bar */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Importance
              </span>
              <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-nori-500 rounded-full transition-all duration-300"
                  style={{ width: `${importancePercent}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-400">
                {importancePercent}%
              </span>
            </div>

            {/* Tags */}
            {memory.tags.length > 0 && (
              <div className="flex gap-1">
                {memory.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Delete button */}
        <button
          onClick={() => onDelete(memory.id)}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg
                     hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500"
          aria-label="Delete memory"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
