export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface Memory {
  id: string;
  memory_type: string;
  content: string;
  importance: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface UserSettings {
  language: string;
  voice_enabled: boolean;
  theme: "light" | "dark" | "system";
  display_name: string;
}

export interface ChatResponse {
  response: string;
  memories_used: string[];
}

export interface MemoriesResponse {
  memories: Memory[];
  count: number;
}

export interface Language {
  name: string;
  native: string;
  greeting: string;
}

export type Languages = Record<string, Language>;
