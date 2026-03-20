"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { api } from "@/lib/api";
import { STORAGE_KEYS } from "@/lib/constants";
import type { Message } from "@/lib/types";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const getUserId = useCallback((): string => {
    if (typeof window === "undefined") return "";
    let userId = localStorage.getItem(STORAGE_KEYS.USER_ID);
    if (!userId) {
      userId = uuidv4();
      localStorage.setItem(STORAGE_KEYS.USER_ID, userId);
    }
    return userId;
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const userId = getUserId();
      const userMessage: Message = {
        id: uuidv4(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await api.chat(content.trim(), userId);
        const assistantMessage: Message = {
          id: uuidv4(),
          role: "assistant",
          content: response.response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);

        // Play voice if enabled
        try {
          const settingsStr = localStorage.getItem("nobi_settings");
          const voiceEnabled = settingsStr ? JSON.parse(settingsStr).voice_enabled : false;
          if (voiceEnabled === "true" && response.response) {
            // Use browser's built-in speech synthesis
            const utterance = new SpeechSynthesisUtterance(response.response);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            // Try to find a nice voice
            const voices = window.speechSynthesis.getVoices();
            const preferred = voices.find(v => v.name.includes("Google") && v.lang.startsWith("en")) 
              || voices.find(v => v.lang.startsWith("en"));
            if (preferred) utterance.voice = preferred;
            window.speechSynthesis.cancel(); // Stop any previous
            window.speechSynthesis.speak(utterance);
          }
        } catch (voiceErr) {
          console.debug("Voice playback not available:", voiceErr);
        }
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : "Something went wrong";
        setError(errorMsg);
        // Add error message to chat
        const errorMessage: Message = {
          id: uuidv4(),
          role: "assistant",
          content:
            "I'm having trouble connecting right now. Please try again in a moment! 🤖",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    },
    [getUserId, isLoading]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    messagesEndRef,
    getUserId,
  };
}
