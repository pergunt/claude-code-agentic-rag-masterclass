import { supabase } from '@/lib/supabase'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Thread = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type Source = {
  document_id: string
  filename: string
  chunk_index: number
  similarity: number
}

export type Me = { id: string; email: string | null; is_admin: boolean }

export type Message = {
  id: string
  thread_id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[] | null
  created_at: string
}

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type DocumentRow = {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  status: DocumentStatus
  error: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

// Mirror the backend limits (MAX_UPLOAD_BYTES and SUPPORTED_TYPES) so the UI can reject early.
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
export const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.markdown']

export type ChatEvent =
  | { type: 'delta'; delta: string }
  | {
      type: 'tool'
      name: string
      status: 'searching' | 'completed' | 'error'
      query?: string | null
      sources?: Source[]
    }
  | { type: 'done'; text: string; sources?: Source[] }
  | { type: 'error'; message: string }

export class ApiError extends Error {
  status: number
  // Per-field messages from a FastAPI 422 (`detail` is a list of {loc, msg}); keyed by the last loc part.
  fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

export type SettingField = { value: string; source: 'app' | 'env'; default: string }
export type SecretField = { configured: boolean; source: 'app' | 'env'; last4: string | null }

export type AdminSettings = {
  llm_base_url: SettingField
  llm_model: SettingField
  embedding_base_url: SettingField
  embedding_model: SettingField
  llm_api_key: SecretField
  embedding_api_key: SecretField
  embedding_dimensions: number
  chunk_count: number
  embedding_locked: boolean
}

// Omitted = unchanged, null = reset to the environment default.
export type AdminSettingsInput = Partial<
  Record<
    | 'llm_base_url'
    | 'llm_model'
    | 'llm_api_key'
    | 'embedding_base_url'
    | 'embedding_model'
    | 'embedding_api_key',
    string | null
  >
>

export type SettingsTestResult = {
  chat: { ok: boolean; error?: string; model: string }
  embeddings: { ok: boolean; error?: string; dimensions?: number }
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        // For FormData the browser must set the multipart Content-Type (with its boundary) itself.
        ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(await authHeaders()),
        ...init.headers,
      },
    })
  } catch (error) {
    // fetch rejects with a bare TypeError ("Failed to fetch") when the backend is unreachable.
    // An AbortError (Stop button) is a DOMException and passes through untouched.
    if (error instanceof TypeError) {
      throw new ApiError(0, "Can't reach the server. Check that the backend is running.")
    }
    throw error
  }
  if (!response.ok) {
    // The token was rejected (revoked or invalid), so drop the local session and
    // let ProtectedRoute send the user back to /login.
    if (response.status === 401) await supabase.auth.signOut({ scope: 'local' })
    const body = await response.json().catch(() => null)
    if (Array.isArray(body?.detail)) {
      const fieldErrors: Record<string, string> = {}
      const parts: string[] = []
      for (const item of body.detail as { loc?: (string | number)[]; msg?: string }[]) {
        const field = String(item.loc?.[item.loc.length - 1] ?? '')
        const msg = item.msg ?? 'Invalid value'
        if (field) fieldErrors[field] = msg
        parts.push(field ? `${field}: ${msg}` : msg)
      }
      throw new ApiError(response.status, parts.join('; ') || response.statusText, fieldErrors)
    }
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json() as Promise<T>
}

export const api = {
  me: () => requestJson<Me>('/api/me'),
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
  listDocuments: () => requestJson<DocumentRow[]>('/api/documents'),
  uploadDocument: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return requestJson<DocumentRow>('/api/documents', { method: 'POST', body })
  },
  deleteDocument: async (id: string) => {
    await request(`/api/documents/${id}`, { method: 'DELETE' })
  },
  getAdminSettings: () => requestJson<AdminSettings>('/api/admin/settings'),
  updateAdminSettings: (input: AdminSettingsInput) =>
    requestJson<AdminSettings>('/api/admin/settings', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
  testAdminSettings: (input: AdminSettingsInput) =>
    requestJson<SettingsTestResult>('/api/admin/settings/test', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
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
