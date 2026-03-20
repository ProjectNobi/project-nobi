"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import ChatBubble from "@/components/ChatBubble";
import ChatInput from "@/components/ChatInput";
import { useChat } from "@/hooks/useChat";
import { STORAGE_KEYS } from "@/lib/constants";

export default function ChatPage() {
  const { messages, isLoading, sendMessage, sendImage, messagesEndRef } = useChat();
  const [mounted, setMounted] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
    // Check onboarding
    const onboarded = localStorage.getItem(STORAGE_KEYS.ONBOARDED);
    if (!onboarded) {
      router.push("/onboarding");
    }
  }, [router]);

  if (!mounted) return null;

  return (
    <div className="flex flex-col h-screen">
      <Navbar />

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-20 animate-fade-in">
              <div className="text-6xl mb-4">🤖</div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Hey there!
              </h2>
              <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                I&apos;m Nori, your personal AI companion. Tell me about yourself,
                ask me anything, or just say hi!
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} />
          ))}

          {/* Typing indicator */}
          {isLoading && (
            <div className="flex gap-3 animate-fade-in">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-nori-500 to-warm-500 flex items-center justify-center text-sm">
                🤖
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-2xl rounded-tl-md px-4 py-3 border border-gray-100 dark:border-gray-700 shadow-sm">
                <div className="flex gap-1.5">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} onSendImage={sendImage} isLoading={isLoading} />
    </div>
  );
}
