"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import { useSettings } from "@/hooks/useSettings";
import { useMemories } from "@/hooks/useMemories";

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "zh", name: "Chinese (中文)" },
  { code: "hi", name: "Hindi (हिन्दी)" },
  { code: "es", name: "Spanish (Español)" },
  { code: "fr", name: "French (Français)" },
  { code: "ar", name: "Arabic (العربية)" },
  { code: "bn", name: "Bengali (বাংলা)" },
  { code: "pt", name: "Portuguese (Português)" },
  { code: "ru", name: "Russian (Русский)" },
  { code: "ja", name: "Japanese (日本語)" },
  { code: "ms", name: "Malay/Indonesian (Bahasa)" },
  { code: "de", name: "German (Deutsch)" },
  { code: "ko", name: "Korean (한국어)" },
  { code: "tr", name: "Turkish (Türkçe)" },
  { code: "vi", name: "Vietnamese (Tiếng Việt)" },
  { code: "it", name: "Italian (Italiano)" },
  { code: "th", name: "Thai (ไทย)" },
  { code: "pl", name: "Polish (Polski)" },
  { code: "uk", name: "Ukrainian (Українська)" },
  { code: "nl", name: "Dutch (Nederlands)" },
];

export default function SettingsPage() {
  const { settings, updateSettings } = useSettings();
  const { forgetAll } = useMemories();
  const [showForgetConfirm, setShowForgetConfirm] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleForget = async () => {
    await forgetAll();
    setShowForgetConfirm(false);
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">
          ⚙️ Settings
        </h1>

        <div className="space-y-6">
          {/* Language */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
              🌍 Language
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Choose your preferred language for conversations
            </p>
            <select
              value={settings.language}
              onChange={(e) => updateSettings({ language: e.target.value })}
              className="input-field"
              aria-label="Language selector"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>

          {/* Voice */}
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  🔊 Voice Replies
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Enable voice responses from Nori
                </p>
              </div>
              <button
                onClick={() =>
                  updateSettings({ voice_enabled: !settings.voice_enabled })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.voice_enabled
                    ? "bg-nori-600"
                    : "bg-gray-300 dark:bg-gray-600"
                }`}
                role="switch"
                aria-checked={settings.voice_enabled}
                aria-label="Toggle voice replies"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.voice_enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Proactive Check-ins */}
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  🔔 Proactive Check-ins
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Nori will reach out with birthday reminders, follow-ups, and check-ins
                </p>
              </div>
              <button
                onClick={() =>
                  updateSettings({ proactive_enabled: !settings.proactive_enabled })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.proactive_enabled
                    ? "bg-nori-600"
                    : "bg-gray-300 dark:bg-gray-600"
                }`}
                role="switch"
                aria-checked={settings.proactive_enabled}
                aria-label="Toggle proactive check-ins"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.proactive_enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Companion Name */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
              🤖 Companion Name
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Give your companion a custom name
            </p>
            <input
              type="text"
              value={settings.companion_name}
              onChange={(e) =>
                updateSettings({ companion_name: e.target.value })
              }
              placeholder="Nori"
              className="input-field"
            />
          </div>

          {/* Display Name */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
              👤 Display Name
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              What should Nori call you?
            </p>
            <input
              type="text"
              value={settings.display_name}
              onChange={(e) =>
                updateSettings({ display_name: e.target.value })
              }
              placeholder="Enter your name"
              className="input-field"
            />
          </div>

          {/* About */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              ℹ️ About Nori
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed mb-4">
              Nori is a personal AI companion built by Project Nobi on
              Bittensor (Subnet 272). Your conversations are private, your
              memories are encrypted at rest (AES-128, server-side), and you&apos;re always in control of your
              data.
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="https://github.com/ProjectNobi/project-nobi"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-nori-600 dark:text-nori-400 hover:underline"
              >
                GitHub →
              </a>
              <a
                href="https://bittensor.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-nori-600 dark:text-nori-400 hover:underline"
              >
                Bittensor →
              </a>
            </div>
          </div>

          {/* Danger Zone */}
          <div className="card p-6 border-red-200 dark:border-red-900/50">
            <h2 className="text-lg font-semibold text-red-600 dark:text-red-400 mb-1">
              ⚠️ Danger Zone
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              This will permanently delete all your memories and conversation
              history.
            </p>

            {!showForgetConfirm ? (
              <button
                onClick={() => setShowForgetConfirm(true)}
                className="btn-danger"
              >
                Forget Everything
              </button>
            ) : (
              <div className="flex items-center gap-3">
                <p className="text-sm text-red-600 dark:text-red-400 font-medium">
                  Are you sure?
                </p>
                <button onClick={handleForget} className="btn-danger text-sm">
                  Yes, delete all
                </button>
                <button
                  onClick={() => setShowForgetConfirm(false)}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
