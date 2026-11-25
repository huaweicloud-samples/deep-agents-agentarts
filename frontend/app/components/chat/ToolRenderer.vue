<script setup lang="ts">
import { useDefaultRenderTool } from "@copilotkit/vue/v2";
import ToolCard from "./ToolCard.vue";

useDefaultRenderTool({
  render: ToolCard,
});
</script>

<template>
  <span class="hidden" aria-hidden="true" />
</template>
