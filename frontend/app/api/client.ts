/**
 * 统一 RESTful API 客户端
 * 负责与后端 FastAPI (/api/...) 进行全部业务与数据交互，
 * 顶层统一携带必需的 X-User-Id 请求头。
 */
import type { HealthResponse, Thread, ThreadListResponse, ThreadMessageItem, ThreadMessagesResponse, UploadResponse } from "~/types";

const API_BASE = (
  import.meta.env.VITE_API_PREFIX ||
  import.meta.env.API_PREFIX ||
  "/api"
).replace(/\/$/, "");

export function getUserId(): string {
  if (typeof window === "undefined") return "default";
  let uid = localStorage.getItem("deepagent_user_id");
  if (!uid) {
    const randomHex =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID().slice(0, 8)
        : Math.random().toString(36).substring(2, 10);
    uid = `user_${randomHex}`;
    try {
      localStorage.setItem("deepagent_user_id", uid);
    } catch (_) {}
  }
  return uid;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("X-User-Id")) {
    headers.set("X-User-Id", getUserId());
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `请求失败: HTTP ${res.status}`);
  }

  return res.json();
}

export const apiClient = {
  /**
   * 会话线程管理
   */
  threads: {
    async list(agentId = "sample_agent"): Promise<Thread[]> {
      const data = await request<ThreadListResponse>(`/threads?agentId=${encodeURIComponent(agentId)}`);
      return data.threads || [];
    },

    async create(name = "新对话", agentId = "sample_agent", id?: string): Promise<Thread> {
      const threadId =
        id || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `thread_${Date.now()}`);
      const data = await request<any>("/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: threadId, name, agentId }),
      });
      return data.thread || data;
    },

    async rename(id: string, name: string): Promise<Thread> {
      const data = await request<any>(`/threads/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      return data.thread || { id, name, ...data };
    },

    async delete(id: string): Promise<void> {
      await request<void>(`/threads/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    },

    async getMessages(threadId: string): Promise<ThreadMessageItem[]> {
      const data = await request<ThreadMessagesResponse>(`/threads/${encodeURIComponent(threadId)}/messages`);
      return data.messages || [];
    },
  },

  /**
   * 多模态文件与附件上传至沙箱环境
   */
  upload: {
    async file(file: File, threadId: string, userId?: string): Promise<UploadResponse> {
      const activeUserId = userId || getUserId();
      const formData = new FormData();
      formData.append("file", file);
      formData.append("thread_id", threadId);

      return request<UploadResponse>("/upload", {
        method: "POST",
        headers: {
          "X-User-Id": activeUserId,
        },
        body: formData,
      });
    },
  },

  /**
   * 系统健康探活
   */
  system: {
    async health(): Promise<HealthResponse> {
      return request<HealthResponse>("/health");
    },
  },
};
