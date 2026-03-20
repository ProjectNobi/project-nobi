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
          const settings = settingsStr ? JSON.parse(settingsStr) : {};
          if (settings.voice_enabled && response.response && typeof window !== "undefined" && window.speechSynthesis) {
            const speakText = (text: string) => {
              const utterance = new SpeechSynthesisUtterance(text);
              utterance.rate = 1.0;
              utterance.pitch = 1.05;
              utterance.volume = 1.0;
              utterance.lang = "en-US";
              const voices = window.speechSynthesis.getVoices();
              const preferred = voices.find(v => v.name.includes("Google") && v.lang.startsWith("en"))
                || voices.find(v => v.name.includes("Samantha"))
                || voices.find(v => v.lang.startsWith("en") && v.localService);
              if (preferred) utterance.voice = preferred;
              window.speechSynthesis.cancel();
              window.speechSynthesis.speak(utterance);
            };
            // Voices may not be loaded yet — wait for them
            if (window.speechSynthesis.getVoices().length > 0) {
              speakText(response.response);
            } else {
              window.speechSynthesis.onvoiceschanged = () => speakText(response.response);
              // Fallback: speak with default voice after 500ms
              setTimeout(() => speakText(response.response), 500);
            }
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

  const sendImage = useCallback(
    async (file: File, caption: string = "") => {
      if (isLoading) return;

      const userId = getUserId();
      const userMessage: Message = {
        id: uuidv4(),
        role: "user",
        content: caption ? `📷 ${caption}` : "📷 [Photo]",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        // Convert file to base64
        const buffer = await file.arrayBuffer();
        const base64 = btoa(
          new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), "")
        );
        const format = file.type.split("/")[1] || "jpg";

        const response = await api.chatWithImage(base64, userId, caption, format);
        const assistantMessage: Message = {
          id: uuidv4(),
          role: "assistant",
          content: response.response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Something went wrong";
        setError(errorMsg);
        const errorMessage: Message = {
          id: uuidv4(),
          role: "assistant",
          content: "I had trouble looking at that image 😅 Try again?",
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
    sendImage,
    clearMessages,
    messagesEndRef,
    getUserId,
  };
}
