import { supabase } from '@/lib/supabase'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Thread = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type Message = {
  id: string
  thread_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export type ChatEvent =
  | { type: 'delta'; delta: string }
  | { type: 'tool'; name: string; status: 'searching' | 'completed' }
  | { type: 'done'; text: string }
  | { type: 'error'; message: string }

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(await authHeaders()),
      ...init.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json() as Promise<T>
}

export const api = {
  me: () => requestJson<{ id: string; email: string | null }>('/api/me'),
  listThreads: () => requestJson<Thread[]>('/api/threads'),
  createThread: () => requestJson<Thread>('/api/threads', { method: 'POST', body: '{}' }),
  renameThread: (id: string, title: string) =>
    requestJson<Thread>(`/api/threads/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
  deleteThread: async (id: string) => {
    await request(`/api/threads/${id}`, { method: 'DELETE' })
  },
  listMessages: (threadId: string) => requestJson<Message[]>(`/api/threads/${threadId}/messages`),
}

/**
 * POST a message and read the SSE reply. EventSource can't send a POST body or an
 * Authorization header, so the stream is parsed by hand from fetch's ReadableStream.
 */
export async function streamMessage(
  threadId: string,
  content: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await request(`/api/threads/${threadId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
    signal,
  })
  if (!response.body) throw new Error('Response has no body')

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const data = block
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      if (data) onEvent(JSON.parse(data) as ChatEvent)
    }
  }
}
