import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage, ChatSession, StreamMode } from '@/types/chat'
import { streamAssistantResponse } from '@/services/stream'
import { fetchHealth, fetchTasks, readLeadInbox } from '@/services/api'

const STORAGE_KEY = 'qlunee-chat-state-v1'

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

function nowIso() {
  return new Date().toISOString()
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const messageMap = ref<Record<string, ChatMessage>>({})
  const activeSessionId = ref<string>('')
  const input = ref('')
  const isStreaming = ref(false)
  const streamMode = ref<StreamMode>((import.meta.env.VITE_STREAM_MODE as StreamMode) ?? 'http')
  const health = ref('unknown')
  const tasksPreview = ref<string>('')
  const currentAbortController = ref<AbortController | null>(null)
  const currentAssistantMessageId = ref<string>('')
  const inboxPollTimer = ref<number | null>(null)
  const inboxPolling = ref(false)

  const activeSession = computed(() => sessions.value.find((s) => s.id === activeSessionId.value))

  const activeMessages = computed(() => {
    if (!activeSession.value) return []
    return activeSession.value.messageIds
      .map((id) => messageMap.value[id])
      .filter(Boolean)
  })

  function setSessionTitleByMessage(session: ChatSession, text: string) {
    if (session.title !== '新会话') return
    const oneLine = text.replace(/\s+/g, ' ').trim()
    session.title = oneLine.slice(0, 24) || '新会话'
  }

  function createSession() {
    const id = uid('sess')
    const session: ChatSession = {
      id,
      title: '新会话',
      createdAt: nowIso(),
      updatedAt: nowIso(),
      messageIds: [],
    }
    sessions.value.unshift(session)
    activeSessionId.value = id

    const welcomeId = uid('msg')
    messageMap.value[welcomeId] = {
      id: welcomeId,
      role: 'assistant',
      content: '你好，我是 Qlunee Agent UI。你可以直接提问，我会通过后端接口流式返回内容。',
      createdAt: nowIso(),
    }
    session.messageIds.push(welcomeId)
    persistState()
  }

  function switchSession(id: string) {
    activeSessionId.value = id
    persistState()
  }

  function appendMessage(sessionId: string, message: ChatMessage) {
    const session = sessions.value.find((s) => s.id === sessionId)
    if (!session) return
    messageMap.value[message.id] = message
    session.messageIds.push(message.id)
    session.updatedAt = nowIso()
    persistState()
  }

  function persistState() {
    const data = {
      sessions: sessions.value,
      messageMap: messageMap.value,
      activeSessionId: activeSessionId.value,
      streamMode: streamMode.value,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  function restoreState() {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return

    try {
      const data = JSON.parse(raw) as {
        sessions?: ChatSession[]
        messageMap?: Record<string, ChatMessage>
        activeSessionId?: string
        streamMode?: StreamMode
      }

      sessions.value = data.sessions ?? []
      messageMap.value = data.messageMap ?? {}
      activeSessionId.value = data.activeSessionId ?? ''
      streamMode.value = data.streamMode ?? streamMode.value
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  async function bootstrap() {
    restoreState()
    if (!sessions.value.length) createSession()

    try {
      const data = await fetchHealth()
      health.value = data.ok ? 'ok' : 'error'
    } catch {
      health.value = 'offline'
    }

    try {
      const data = await fetchTasks()
      const text = JSON.stringify(data)
      tasksPreview.value = text.slice(0, 120)
    } catch {
      tasksPreview.value = '无法读取 /api/tasks'
    }

    startInboxPolling()
  }

  function formatInboxItems(items: Array<{ from: string; type: string; content: string; timestamp: number }>) {
    const lines = items.map((item) => {
      const time = new Date(item.timestamp * 1000).toLocaleTimeString()
      return `- [${time}] ${item.from} (${item.type}): ${item.content}`
    })
    return ['### 队友异步消息', '', ...lines].join('\n')
  }

  async function pollLeadInbox() {
    if (inboxPolling.value) return
    inboxPolling.value = true
    try {
      const data = await readLeadInbox()
      if (!data.count) return

      if (!activeSession.value) createSession()
      if (!activeSession.value) return

      appendMessage(activeSession.value.id, {
        id: uid('msg'),
        role: 'assistant',
        content: formatInboxItems(data.items),
        createdAt: nowIso(),
      })
    } catch {
      // Ignore polling errors to avoid interrupting user chat flow.
    } finally {
      inboxPolling.value = false
    }
  }

  function startInboxPolling() {
    if (inboxPollTimer.value !== null) return
    inboxPollTimer.value = window.setInterval(() => {
      void pollLeadInbox()
    }, 2000)
  }

  async function sendMessage(text: string) {
    const content = text.trim()
    if (!content || isStreaming.value) return
    if (!activeSession.value) createSession()
    if (!activeSession.value) return

    const session = activeSession.value
    setSessionTitleByMessage(session, content)

    const userMsg: ChatMessage = {
      id: uid('msg'),
      role: 'user',
      content,
      createdAt: nowIso(),
    }
    appendMessage(session.id, userMsg)

    const assistantMsg: ChatMessage = {
      id: uid('msg'),
      role: 'assistant',
      content: '',
      createdAt: nowIso(),
      isStreaming: true,
      requestText: content,
      canRetry: false,
    }
    appendMessage(session.id, assistantMsg)

    isStreaming.value = true
    currentAssistantMessageId.value = assistantMsg.id
    currentAbortController.value = new AbortController()

    await streamAssistantResponse(
      streamMode.value,
      {
        conversationId: session.id,
        message: content,
      },
      {
        onDelta(chunk) {
          const target = messageMap.value[assistantMsg.id]
          if (!target) return
          target.content += chunk
          persistState()
        },
        onDone() {
          const target = messageMap.value[assistantMsg.id]
          if (target) {
            target.isStreaming = false
            target.canRetry = true
          }
          isStreaming.value = false
          currentAbortController.value = null
          currentAssistantMessageId.value = ''
          persistState()
        },
        onError(error) {
          const target = messageMap.value[assistantMsg.id]
          if (target) {
            if (error === 'generation_aborted') {
              target.content += '\n\n[已停止生成]'
            } else {
              target.content += `\n\n[stream error] ${error}`
              target.error = true
            }
            target.isStreaming = false
            target.canRetry = true
          }
          isStreaming.value = false
          currentAbortController.value = null
          currentAssistantMessageId.value = ''
          persistState()
        },
      },
      { signal: currentAbortController.value.signal },
    )
  }

  function stopStreaming() {
    if (!isStreaming.value) return
    currentAbortController.value?.abort()
  }

  async function retryAssistant(messageId: string) {
    const message = messageMap.value[messageId]
    if (!message?.requestText || isStreaming.value) return
    await sendMessage(message.requestText)
  }

  return {
    sessions,
    messageMap,
    activeSessionId,
    activeSession,
    activeMessages,
    input,
    isStreaming,
    streamMode,
    health,
    tasksPreview,
    currentAssistantMessageId,
    bootstrap,
    createSession,
    switchSession,
    sendMessage,
    stopStreaming,
    retryAssistant,
    startInboxPolling,
  }
})
