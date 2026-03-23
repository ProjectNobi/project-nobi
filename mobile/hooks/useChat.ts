/**
 * Chat state management hook.
 * Manages message list, sending, receiving, offline queue, and loading states.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api, type Message } from '../services/api';
import { encryption } from '../services/encryption';
import { auth } from '../services/auth';

// ─── Constants ───────────────────────────────────────────────────────────────

const MESSAGES_KEY = '@nobi/messages';
const PAGE_SIZE = 50;

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const pageRef = useRef(0);

  // ─── Load messages from local storage ─────────────────────────────────

  const loadMessages = useCallback(async () => {
    try {
      const raw = await AsyncStorage.getItem(MESSAGES_KEY);
      if (raw) {
        const all: Message[] = JSON.parse(raw);
        const page = all.slice(0, PAGE_SIZE);
        setMessages(page);
        setHasMore(all.length > PAGE_SIZE);
        pageRef.current = 1;
      }
    } catch {
      setError('Failed to load messages');
    }
  }, []);

  // ─── Load older messages (pagination) ──────────────────────────────────

  const loadOlderMessages = useCallback(async () => {
    if (!hasMore || isLoading) return;

    try {
      setIsLoading(true);
      const raw = await AsyncStorage.getItem(MESSAGES_KEY);
      if (raw) {
        const all: Message[] = JSON.parse(raw);
        const start = pageRef.current * PAGE_SIZE;
        const end = start + PAGE_SIZE;
        const olderPage = all.slice(start, end);

        if (olderPage.length > 0) {
          setMessages((prev) => [...prev, ...olderPage]);
          pageRef.current += 1;
          setHasMore(end < all.length);
        } else {
          setHasMore(false);
        }
      }
    } catch {
      setError('Failed to load older messages');
    } finally {
      setIsLoading(false);
    }
  }, [hasMore, isLoading]);

  // ─── Save messages to local storage ────────────────────────────────────

  const saveMessages = useCallback(async (msgs: Message[]) => {
    try {
      await AsyncStorage.setItem(MESSAGES_KEY, JSON.stringify(msgs));
    } catch {
      // Silent fail — messages still in state
    }
  }, []);

  // ─── Send a message ────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (content: string) => {
      const user = auth.getUser();
      if (!user || !content.trim()) return;

      setError(null);

      // Create user message
      const encryptionOn = user.preferences.encryptionEnabled;
      const userMessage: Message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        role: 'user',
        content: content.trim(),
        timestamp: Date.now(),
        status: 'sending',
        isEncrypted: encryptionOn,
      };

      // Add to UI immediately
      setMessages((prev) => {
        const updated = [userMessage, ...prev];
        saveMessages(updated);
        return updated;
      });

      setIsTyping(true);

      try {
        // Encrypt if enabled
        const messageToSend = encryptionOn
          ? await encryption.encrypt(user.id, content.trim())
          : content.trim();

        // Send to API
        const result = await api.sendMessage(user.id, messageToSend);

        if (result.ok && result.data) {
          // Decrypt response if needed
          const responseText = encryptionOn
            ? await encryption.decrypt(user.id, result.data.response)
            : result.data.response;

          // Mark user message as sent
          userMessage.status = 'sent';

          // Create Nori's response
          const noriMessage: Message = {
            id: `msg_${Date.now()}_nori_${Math.random().toString(36).slice(2, 8)}`,
            role: 'nori',
            content: responseText,
            timestamp: Date.now(),
            status: 'sent',
            isEncrypted: encryptionOn,
          };

          setMessages((prev) => {
            const updated = prev.map((m) =>
              m.id === userMessage.id ? { ...m, status: 'sent' as const } : m,
            );
            const withResponse = [noriMessage, ...updated];
            saveMessages(withResponse);
            return withResponse;
          });
        } else if (result.error === 'offline') {
          // Message queued for later
          setMessages((prev) =>
            prev.map((m) =>
              m.id === userMessage.id ? { ...m, status: 'queued' as const } : m,
            ),
          );
        } else {
          // Error
          setMessages((prev) =>
            prev.map((m) =>
              m.id === userMessage.id ? { ...m, status: 'error' as const } : m,
            ),
          );
          setError(result.error ?? 'Failed to send message');
        }
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMessage.id ? { ...m, status: 'error' as const } : m,
          ),
        );
        setError('Something went wrong');
      } finally {
        setIsTyping(false);
      }
    },
    [saveMessages],
  );

  // ─── Send an image ─────────────────────────────────────────────────────

  const sendImage = useCallback(
    async (imageBase64: string, caption: string, imageUri: string) => {
      const user = auth.getUser();
      if (!user) return;

      setError(null);

      const userMessage: Message = {
        id: `msg_${Date.now()}_img_${Math.random().toString(36).slice(2, 8)}`,
        role: 'user',
        content: caption || '📷 Sent an image',
        timestamp: Date.now(),
        imageUri,
        status: 'sending',
      };

      setMessages((prev) => {
        const updated = [userMessage, ...prev];
        saveMessages(updated);
        return updated;
      });

      setIsTyping(true);

      try {
        const result = await api.sendImage(user.id, imageBase64, caption);

        userMessage.status = 'sent';

        if (result.ok && result.data) {
          const noriMessage: Message = {
            id: `msg_${Date.now()}_nori_img`,
            role: 'nori',
            content: result.data.response,
            timestamp: Date.now(),
            imageDescription: result.data.description,
            status: 'sent',
          };

          setMessages((prev) => {
            const updated = prev.map((m) =>
              m.id === userMessage.id ? { ...m, status: 'sent' as const } : m,
            );
            return [noriMessage, ...updated];
          });
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === userMessage.id ? { ...m, status: 'error' as const } : m,
            ),
          );
          setError('Failed to analyze image');
        }
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMessage.id ? { ...m, status: 'error' as const } : m,
          ),
        );
      } finally {
        setIsTyping(false);
      }
    },
    [saveMessages],
  );

  // ─── Retry failed message ──────────────────────────────────────────────

  const retryMessage = useCallback(
    async (messageId: string) => {
      const msg = messages.find((m) => m.id === messageId);
      if (!msg || msg.status !== 'error') return;

      // Remove the failed message
      setMessages((prev) => prev.filter((m) => m.id !== messageId));

      // Re-send
      await sendMessage(msg.content);
    },
    [messages, sendMessage],
  );

  // ─── Clear chat ────────────────────────────────────────────────────────

  const clearChat = useCallback(async () => {
    setMessages([]);
    await AsyncStorage.removeItem(MESSAGES_KEY);
  }, []);

  // ─── Init ──────────────────────────────────────────────────────────────

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  return {
    messages,
    isLoading,
    isTyping,
    error,
    hasMore,
    sendMessage,
    sendImage,
    retryMessage,
    loadOlderMessages,
    clearChat,
  };
}
