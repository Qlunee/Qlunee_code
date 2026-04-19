import axios from 'axios'

export interface HealthResponse {
  ok: boolean
  workdir: string
  tasks: number
  inbox_files: number
}

export interface TaskItem {
  id: number
  subject: string
  description: string
  status: string
  owner: string | null
  blockedBy: number[]
}

export interface TasksResponse {
  items: TaskItem[]
  count: number
}

export interface TaskCreateRequest {
  subject: string
  description?: string
}

export interface TaskUpdateRequest {
  status?: string | null
  owner?: string | null
  blockedBy?: number[] | null
}

export interface ChatRequest {
  conversationId: string
  message: string
}

export interface ChatResponse {
  text: string
  model: string
}

export interface InboxMessage {
  type: string
  from: string
  content: string
  timestamp: number
  request_id?: string | null
  approve?: boolean | null
  feedback?: string | null
}

export interface InboxResponse {
  items: InboxMessage[]
  count: number
}

const baseURL = import.meta.env.VITE_API_BASE_URL ?? ''
const timeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 1200000)

export const api = axios.create({
  baseURL,
  timeout: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 1200000,
})

export async function fetchHealth() {
  const { data } = await api.get<HealthResponse>('/api/health')
  return data
}

export async function fetchTasks(signal?: AbortSignal) {
  const { data } = await api.get<TasksResponse>('/api/tasks', { signal })
  return data
}

export async function createTask(payload: TaskCreateRequest, signal?: AbortSignal) {
  const { data } = await api.post<TaskItem>('/api/tasks', payload, { signal })
  return data
}

export async function updateTask(taskId: number, payload: TaskUpdateRequest, signal?: AbortSignal) {
  const { data } = await api.patch<TaskItem>(`/api/tasks/${taskId}`, payload, { signal })
  return data
}

export async function chatCompletion(payload: ChatRequest, signal?: AbortSignal) {
  const { data } = await api.post<ChatResponse>('/api/chat', payload, { signal })
  return data
}

export async function readLeadInbox(signal?: AbortSignal) {
  const { data } = await api.get<InboxResponse>('/api/inbox/lead', { signal })
  return data
}
