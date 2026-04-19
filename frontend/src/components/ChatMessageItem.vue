<script setup lang="ts">
import type { ChatMessage } from '@/types/chat'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

const props = defineProps<{
  message: ChatMessage
}>()

const emit = defineEmits<{
  retry: [messageId: string]
}>()
</script>

<template>
  <div
    class="animate-rise px-4 py-3"
    :class="props.message.role === 'user' ? 'bg-white/[0.02]' : ''"
  >
    <div class="mx-auto max-w-3xl">
      <div class="mb-2 text-xs uppercase tracking-wider text-slate-400">
        {{ props.message.role === 'user' ? 'You' : 'Assistant' }}
      </div>
      <div class="rounded-2xl border border-white/10 bg-card px-4 py-3 shadow-glow">
        <MarkdownRenderer :content="props.message.content || (props.message.isStreaming ? '...' : '')" />
      </div>
      <div
        v-if="props.message.role === 'assistant' && props.message.canRetry && !props.message.isStreaming"
        class="mt-2 flex justify-end"
      >
        <button
          class="rounded-md border border-white/20 px-2 py-1 text-xs text-slate-300 transition hover:bg-white/10"
          @click="emit('retry', props.message.id)"
        >
          重试
        </button>
      </div>
    </div>
  </div>
</template>
