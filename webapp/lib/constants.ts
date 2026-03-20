export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8042";

export const APP_NAME = "Nori";
export const APP_DESCRIPTION = "Your personal AI companion — warm, private, and always there for you.";

export const STORAGE_KEYS = {
  USER_ID: "nobi_user_id",
  SETTINGS: "nobi_settings",
  ONBOARDED: "nobi_onboarded",
  THEME: "nobi_theme",
} as const;

export const DEFAULT_SETTINGS = {
  language: "en",
  voice_enabled: false,
  theme: "system" as const,
  display_name: "",
  proactive_enabled: false,
  companion_name: "",
};

export const MEMORY_TYPE_LABELS: Record<string, string> = {
  fact: "📋 Fact",
  event: "📅 Event",
  preference: "❤️ Preference",
  context: "🔗 Context",
  emotion: "💭 Emotion",
};

export const MEMORY_TYPE_COLORS: Record<string, string> = {
  fact: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300",
  event: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300",
  preference: "bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300",
  context: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300",
  emotion: "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300",
};
