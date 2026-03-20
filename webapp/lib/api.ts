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

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

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
    });
  }

  async getMemories(
    userId: string,
    search?: string,
    limit: number = 50
  ): Promise<MemoriesResponse> {
    const params = new URLSearchParams({ user_id: userId, limit: String(limit) });
    if (search) params.set("search", search);
    return this.request<MemoriesResponse>(`/api/memories?${params}`);
  }

  async deleteMemory(memoryId: string, userId: string): Promise<void> {
    await this.request(`/api/memories/${memoryId}?user_id=${userId}`, {
      method: "DELETE",
    });
  }

  async exportMemories(userId: string): Promise<{ success: boolean; data: Record<string, unknown> }> {
    return this.request("/api/memories/export", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
  }

  async forgetAll(userId: string): Promise<void> {
    await this.request(`/api/memories/all?user_id=${userId}`, {
      method: "DELETE",
    });
  }

  async saveSettings(
    userId: string,
    settings: Partial<UserSettings>
  ): Promise<void> {
    await this.request("/api/settings", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, ...settings }),
    });
  }

  async getSettings(userId: string): Promise<{ settings: Partial<UserSettings> }> {
    return this.request(`/api/settings?user_id=${userId}`);
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
    });
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
    });
  }

  async getFeedback(
    userId: string,
    status?: string,
    limit: number = 50
  ): Promise<FeedbackHistoryResponse> {
    const params = new URLSearchParams({ user_id: userId, limit: String(limit) });
    if (status) params.set("status", status);
    return this.request<FeedbackHistoryResponse>(`/api/feedback?${params}`);
  }
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
    });
  }
}

export const api = new ApiClient();
export default api;
