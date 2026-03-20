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

// ─── Support & Feedback ───────────────────────────────────────

export interface FaqEntry {
  id: string;
  topic: string;
  answer: string;
}

export interface FeedbackEntry {
  id: string;
  user_id: string;
  platform: string;
  category: string;
  message: string;
  status: "open" | "in_progress" | "resolved" | "closed" | "duplicate";
  created_at: string;
  resolved_at: string | null;
  admin_notes: string | null;
}

export interface FeedbackResult {
  success: boolean;
  feedback_id: string;
  ticket_id: string;
  category: string;
  acknowledgment: string;
}

export interface SupportResult {
  success: boolean;
  type: "faq" | "ticket" | "error";
  answer: string;
  faq_id?: string;
  topic?: string;
  ticket_id?: string;
}

export interface FeedbackStats {
  total: number;
  open: number;
  resolved: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  avg_resolution_hours: number | null;
}

export interface FaqResponse {
  success: boolean;
  faq: FaqEntry[];
  count: number;
}

export interface FeedbackHistoryResponse {
  success: boolean;
  feedback: FeedbackEntry[];
  count: number;
}
