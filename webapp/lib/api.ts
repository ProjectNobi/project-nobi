import { API_BASE_URL } from "./constants";
import type { ChatResponse, MemoriesResponse, Memory, UserSettings, Languages } from "./types";

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
}

export const api = new ApiClient();
export default api;
