<script setup lang="ts">
import { nextTick, onUpdated, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatMessageItem from '@/components/ChatMessageItem.vue'

const chatStore = useChatStore()
const listRef = ref<HTMLDivElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (!listRef.value) return
    listRef.value.scrollTop = listRef.value.scrollHeight
  })
}

onUpdated(scrollToBottom)
</script>

<template>
  <section class="flex h-full min-h-0 flex-col">
    <header class="border-b border-white/10 px-5 py-3 text-sm text-slate-300">
      <div class="flex items-center justify-between">
        <h1 class="font-semibold text-slate-100">Qlunee Coding Agent</h1>
        <div class="text-xs text-slate-400">mode: {{ chatStore.streamMode }}</div>
      </div>
    </header>

    <div ref="listRef" class="scrollbar-thin flex-1 overflow-y-auto">
      <ChatMessageItem
        v-for="message in chatStore.activeMessages"
        :key="message.id"
        :message="message"
        @retry="chatStore.retryAssistant"
      />
    </div>
  </section>
</template>
