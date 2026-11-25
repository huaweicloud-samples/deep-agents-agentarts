<script setup lang="ts">
import { computed } from "vue";
import { MenuIcon, PlusIcon } from "~/components/common";
import type { Thread } from "~/types";

const props = defineProps<{
  activeThread?: Thread;
  isSidebarOpen: boolean;
}>();

defineEmits<{
  (e: "toggleSidebar"): void;
  (e: "newThread"): void;
}>();

const title = computed(() => props.activeThread?.name || props.activeThread?.title || "新对话");
</script>

<template>
  <header class="h-14 border-b border-slate-100 flex items-center justify-between px-4 shrink-0 bg-white z-10 select-none">
    <div class="flex items-center gap-3">
      <!-- 展开/收起侧边栏 -->
      <button
        type="button"
        @click="$emit('toggleSidebar')"
        :title="isSidebarOpen ? '收起侧边栏' : '展开侧边栏'"
        class="p-2 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
      >
        <div class="w-5 h-5">
          <MenuIcon />
        </div>
      </button>

      <!-- 当前线程标题与徽章 -->
      <div class="flex items-center gap-2">
        <span class="font-semibold text-slate-800 text-sm md:text-base truncate max-w-xs md:max-w-md">
          {{ title }}
        </span>
        <span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
          Deep Agent
        </span>
        <span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          多模态支持
        </span>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        @click="$emit('newThread')"
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors cursor-pointer"
      >
        <div class="w-3.5 h-3.5">
          <PlusIcon />
        </div>
        <span>新对话</span>
      </button>
    </div>
  </header>
</template>
