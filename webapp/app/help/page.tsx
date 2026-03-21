"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";
import type { FaqEntry } from "@/lib/types";

const FEATURES = [
  {
    icon: "💬",
    title: "Chat",
    description:
      "Have natural conversations with Nori. She remembers your preferences, past events, and important moments in your life.",
  },
  {
    icon: "🧠",
    title: "Memory",
    description:
      "Nori builds a private memory of you over time — facts, preferences, events, and emotions — so every conversation feels personal.",
  },
  {
    icon: "🔊",
    title: "Voice Replies",
    description:
      "Enable voice mode in Settings and Nori will respond with warm, natural speech instead of just text.",
  },
  {
    icon: "📸",
    title: "Photo Sharing",
    description:
      "Send photos to Nori in chat. She can describe what she sees, remember visual moments, and respond contextually.",
  },
  {
    icon: "📥",
    title: "Export & Import Memories",
    description:
      "Download all your memories as a JSON file, or import memories from a backup. Your data is always yours.",
  },
  {
    icon: "🌍",
    title: "Multilingual",
    description:
      "Nori speaks your language. Choose from 20+ languages in Settings and she'll respond naturally in your preferred tongue.",
  },
  {
    icon: "🔔",
    title: "Proactive Check-ins",
    description:
      "When enabled, Nori will reach out proactively — birthday reminders, follow-ups, and thoughtful check-ins.",
  },
  {
    icon: "🤖",
    title: "Custom Companion Name",
    description:
      "Give your AI companion a name that feels right to you. Personalise your experience in Settings.",
  },
  {
    icon: "🔒",
    title: "Privacy First",
    description:
      "Your memories are private and encrypted. Built on Bittensor's decentralised network — no surveillance, no ads.",
  },
];

const HOW_TO = [
  {
    icon: "💬",
    title: "Chat",
    steps: [
      "Go to the Chat page from the navigation.",
      "Type your message and press Enter (or Shift+Enter for a new line).",
      "Nori will reply with context from your past conversations.",
    ],
  },
  {
    icon: "🔊",
    title: "Voice",
    steps: [
      "Go to Settings → Voice Replies.",
      "Toggle Voice Replies on.",
      "Return to Chat — Nori's responses will now include audio playback.",
    ],
  },
  {
    icon: "📸",
    title: "Photos",
    steps: [
      "In Chat, click the 📎 attachment icon.",
      "Select a photo from your device.",
      "Optionally add a caption, then send.",
    ],
  },
  {
    icon: "🧠",
    title: "Memories",
    steps: [
      "Go to the Memories page to see everything Nori knows about you.",
      "Use the search bar to find specific memories.",
      "Delete individual memories or export all as JSON.",
      "Import a previous backup with the Import JSON button.",
    ],
  },
  {
    icon: "⚙️",
    title: "Settings",
    steps: [
      "Change language, voice, display name, companion name, and proactive check-ins.",
      "Use 'Forget Everything' in the Danger Zone to wipe all memories.",
    ],
  },
];

const SHORTCUTS = [
  { keys: "Enter", description: "Send message" },
  { keys: "Shift + Enter", description: "New line in message" },
  { keys: "Esc", description: "Close modals / cancel" },
];

const LINKS = [
  {
    icon: "⛏️",
    label: "Mining Guide",
    href: "https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md",
    description: "Learn how to mine on Bittensor SN272",
  },
  {
    icon: "📄",
    label: "Whitepaper",
    href: "https://github.com/ProjectNobi/project-nobi/blob/main/docs/WHITEPAPER.md",
    description: "Technical overview of Project Nobi",
  },
  {
    icon: "💬",
    label: "Discord",
    href: "https://discord.gg/e6StezHM",
    description: "Join our community",
  },
  {
    icon: "🤖",
    label: "Telegram Bot",
    href: "https://t.me/ProjectNobiBot",
    description: "Chat with Nori on Telegram",
  },
];

