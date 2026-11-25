<script setup lang="ts">
import {
  CopilotKitProvider,
  CopilotChatConfigurationProvider,
} from "@copilotkit/vue/v2";
import ChatLayout from "~/components/chat/ChatLayout.vue";

const apiPrefix = (
  import.meta.env.VITE_API_PREFIX ||
  import.meta.env.API_PREFIX ||
  "/api"
).replace(/\/$/, "");
const runtimeUrl = `${apiPrefix}/copilotkit`;
</script>

<template>
  <CopilotKitProvider
    :runtime-url="runtimeUrl"
    agent-id="sample_agent"
    :use-single-endpoint="false"
    :enable-inspector="false"
  >
    <CopilotChatConfigurationProvider agent-id="sample_agent">
      <ChatLayout />
    </CopilotChatConfigurationProvider>
  </CopilotKitProvider>
</template>
