<script setup lang="ts">
defineProps<{
  name?: string;
  toolCallId?: string;
  parameters?: any;
  status?: string;
  result?: any;
}>();
</script>

<template>
  <details class="my-2.5 rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs font-mono shadow-xs">
    <summary class="cursor-pointer font-semibold text-slate-700 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-base">{{ status === 'complete' ? '⚡' : '⏳' }}</span>
        <span>
          工具执行: <strong class="text-blue-600">{{ name }}</strong>
        </span>
      </div>
      <span
        :class="[
          'px-2 py-0.5 rounded text-[10px] uppercase font-bold',
          status === 'complete' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
        ]"
      >
        {{ status }}
      </span>
    </summary>
    <div class="mt-2.5 space-y-1.5 text-slate-600 bg-white p-2.5 rounded-lg border border-slate-100 overflow-x-auto">
      <p v-if="parameters !== undefined" class="whitespace-pre-wrap text-slate-600">
        <span class="font-semibold text-slate-700">入参:</span> {{ typeof parameters === 'string' ? parameters : JSON.stringify(parameters) }}
      </p>
      <p v-if="result !== undefined" class="whitespace-pre-wrap text-slate-600">
        <span class="font-semibold text-slate-700">结果:</span> {{ typeof result === 'string' ? result : JSON.stringify(result) }}
      </p>
    </div>
  </details>
</template>