export default function HelpPage() {
  const [faq, setFaq] = useState<FaqEntry[]>([]);
  const [faqLoading, setFaqLoading] = useState(true);
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    api
      .getFaq()
      .then((res) => setFaq(res.faq))
      .catch(() => setFaq([]))
      .finally(() => setFaqLoading(false));
  }, []);

  if (!mounted) return null;

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">
            ❓ Help & Guide
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            Everything you need to know about Nori
          </p>
        </div>

        {/* Features */}
        <section className="mb-12">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
            ✨ Features
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="card p-5">
                <div className="text-2xl mb-3">{f.icon}</div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-1 text-sm">
                  {f.title}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                  {f.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* How to use */}
        <section className="mb-12">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
            🚀 How to Use
          </h2>
          <div className="space-y-4">
            {HOW_TO.map((section) => (
              <div key={section.title} className="card p-6">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                  <span>{section.icon}</span>
                  {section.title}
                </h3>
                <ol className="space-y-2">
                  {section.steps.map((step, i) => (
                    <li key={i} className="flex gap-3 text-sm text-gray-600 dark:text-gray-300">
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-nori-100 dark:bg-nori-900/30 text-nori-700 dark:text-nori-300 flex items-center justify-center text-xs font-bold">
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </section>

        {/* Keyboard shortcuts */}
        <section className="mb-12">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
            ⌨️ Keyboard Shortcuts
          </h2>
          <div className="card divide-y divide-gray-100 dark:divide-gray-800">
            {SHORTCUTS.map((s) => (
              <div key={s.keys} className="flex items-center justify-between px-6 py-4">
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  {s.description}
                </span>
                <kbd className="px-3 py-1.5 text-xs font-mono bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg border border-gray-200 dark:border-gray-700">
                  {s.keys}
                </kbd>
              </div>
            ))}
          </div>
        </section>

        {/* Links */}
        <section className="mb-12">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
            🔗 Links
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="card p-5 flex items-start gap-4 hover:border-nori-300 dark:hover:border-nori-700 transition-colors group"
              >
                <span className="text-2xl">{link.icon}</span>
                <div>
                  <div className="font-semibold text-gray-900 dark:text-white text-sm group-hover:text-nori-600 dark:group-hover:text-nori-400 transition-colors">
                    {link.label} →
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {link.description}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-12">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
            📚 FAQ
          </h2>

          {faqLoading && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <div className="w-6 h-6 border-2 border-nori-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading FAQ...
            </div>
          )}

          {!faqLoading && faq.length === 0 && (
            <div className="card p-6 text-center text-gray-500 dark:text-gray-400 text-sm">
              No FAQ entries available. Check back soon!
            </div>
          )}

          {!faqLoading && faq.length > 0 && (
            <div className="space-y-3">
              {faq.map((entry) => (
                <div
                  key={entry.id}
                  className="card overflow-hidden"
                >
                  <button
                    onClick={() =>
                      setExpandedFaq(expandedFaq === entry.id ? null : entry.id)
                    }
                    className="w-full px-6 py-4 flex items-center justify-between text-left"
                  >
                    <span className="font-medium text-gray-900 dark:text-white text-sm">
                      {entry.topic}
                    </span>
                    <span className="text-gray-400 ml-4 flex-shrink-0 text-sm">
                      {expandedFaq === entry.id ? "▲" : "▼"}
                    </span>
                  </button>
                  {expandedFaq === entry.id && (
                    <div className="px-6 pb-5 text-sm text-gray-600 dark:text-gray-300 leading-relaxed border-t border-gray-100 dark:border-gray-800 pt-4 whitespace-pre-wrap">
                      {entry.answer}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Footer note */}
        <div className="text-center py-6 text-sm text-gray-400 dark:text-gray-500">
          Still need help?{" "}
          <a href="/support" className="text-nori-600 dark:text-nori-400 hover:underline">
            Visit the Support Center →
          </a>
        </div>
      </div>
    </div>
  );
}
