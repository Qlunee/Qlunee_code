<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const sessionCount = computed(() => chatStore.sessions.length)
</script>

<template>
  <aside class="flex h-full w-full flex-col border-r border-white/10 bg-gradient-to-b from-slate-950 to-slate-900">
    <div class="p-4">
      <button
        class="w-full rounded-xl border border-teal-300/20 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-200 transition hover:bg-teal-500/20"
        @click="chatStore.createSession"
      >
        + 新建会话
      </button>
    </div>

    <div class="px-4 pb-3 text-xs text-slate-400">
      会话 {{ sessionCount }} · Health: {{ chatStore.health }}
    </div>

    <nav class="scrollbar-thin flex-1 overflow-y-auto px-2 pb-4">
      <button
        v-for="session in chatStore.sessions"
        :key="session.id"
        class="mb-1 w-full rounded-lg px-3 py-2 text-left text-sm transition"
        :class="session.id === chatStore.activeSessionId ? 'bg-white/12 text-white' : 'text-slate-300 hover:bg-white/8'"
        @click="chatStore.switchSession(session.id)"
      >
        <div class="truncate font-medium">{{ session.title }}</div>
        <div class="truncate text-xs text-slate-400">{{ new Date(session.updatedAt).toLocaleString() }}</div>
      </button>
    </nav>

    <div class="border-t border-white/10 p-4 text-xs text-slate-400">
      <div class="mb-1 font-medium text-slate-200">/api/tasks</div>
      <div class="line-clamp-3">{{ chatStore.tasksPreview || '暂无数据' }}</div>
    </div>
  </aside>
</template>
