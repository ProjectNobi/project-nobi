"use client";

import { useState, useCallback } from "react";
import api from "@/lib/api";
import type { FaqEntry, FeedbackEntry, SupportResult, FeedbackResult } from "@/lib/types";

interface UseSupportReturn {
  // FAQ
  faq: FaqEntry[];
  faqLoading: boolean;
  faqError: string | null;
  loadFaq: () => Promise<void>;

  // Support chat
  supportResult: SupportResult | null;
  supportLoading: boolean;
  supportError: string | null;
  askSupport: (question: string, userId: string) => Promise<SupportResult | null>;

  // Feedback submission
  feedbackResult: FeedbackResult | null;
  feedbackLoading: boolean;
  feedbackError: string | null;
  submitFeedback: (
    message: string,
    userId: string,
    category?: string
  ) => Promise<FeedbackResult | null>;

  // User feedback history
  feedbackHistory: FeedbackEntry[];
  historyLoading: boolean;
  loadFeedbackHistory: (userId: string) => Promise<void>;

  // Reset
  reset: () => void;
}

export function useSupport(): UseSupportReturn {
  const [faq, setFaq] = useState<FaqEntry[]>([]);
  const [faqLoading, setFaqLoading] = useState(false);
  const [faqError, setFaqError] = useState<string | null>(null);

  const [supportResult, setSupportResult] = useState<SupportResult | null>(null);
  const [supportLoading, setSupportLoading] = useState(false);
  const [supportError, setSupportError] = useState<string | null>(null);

  const [feedbackResult, setFeedbackResult] = useState<FeedbackResult | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const [feedbackHistory, setFeedbackHistory] = useState<FeedbackEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadFaq = useCallback(async () => {
    setFaqLoading(true);
    setFaqError(null);
    try {
      const data = await api.getFaq();
      setFaq(data.faq);
    } catch (err) {
      setFaqError(err instanceof Error ? err.message : "Failed to load FAQ");
    } finally {
      setFaqLoading(false);
    }
  }, []);

  const askSupport = useCallback(
    async (question: string, userId: string): Promise<SupportResult | null> => {
      setSupportLoading(true);
      setSupportError(null);
      try {
        const result = await api.askSupport(question, userId);
        setSupportResult(result);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to submit question";
        setSupportError(msg);
        return null;
      } finally {
        setSupportLoading(false);
      }
    },
    []
  );

  const submitFeedback = useCallback(
    async (
      message: string,
      userId: string,
      category?: string
    ): Promise<FeedbackResult | null> => {
      setFeedbackLoading(true);
      setFeedbackError(null);
      try {
        const result = await api.submitFeedback(message, userId, category);
        setFeedbackResult(result);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to submit feedback";
        setFeedbackError(msg);
        return null;
      } finally {
        setFeedbackLoading(false);
      }
    },
    []
  );

  const loadFeedbackHistory = useCallback(async (userId: string) => {
    setHistoryLoading(true);
    try {
      const data = await api.getFeedback(userId);
      setFeedbackHistory(data.feedback);
    } catch {
      // silently fail — user may not have any feedback yet
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSupportResult(null);
    setSupportError(null);
    setFeedbackResult(null);
    setFeedbackError(null);
  }, []);

  return {
    faq,
    faqLoading,
    faqError,
    loadFaq,
    supportResult,
    supportLoading,
    supportError,
    askSupport,
    feedbackResult,
    feedbackLoading,
    feedbackError,
    submitFeedback,
    feedbackHistory,
    historyLoading,
    loadFeedbackHistory,
    reset,
  };
}
