"use client";

import ReactMarkdown from "react-markdown";
import type { Message } from "@/lib/types";

interface ChatBubbleProps {
  message: Message;
}

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === "user";
  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={`flex gap-3 animate-slide-up ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm ${
          isUser
            ? "bg-nori-100 dark:bg-nori-900/50"
            : "bg-gradient-to-br from-nori-500 to-warm-500"
        }`}
        aria-hidden="true"
      >
        {isUser ? "👤" : "🤖"}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[80%] sm:max-w-[70%] ${
          isUser
            ? "bg-nori-600 text-white rounded-2xl rounded-tr-md"
            : "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-2xl rounded-tl-md border border-gray-100 dark:border-gray-700"
        } px-4 py-3 shadow-sm`}
      >
        {isUser ? (
          <p className="text-sm sm:text-base whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="text-sm sm:text-base prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
        <p
          className={`text-[10px] mt-1.5 ${
            isUser
              ? "text-nori-200"
              : "text-gray-400 dark:text-gray-500"
          }`}
        >
          {time}
        </p>
      </div>
    </div>
  );
}
