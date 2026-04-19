<script setup lang="ts">
import { onMounted } from 'vue'
import ChatSidebar from '@/components/ChatSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ChatComposer from '@/components/ChatComposer.vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

onMounted(() => {
  void chatStore.bootstrap()
})

function submit() {
  const text = chatStore.input
  chatStore.input = ''
  void chatStore.sendMessage(text)
}
</script>

<template>
  <div class="relative min-h-screen overflow-hidden bg-surface text-ink">
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_10%_10%,rgba(20,184,166,0.14),transparent_35%),radial-gradient(circle_at_80%_20%,rgba(6,182,212,0.1),transparent_35%)]" />

    <div class="relative z-10 grid h-screen grid-cols-1 md:grid-cols-[280px_1fr]">
      <ChatSidebar class="hidden md:flex" />

      <main class="flex min-h-0 flex-col">
        <ChatPanel />
        <ChatComposer
          v-model="chatStore.input"
          :disabled="chatStore.isStreaming"
          @submit="submit"
          @stop="chatStore.stopStreaming"
        />
      </main>
    </div>
  </div>
</template>
