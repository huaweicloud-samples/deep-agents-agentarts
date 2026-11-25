<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from "vue";
import {
  CopilotChat,
  CopilotChatAttachmentRenderer,
  useAgent,
  useCopilotChatConfiguration,
} from "@copilotkit/vue/v2";
import { apiClient } from "~/api/client";
import { useAttachments } from "~/composables/use-attachments";
import type { Thread } from "~/types";

const props = defineProps<{
  activeThread?: Thread;
  isThreadsLoading?: boolean;
}>();

const { attachmentsConfig } = useAttachments(() => props.activeThread?.id);
const threadName = computed(() => props.activeThread?.name || props.activeThread?.title || "新对话");

const config = useCopilotChatConfiguration();
const { agent } = useAgent({ agentId: "sample_agent" });

const lastFetchedThreadId = ref<string | null>(null);
const isLoadingMessages = ref(false);
const hasHistory = ref(false);
let pendingMessages: { threadId: string; messages: any[] } | null = null;
let historyTimer: ReturnType<typeof setTimeout> | null = null;

const isDataLoading = computed(() =>
  Boolean(props.isThreadsLoading || isLoadingMessages.value || !agent.value)
);
const canShowWelcome = computed(() => !isDataLoading.value && !hasHistory.value);

function applyMessages(threadId: string, messages: any[]) {
  if (props.activeThread?.id !== threadId || !agent.value) return;
  agent.value.setMessages(messages);
}

// 当 CopilotKitProvider 完成 /info 初始化并注册真实 agent 实例时，同步回填已拉取的历史消息
watch(
  () => agent.value,
  (newAgent) => {
    if (!newAgent || !pendingMessages) return;
    if (pendingMessages.threadId === props.activeThread?.id) {
      applyMessages(pendingMessages.threadId, pendingMessages.messages);
    }
  }
);

// 遵循官方文档 Manual hydration：当选中已有持久化会话时拉取并回填消息
watch(
  () => props.activeThread?.id,
  (threadId) => {
    if (!threadId) return;
    if (lastFetchedThreadId.value === threadId) return;
    lastFetchedThreadId.value = threadId;
    pendingMessages = null;

    if (historyTimer) {
      clearTimeout(historyTimer);
      historyTimer = null;
    }

    // 使用 explicit: false 同步切换 threadId，避免 CopilotChat 触发 connectAgent
    // 在异步回放阶段清空已回填的历史消息导致闪现后白屏
    config.value?.setActiveThreadId(threadId, { explicit: false });
    isLoadingMessages.value = true;
    hasHistory.value = false;

    apiClient.threads
      .getMessages(threadId)
      .then((history) => {
        // 若用户已切换至其他会话，放弃当前回填
        if (props.activeThread?.id !== threadId) {
          return;
        }

        const resolveContent = (val: any) => {
          if (Array.isArray(val)) return val;
          return val ?? "";
        };

        const formatted = history
          .map((m) => {
            if (m.role === "assistant") {
              const item: Record<string, any> = {
                id: m.id,
                role: "assistant",
                content: resolveContent(m.content),
              };
              if (m.toolCalls && m.toolCalls.length > 0) {
                item.toolCalls = m.toolCalls;
              }
              return item;
            }
            if (m.role === "tool") {
              return {
                id: m.id,
                role: "tool",
                content: resolveContent(m.content),
                toolCallId: m.toolCallId || "",
              };
            }
            if (m.role === "user") {
              return {
                id: m.id,
                role: "user",
                content: resolveContent(m.content),
              };
            }
            if (m.role === "reasoning") {
              return {
                id: m.id,
                role: "reasoning",
                content: resolveContent(m.content),
              };
            }
            return null;
          })
          .filter(Boolean);

        hasHistory.value = formatted.length > 0;
        pendingMessages = { threadId, messages: formatted };

        historyTimer = setTimeout(() => {
          applyMessages(threadId, formatted);
          if (props.activeThread?.id === threadId) {
            isLoadingMessages.value = false;
          }
        }, 0);
      })
      .catch((err) => {
        console.error("加载会话历史消息失败:", err);
        if (props.activeThread?.id === threadId) {
          isLoadingMessages.value = false;
        }
      });
  },
  { immediate: true }
);

onUnmounted(() => {
  if (historyTimer) {
    clearTimeout(historyTimer);
  }
});

const labels = computed(() => ({
  chatInputPlaceholder: "输入消息，或点击左下角回形针/拖拽上传图片与文档...",
  chatInputToolbarAddButtonLabel: "上传附件 (支持图片、PDF、TXT、Markdown及代码文档)",
  welcomeMessageText: `你好！这是对话 “${threadName.value}”。已开启多模态能力，你可以向我提问，或上传图片、PDF报告、各类文本代码文档进行深入分析。`,
}));

function extractText(content: any): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter((p) => p && typeof p === "object" && p.type === "text" && typeof p.text === "string")
      .map((p) => p.text)
      .join("\n");
  }
  return "";
}

function handleError(event: any) {
  console.error("CopilotChat 运行异常:", event);
}
</script>

<template>
  <div class="relative h-full w-full flex-1 flex flex-col min-h-0">
    <CopilotChat
      agent-id="sample_agent"
      class="h-full w-full flex-1"
      :attachments="attachmentsConfig"
      :labels="labels"
      :welcome-screen="canShowWelcome"
      :on-error="handleError"
    >
      <!-- 使用官方 CopilotChatAttachmentRenderer 渲染用户消息内的附件胶囊卡片与图片 -->
      <template #user-message="{ message }">
        <div class="cpk:flex cpk:flex-col cpk:items-end cpk:gap-2 cpk:group cpk:pt-6 w-full">
          <!-- 官方附件渲染器列表：渲染为文件胶囊卡片或图片预览 -->
          <div
            v-if="Array.isArray(message.content)"
            class="cpk:flex cpk:flex-wrap cpk:gap-2 cpk:justify-end cpk:max-w-[85%]"
          >
            <template v-for="(part, idx) in message.content" :key="idx">
              <CopilotChatAttachmentRenderer
                v-if="part && typeof part === 'object' && part.type !== 'text' && part.source"
                :type="part.type"
                :source="part.source"
                :filename="part.metadata?.filename"
              />
            </template>
          </div>

          <!-- 纯文本消息气泡 -->
          <div
            v-if="extractText(message.content)"
            class="cpk:prose cpk:dark:prose-invert cpk:bg-muted cpk:relative cpk:max-w-[85%] cpk:rounded-[18px] cpk:px-4 cpk:py-2 cpk:inline-block cpk:whitespace-pre-wrap"
          >
            {{ extractText(message.content) }}
          </div>
        </div>
      </template>
    </CopilotChat>

    <div
      v-if="isDataLoading"
      data-testid="chat-loading-overlay"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/85 backdrop-blur-[1px]"
    >
      <svg
        class="h-7 w-7 animate-spin text-slate-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-label="加载中"
      >
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  </div>
</template>
