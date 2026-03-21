"use client";

import { useState, useEffect, useRef } from "react";
import Navbar from "@/components/Navbar";
import { useSupport } from "@/hooks/useSupport";
import type { FaqEntry, FeedbackEntry } from "@/lib/types";

const USER_ID_KEY = "nobi_user_id";
const CATEGORIES = [
  { value: "", label: "Auto-detect" },
  { value: "bug_report", label: "🐛 Bug Report" },
  { value: "feature_request", label: "💡 Feature Request" },
  { value: "general_feedback", label: "💬 General Feedback" },
  { value: "question", label: "❓ Question" },
  { value: "complaint", label: "😤 Complaint" },
];

const STATUS_BADGES: Record<string, { label: string; color: string }> = {
  open: { label: "Open", color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  in_progress: { label: "In Progress", color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300" },
  resolved: { label: "Resolved", color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300" },
  closed: { label: "Closed", color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
  duplicate: { label: "Duplicate", color: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300" },
};

// ─── Chat message types ────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "nori";
  content: string;
  isTicket?: boolean;
  ticketId?: string;
}

// ─── Support page ─────────────────────────────────────────────

export default function SupportPage() {
  const [userId, setUserId] = useState("web_user");
  const [activeTab, setActiveTab] = useState<"chat" | "faq" | "feedback" | "history">("chat");
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);

  // Chat
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "nori",
      content:
        "Hi! 👋 I'm Nori. Ask me anything about Project Nobi and I'll answer right away. If I can't answer, I'll make sure the team gets back to you!",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Feedback form
  const [fbMessage, setFbMessage] = useState("");
  const [fbCategory, setFbCategory] = useState("");

  const {
    faq,
    faqLoading,
    loadFaq,
    askSupport,
    supportLoading,
    submitFeedback,
    feedbackLoading,
    feedbackResult,
    feedbackHistory,
    historyLoading,
    loadFeedbackHistory,
  } = useSupport();

  // Load user ID from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(USER_ID_KEY);
      if (stored) setUserId(stored);
      else {
        const newId = `web_${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem(USER_ID_KEY, newId);
        setUserId(newId);
      }
    }
  }, []);

  // Auto-load FAQ and history when tab changes
  useEffect(() => {
    if (activeTab === "faq" && faq.length === 0) loadFaq();
    if (activeTab === "history") loadFeedbackHistory(userId);
  }, [activeTab, userId, faq.length, loadFaq, loadFeedbackHistory]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // ── Chat send ──────────────────────────────────────────────

  const handleChatSend = async () => {
    const q = chatInput.trim();
    if (!q || supportLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: q,
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");

    // Local greeting/FAQ matching first (instant, no API call)
    const qLower = q.toLowerCase().trim();
    const greetings = ["hello", "hi", "hey", "yo", "sup", "howdy", "hola", "good morning", "good evening", "hello there", "hi there"];
    const isGreeting = greetings.some(g => qLower === g || qLower === g + " there" || qLower === g + "!");
    
    if (isGreeting) {
      const noriMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "nori",
        content: "Hey there! 👋 I'm here to help with questions about Project Nobi. You can ask me about how Nori works, mining, privacy, or anything else. What would you like to know?",
      };
      setChatMessages((prev) => [...prev, noriMsg]);
      return;
    }

    const result = await askSupport(q, userId);
    if (result) {
      if (result.type === "ticket") {
        // No FAQ match — ask Nori via chat API for a real answer
        try {
          const chatRes = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL || "https://api.projectnobi.ai"}/api/chat`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: q, user_id: userId }),
            }
          );
          const chatData = await chatRes.json();
          if (chatData.response) {
            const noriMsg: ChatMessage = {
              id: (Date.now() + 1).toString(),
              role: "nori",
              content: chatData.response,
            };
            setChatMessages((prev) => [...prev, noriMsg]);
            return;
          }
        } catch {
          // Chat API failed — show fallback
        }
        const noriMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "nori",
          content: "Hmm, I'm having trouble answering that right now. Try the Chat page for a full conversation with Nori! 💬",
        };
        setChatMessages((prev) => [...prev, noriMsg]);
      } else {
        const noriMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "nori",
          content: result.answer,
        };
        setChatMessages((prev) => [...prev, noriMsg]);
      }
    }
  };

  // ── Feedback submit ───────────────────────────────────────

  const handleFeedbackSubmit = async () => {
    if (!fbMessage.trim() || feedbackLoading) return;
    await submitFeedback(fbMessage.trim(), userId, fbCategory || undefined);
    setFbMessage("");
    setFbCategory("");
  };

  // ─── Render ────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            🆘 Support Center
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Ask Nori a question, browse the FAQ, or send us feedback
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-1">
          {(["chat", "faq", "feedback", "history"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-colors capitalize ${
                activeTab === tab
                  ? "bg-nori-600 text-white"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              {tab === "chat" && "💬 "}
              {tab === "faq" && "📚 "}
              {tab === "feedback" && "📝 "}
              {tab === "history" && "📋 "}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* ── Chat Tab ─────────────────────────────────────── */}
        {activeTab === "chat" && (
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 flex flex-col h-[500px]">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "nori" && (
                    <div className="w-8 h-8 rounded-full bg-nori-100 dark:bg-nori-900/30 flex items-center justify-center text-sm mr-2 flex-shrink-0 mt-1">
                      🤖
                    </div>
                  )}
                  <div
                    className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-nori-600 text-white rounded-br-sm"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>

                  </div>
                </div>
              ))}
              {supportLoading && (
                <div className="flex justify-start">
                  <div className="w-8 h-8 rounded-full bg-nori-100 dark:bg-nori-900/30 flex items-center justify-center text-sm mr-2">
                    🤖
                  </div>
                  <div className="bg-gray-100 dark:bg-gray-800 px-4 py-3 rounded-2xl rounded-bl-sm">
                    <span className="inline-flex gap-1">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    </span>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleChatSend()}
                placeholder="Ask me anything about Nobi..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white text-sm outline-none focus:ring-2 focus:ring-nori-500 focus:border-transparent"
                disabled={supportLoading}
              />
              <button
                onClick={handleChatSend}
                disabled={!chatInput.trim() || supportLoading}
                className="px-4 py-2.5 bg-nori-600 hover:bg-nori-700 disabled:opacity-40 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* ── FAQ Tab ──────────────────────────────────────── */}
        {activeTab === "faq" && (
          <div className="space-y-3">
            {faqLoading && (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                Loading FAQ...
              </div>
            )}
            {!faqLoading && faq.length === 0 && (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                No FAQ entries found.
              </div>
            )}
            {faq.map((entry: FaqEntry) => (
              <div
                key={entry.id}
                className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden"
              >
                <button
                  onClick={() =>
                    setExpandedFaq(expandedFaq === entry.id ? null : entry.id)
                  }
                  className="w-full px-5 py-4 flex items-center justify-between text-left"
                >
                  <span className="font-medium text-gray-900 dark:text-white text-sm">
                    {entry.topic}
                  </span>
                  <span className="text-gray-400 ml-4 flex-shrink-0 text-lg">
                    {expandedFaq === entry.id ? "▲" : "▼"}
                  </span>
                </button>
                {expandedFaq === entry.id && (
                  <div className="px-5 pb-5 text-sm text-gray-600 dark:text-gray-300 leading-relaxed border-t border-gray-100 dark:border-gray-800 pt-3 whitespace-pre-wrap">
                    {entry.answer}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── Feedback Tab ─────────────────────────────────── */}
        {activeTab === "feedback" && (
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6">
            {feedbackResult ? (
              <div className="text-center py-8">
                <div className="text-5xl mb-4">✅</div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Feedback Received!
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">
                  {feedbackResult.acknowledgment}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 font-mono">
                  Ticket #{feedbackResult.ticket_id}
                </p>
                <button
                  onClick={() => setActiveTab("history")}
                  className="mt-6 px-4 py-2 text-sm text-nori-600 dark:text-nori-400 hover:underline"
                >
                  View your feedback history →
                </button>
              </div>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                  Send Feedback
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
                  Bug reports, feature ideas, or general thoughts — we read everything 💙
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Category
                    </label>
                    <select
                      value={fbCategory}
                      onChange={(e) => setFbCategory(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white text-sm outline-none focus:ring-2 focus:ring-nori-500"
                    >
                      {CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>
                          {cat.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Message
                    </label>
                    <textarea
                      value={fbMessage}
                      onChange={(e) => setFbMessage(e.target.value)}
                      rows={5}
                      placeholder="Tell us what's on your mind..."
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white text-sm outline-none focus:ring-2 focus:ring-nori-500 resize-none"
                    />
                    <div className="mt-1 text-right text-xs text-gray-400">
                      {fbMessage.length}/10000
                    </div>
                  </div>

                  <button
                    onClick={handleFeedbackSubmit}
                    disabled={!fbMessage.trim() || feedbackLoading}
                    className="w-full py-3 bg-nori-600 hover:bg-nori-700 disabled:opacity-40 text-white rounded-xl font-medium text-sm transition-colors"
                  >
                    {feedbackLoading ? "Sending..." : "Send Feedback"}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── History Tab ──────────────────────────────────── */}
        {activeTab === "history" && (
          <div className="space-y-3">
            {historyLoading && (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                Loading your feedback...
              </div>
            )}
            {!historyLoading && feedbackHistory.length === 0 && (
              <div className="text-center py-16">
                <div className="text-5xl mb-4">📭</div>
                <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  No feedback yet
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  When you submit feedback, it&apos;ll appear here.
                </p>
                <button
                  onClick={() => setActiveTab("feedback")}
                  className="mt-4 px-4 py-2 text-sm text-nori-600 dark:text-nori-400 hover:underline"
                >
                  Send your first feedback →
                </button>
              </div>
            )}
            {feedbackHistory.map((entry: FeedbackEntry) => {
              const badge = STATUS_BADGES[entry.status] || STATUS_BADGES.open;
              return (
                <div
                  key={entry.id}
                  className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono text-gray-400">
                        #{entry.id.slice(0, 8).toUpperCase()}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.color}`}>
                        {badge.label}
                      </span>
                      <span className="text-xs text-gray-400 capitalize">
                        {entry.category.replace("_", " ")}
                      </span>
                    </div>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {new Date(entry.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                    {entry.message}
                  </p>
                  {entry.admin_notes && (
                    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        💬 Response from team:
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-300">
                        {entry.admin_notes}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
