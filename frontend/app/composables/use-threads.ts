import { ref, computed, onMounted } from "vue";
import { apiClient } from "~/api/client";
import type { Thread } from "~/types";

export interface UseThreadsOptions {
  agentId?: string;
  autoSelectFirst?: boolean;
}

export function useThreads(options: UseThreadsOptions = {}) {
  const { agentId = "sample_agent", autoSelectFirst = true } = options;

  const threads = ref<Thread[]>([]);
  const activeThreadId = ref<string>("");
  const isLoading = ref<boolean>(true);
  const error = ref<Error | null>(null);

  const activeThread = computed(() =>
    threads.value.find((t) => t.id === activeThreadId.value)
  );

  async function refresh() {
    try {
      isLoading.value = true;
      error.value = null;
      const list = await apiClient.threads.list(agentId);
      threads.value = list;
      return list;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      error.value = e;
      console.error("加载会话列表失败:", e);
      return [];
    } finally {
      isLoading.value = false;
    }
  }

  async function createThread(name = "新对话") {
    try {
      const newThread = await apiClient.threads.create(name, agentId);
      threads.value = [newThread, ...threads.value.filter((t) => t.id !== newThread.id)];
      activeThreadId.value = newThread.id;
      return newThread;
    } catch (err) {
      console.error("创建会话失败:", err);
      throw err;
    }
  }

  async function renameThread(id: string, newName: string) {
    const trimmed = newName.trim();
    if (!trimmed) return;
    try {
      const updated = await apiClient.threads.rename(id, trimmed);
      threads.value = threads.value.map((t) =>
        t.id === id ? { ...t, name: updated.name || trimmed } : t
      );
    } catch (err) {
      console.error("重命名会话失败:", err);
      throw err;
    }
  }

  async function deleteThread(id: string) {
    try {
      await apiClient.threads.delete(id);
      threads.value = threads.value.filter((t) => t.id !== id);
      if (activeThreadId.value === id) {
        if (threads.value.length > 0) {
          activeThreadId.value = threads.value[0].id;
        } else {
          await createThread();
        }
      }
    } catch (err) {
      console.error("删除会话失败:", err);
      throw err;
    }
  }

  function setActiveThreadId(id: string) {
    activeThreadId.value = id;
  }

  onMounted(async () => {
    try {
      isLoading.value = true;
      error.value = null;
      const list = await apiClient.threads.list(agentId);
      threads.value = list;
      if (list && list.length > 0) {
        if (autoSelectFirst && !activeThreadId.value) {
          activeThreadId.value = list[0].id;
        }
      } else {
        await createThread();
      }
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      error.value = e;
      console.error("初始化会话列表失败:", e);
    } finally {
      isLoading.value = false;
    }
  });

  return {
    threads,
    activeThreadId,
    activeThread,
    isLoading,
    error,
    setActiveThreadId,
    createThread,
    renameThread,
    deleteThread,
    refresh,
  };
}
