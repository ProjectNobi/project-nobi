import { API_BASE_URL } from "./constants";
import type {
  ChatResponse,
  MemoriesResponse,
  Memory,
  UserSettings,
  Languages,
  FaqResponse,
  FeedbackResult,
  FeedbackHistoryResponse,
  SupportResult,
} from "./types";

const SESSION_TOKEN_KEY = "nobi_session_token";

class ApiClient {
  private baseUrl: string;
  private sessionToken: string | null = null;
  private sessionPromise: Promise<string> | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    // Restore token from localStorage if available
    if (typeof window !== "undefined") {
      this.sessionToken = localStorage.getItem(SESSION_TOKEN_KEY);
    }
  }

  /**
   * Ensure we have a valid session token. Creates one if needed.
   * Returns the Bearer token string.
   */
  async ensureSession(userId: string): Promise<string> {
    if (this.sessionToken) return this.sessionToken;

    // Deduplicate concurrent session creation requests
    if (this.sessionPromise) return this.sessionPromise;

    this.sessionPromise = (async () => {
      try {
        const res = await fetch(`${this.baseUrl}/api/auth/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId }),
        });
        if (!res.ok) throw new Error("Session creation failed");
        const data = await res.json();
        this.sessionToken = data.token;
        if (typeof window !== "undefined") {
          localStorage.setItem(SESSION_TOKEN_KEY, data.token);
        }
        return data.token;
      } finally {
        this.sessionPromise = null;
      }
    })();

    return this.sessionPromise;
  }

  /**
   * Clear session (e.g. on 401 to force re-auth).
   */
  clearSession(): void {
    this.sessionToken = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem(SESSION_TOKEN_KEY);
    }
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    userId?: string
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    // Build headers with session token if we have a userId
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (userId) {
      const token = await this.ensureSession(userId);
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(url, {
      ...options,
      headers,
    });

    // If 401, clear session and retry once
    if (res.status === 401 && userId) {
      this.clearSession();
      const newToken = await this.ensureSession(userId);
      headers["Authorization"] = `Bearer ${newToken}`;
      const retry = await fetch(url, { ...options, headers });
      if (!retry.ok) {
        const error = await retry.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(error.detail || `HTTP ${retry.status}`);
      }
      return retry.json();
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  async chat(
    message: string,
    userId: string,
    conversationHistory: { role: string; content: string }[] = []
  ): Promise<ChatResponse> {
    return this.request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        user_id: userId,
        conversation_history: conversationHistory,
      }),
    }, userId);
  }

  async getMemories(
    userId: string,
    search?: string,
    limit: number = 50
  ): Promise<MemoriesResponse> {
    const params = new URLSearchParams({ user_id: userId, limit: String(limit) });
    if (search) params.set("search", search);
    return this.request<MemoriesResponse>(`/api/memories?${params}`, {}, userId);
  }

  async deleteMemory(memoryId: string, userId: string): Promise<void> {
    await this.request(`/api/memories/${memoryId}?user_id=${userId}`, {
      method: "DELETE",
    }, userId);
  }

  async exportMemories(userId: string): Promise<{ success: boolean; data: Record<string, unknown> }> {
    return this.request("/api/memories/export", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }, userId);
  }

  async importMemories(userId: string, data: Record<string, unknown>): Promise<{ success: boolean; imported: number }> {
    return this.request("/api/memories/import", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, data }),
    }, userId);
  }

  async forgetAll(userId: string): Promise<void> {
    await this.request(`/api/memories/all?user_id=${userId}`, {
      method: "DELETE",
    }, userId);
  }

  async saveSettings(
    userId: string,
    settings: Partial<UserSettings>
  ): Promise<void> {
    await this.request("/api/settings", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, ...settings }),
    }, userId);
  }

  async getSettings(userId: string): Promise<{ settings: Partial<UserSettings> }> {
    return this.request(`/api/settings?user_id=${userId}`, {}, userId);
  }

  async getLanguages(): Promise<{ languages: Languages }> {
    return this.request("/api/languages");
  }

  async healthCheck(): Promise<{ status: string; llm_configured: boolean }> {
    return this.request("/api/health");
  }

  // ─── Support & Feedback ──────────────────────────────────────

  async getFaq(): Promise<FaqResponse> {
    return this.request<FaqResponse>("/api/faq");
  }

  async askSupport(question: string, userId: string): Promise<SupportResult> {
    return this.request<SupportResult>("/api/support", {
      method: "POST",
      body: JSON.stringify({ question, user_id: userId, platform: "web" }),
    }, userId);
  }

  async submitFeedback(
    message: string,
    userId: string,
    category?: string
  ): Promise<FeedbackResult> {
    return this.request<FeedbackResult>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        message,
        user_id: userId,
        platform: "web",
        category: category ?? null,
      }),
    }, userId);
  }

  async getFeedback(
    userId: string,
    status?: string,
    limit: number = 50
  ): Promise<FeedbackHistoryResponse> {
    const params = new URLSearchParams({ user_id: userId, limit: String(limit) });
    if (status) params.set("status", status);
    return this.request<FeedbackHistoryResponse>(`/api/feedback?${params}`, {}, userId);
  }

  async chatWithImage(
    imageBase64: string,
    userId: string,
    caption: string = "",
    format: string = "jpg"
  ): Promise<{ response: string; success: boolean }> {
    return this.request("/api/chat/image", {
      method: "POST",
      body: JSON.stringify({
        image: imageBase64,
        user_id: userId,
        caption,
        format,
      }),
    }, userId);
  }
}

export const api = new ApiClient();
export default api;
