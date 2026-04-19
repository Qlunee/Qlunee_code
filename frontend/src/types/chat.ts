export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: string
  isStreaming?: boolean
  requestText?: string
  canRetry?: boolean
  error?: boolean
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageIds: string[]
}

export type StreamMode = 'sse' | 'websocket' | 'http'

export interface StreamRequest {
  conversationId: string
  message: string
}

export interface StreamCallbacks {
  onDelta: (chunk: string) => void
  onDone: () => void
  onError: (error: string) => void
}
