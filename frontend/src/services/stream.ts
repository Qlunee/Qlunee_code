import type { StreamCallbacks, StreamMode, StreamRequest } from '@/types/chat'
import { chatCompletion } from '@/services/api'

interface StreamOptions {
  signal?: AbortSignal
}

async function emitChunkedText(
  text: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
  chunkSize = 18,
) {
  for (let i = 0; i < text.length; i += chunkSize) {
    if (signal?.aborted) {
      throw new DOMException('aborted', 'AbortError')
    }
    callbacks.onDelta(text.slice(i, i + chunkSize))
    await new Promise((resolve) => setTimeout(resolve, 12))
  }
}

async function streamViaHttpChatProtocol(
  request: StreamRequest,
  callbacks: StreamCallbacks,
  options?: StreamOptions,
) {
  const response = await chatCompletion(
    {
      conversationId: request.conversationId,
      message: request.message,
    },
    options?.signal,
  )

  await emitChunkedText(response.text, callbacks, options?.signal)
  callbacks.onDone()
}

export async function streamAssistantResponse(
  mode: StreamMode,
  request: StreamRequest,
  callbacks: StreamCallbacks,
  options?: StreamOptions,
) {
  try {
    if (mode === 'sse' || mode === 'websocket') {
      callbacks.onDelta('> 当前后端未提供 SSE/WebSocket 聊天路由，已自动切换为 HTTP 聊天协议。\n\n')
      await streamViaHttpChatProtocol(request, callbacks, options)
      return
    }

    await streamViaHttpChatProtocol(request, callbacks, options)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      callbacks.onError('generation_aborted')
      return
    }
    callbacks.onError(error instanceof Error ? error.message : String(error))
  }
}
