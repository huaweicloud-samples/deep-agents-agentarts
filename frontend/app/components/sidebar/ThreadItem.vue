<script setup lang="ts">
import { ref, computed, nextTick } from "vue";
import { ChatIcon, EditIcon, TrashIcon } from "~/components/common";
import type { Thread } from "~/types";

const props = defineProps<{
  thread: Thread;
  isActive: boolean;
}>();

const emit = defineEmits<{
  (e: "select", id: string): void;
  (e: "rename", id: string, newName: string): void;
  (e: "delete", id: string): void;
}>();

const isEditing = ref(false);
const editTitle = ref("");
const inputRef = ref<HTMLInputElement | null>(null);

const displayName = computed(() => props.thread.name || props.thread.title || "未命名对话");

async function handleStartRename(e: MouseEvent) {
  e.stopPropagation();
  isEditing.value = true;
  editTitle.value = displayName.value;
  await nextTick();
  inputRef.value?.focus();
  inputRef.value?.select();
}

function handleSaveRename() {
  if (!isEditing.value) return;
  const trimmed = editTitle.value.trim();
  isEditing.value = false;
  if (trimmed && trimmed !== displayName.value) {
    emit("rename", props.thread.id, trimmed);
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Enter") {
    handleSaveRename();
  } else if (e.key === "Escape") {
    isEditing.value = false;
    editTitle.value = "";
  }
}

function handleDelete(e: MouseEvent) {
  e.stopPropagation();
  if (confirm("确定要删除这个对话吗？")) {
    emit("delete", props.thread.id);
  }
}

function handleClick() {
  if (!isEditing.value) {
    emit("select", props.thread.id);
  }
}
</script>

<template>
  <div
    @click="handleClick"
    :class="[
      'group relative flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm cursor-pointer transition-all',
      isActive
        ? 'bg-[#27272a] text-white font-medium'
        : 'text-slate-300 hover:bg-[#27272a]/60 hover:text-white'
    ]"
  >
    <div class="w-4 h-4 shrink-0 text-slate-400">
      <ChatIcon />
    </div>

    <input
      v-if="isEditing"
      ref="inputRef"
      v-model="editTitle"
      @blur="handleSaveRename"
      @keydown="handleKeyDown"
      class="flex-1 bg-[#18181b] text-white text-xs px-2 py-1 rounded border border-blue-500 outline-none"
    />
    <span v-else class="flex-1 truncate text-xs md:text-sm">
      {{ displayName }}
    </span>

    <div
      v-if="!isEditing"
      :class="[
        'items-center gap-1 shrink-0',
        isActive ? 'flex' : 'hidden group-hover:flex'
      ]"
    >
      <button
        type="button"
        title="重命名"
        @click="handleStartRename"
        class="p-1 text-slate-400 hover:text-white rounded hover:bg-[#3f3f46] transition-colors cursor-pointer"
      >
        <div class="w-3.5 h-3.5">
          <EditIcon />
        </div>
      </button>
      <button
        type="button"
        title="删除对话"
        @click="handleDelete"
        class="p-1 text-slate-400 hover:text-red-400 rounded hover:bg-[#3f3f46] transition-colors cursor-pointer"
      >
        <div class="w-3.5 h-3.5">
          <TrashIcon />
        </div>
      </button>
    </div>
  </div>
</template>
