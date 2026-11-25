<script setup lang="ts">
import { PlusIcon } from "~/components/common";
import ThreadItem from "./ThreadItem.vue";
import type { Thread } from "~/types";

defineProps<{
  isOpen: boolean;
  threads: Thread[];
  activeThreadId: string;
  isLoading: boolean;
}>();

defineEmits<{
  (e: "selectThread", id: string): void;
  (e: "createThread"): void;
  (e: "renameThread", id: string, newName: string): void;
  (e: "deleteThread", id: string): void;
}>();
</script>

<template>
  <aside
    :class="[
      isOpen ? 'w-64 md:w-72' : 'w-0 -translate-x-full',
      'transition-all duration-200 ease-in-out shrink-0 bg-[#18181b] text-slate-200 flex flex-col h-full z-30 select-none overflow-hidden border-r border-[#27272a]'
    ]"
  >
    <div class="p-3.5 flex flex-col h-full gap-3">
      <!-- 新建对话按钮 -->
      <button
        type="button"
        @click="$emit('createThread')"
        class="flex items-center justify-between w-full px-3.5 py-2.5 text-sm font-medium rounded-xl bg-[#27272a] hover:bg-[#3f3f46] text-white border border-[#3f3f46] transition-colors shadow-xs group cursor-pointer"
      >
        <div class="flex items-center gap-2.5">
          <div class="w-4 h-4 text-slate-300 group-hover:text-white">
            <PlusIcon />
          </div>
          <span>新对话</span>
        </div>
        <kbd class="text-[10px] px-1.5 py-0.5 rounded bg-[#18181b] text-slate-400 border border-[#3f3f46]">
          New
        </kbd>
      </button>

      <!-- 对话列表区 -->
      <div class="flex-1 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
        <div class="text-[11px] font-semibold text-slate-400 px-2 py-1 uppercase tracking-wider flex items-center justify-between">
          <span>会话列表</span>
          <span
            class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-mono truncate max-w-[100px]"
            title="/api/threads"
          >
            /api/threads
          </span>
        </div>

        <div v-if="isLoading" class="p-4 text-center text-xs text-slate-400">
          正在同步对话...
        </div>
        <div v-else-if="threads.length === 0" class="p-4 text-center text-xs text-slate-400">
          暂无对话记录
        </div>
        <template v-else>
          <ThreadItem
            v-for="thread in threads"
            :key="thread.id"
            :thread="thread"
            :is-active="thread.id === activeThreadId"
            @select="$emit('selectThread', $event)"
            @rename="(id, name) => $emit('renameThread', id, name)"
            @delete="$emit('deleteThread', $event)"
          />
        </template>
      </div>

      <!-- 侧边栏底部说明 -->
      <div class="pt-2 border-t border-[#27272a] text-xs text-slate-400 flex flex-col gap-1.5 px-2">
        <div class="flex items-center gap-2 text-slate-300 font-medium">
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>FastAPI + DeepAgents (Vue 3)</span>
        </div>
        <p class="text-[11px] text-slate-500">
          UI 协议与业务 API 均收敛至 API_PREFIX 规范化解耦。
        </p>
      </div>
    </div>
  </aside>
</template>
