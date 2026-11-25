<script setup lang="ts">
import { ref } from "vue";
import { useCopilotChatConfiguration } from "@copilotkit/vue/v2";
import Sidebar from "~/components/sidebar/Sidebar.vue";
import ChatHeader from "~/components/chat/ChatHeader.vue";
import ChatContainer from "~/components/chat/ChatContainer.vue";
import ToolRenderer from "~/components/chat/ToolRenderer.vue";
import { useThreads } from "~/composables/use-threads";

const isSidebarOpen = ref(true);
const config = useCopilotChatConfiguration();

const {
  threads,
  activeThreadId,
  activeThread,
  isLoading,
  setActiveThreadId,
  createThread,
  renameThread,
  deleteThread,
} = useThreads();

function handleSelectThread(threadId: string) {
  if (threadId === activeThreadId.value) return;
  setActiveThreadId(threadId);
}

async function handleNewThread() {
  const newThread = await createThread();
  config.value?.setActiveThreadId(newThread.id, { explicit: false });
}
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden bg-white text-slate-900 font-sans antialiased">
    <!-- 工具调用可视化监听 -->
    <ToolRenderer />

    <!-- 左侧会话侧边栏 -->
    <Sidebar
      :is-open="isSidebarOpen"
      :threads="threads"
      :active-thread-id="activeThreadId"
      :is-loading="isLoading"
      @select-thread="handleSelectThread"
      @create-thread="handleNewThread"
      @rename-thread="renameThread"
      @delete-thread="deleteThread"
    />

    <!-- 右侧主聊天工作区 -->
    <div class="flex-1 flex flex-col h-full min-w-0 bg-white">
      <ChatHeader
        :active-thread="activeThread"
        :is-sidebar-open="isSidebarOpen"
        @toggle-sidebar="isSidebarOpen = !isSidebarOpen"
        @new-thread="handleNewThread"
      />

      <main class="flex-1 min-h-0 w-full flex justify-center overflow-hidden relative">
        <div class="w-full max-w-4xl h-full flex flex-col">
          <ChatContainer :active-thread="activeThread" :is-threads-loading="isLoading" />
        </div>
      </main>
    </div>
  </div>
</template>
