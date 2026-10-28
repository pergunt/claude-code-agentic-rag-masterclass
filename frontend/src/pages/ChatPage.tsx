import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import { Composer } from '@/components/chat/Composer'
import type { ChatMessage } from '@/components/chat/MessageBubble'
import { MessageList } from '@/components/chat/MessageList'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { useAuth } from '@/context/AuthProvider'
import { api, streamMessage, type ChatEvent, type Thread } from '@/lib/api'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const { session, signOut } = useAuth()

  const [threads, setThreads] = useState<Thread[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A thread created by sending the first message already has its messages in state.
  const skipLoadFor = useRef<string | null>(null)
  // Aborts the in-flight reply when the user clicks Stop.
  const abortRef = useRef<AbortController | null>(null)

  // Background refresh the user didn't ask for, so a failure is logged instead of shown.
  const refreshThreads = useCallback(async () => {
    try {
      setThreads(await api.listThreads())
    } catch (e) {
      console.warn('Could not load threads:', errorMessage(e))
    }
  }, [])

  useEffect(() => {
    void refreshThreads()
  }, [refreshThreads])

  useEffect(() => () => abortRef.current?.abort(), [])

  useEffect(() => {
    if (!threadId) {
      setMessages([])
      return
    }
    if (skipLoadFor.current === threadId) {
      skipLoadFor.current = null
      return
    }
    let cancelled = false
    api
      .listMessages(threadId)
      .then((rows) => {
        if (!cancelled) setMessages(rows)
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e))
      })
    return () => {
      cancelled = true
    }
  }, [threadId])

  const updateAssistant = (id: string, update: (message: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? update(m) : m)))
  }

  const handleSend = async (content: string) => {
    setError(null)
    setStreaming(true)
    const assistantId = `assistant-${Date.now()}`
    const controller = new AbortController()
    abortRef.current = controller
    try {
      let id = threadId
      if (!id) {
        const thread = await api.createThread()
        id = thread.id
        setThreads((prev) => [thread, ...prev])
        skipLoadFor.current = id
        navigate(`/t/${id}`)
      }
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: 'user', content },
        { id: assistantId, role: 'assistant', content: '' },
      ])
      await streamMessage(id, content, (event: ChatEvent) => {
        switch (event.type) {
          case 'delta':
            setSearching(false)
            updateAssistant(assistantId, (m) => ({ ...m, content: m.content + event.delta }))
            break
          case 'tool':
            setSearching(event.status === 'searching')
            break
          case 'done':
            updateAssistant(assistantId, (m) => ({ ...m, content: event.text }))
            break
          case 'error':
            updateAssistant(assistantId, (m) => ({ ...m, content: event.message, error: true }))
            break
        }
      }, controller.signal)
      void refreshThreads()
    } catch (e) {
      // Stopped by the user: keep the partial reply; the backend saves it too.
      if (isAbort(e)) void refreshThreads()
      else setError(errorMessage(e))
      setMessages((prev) => prev.filter((m) => m.id !== assistantId || m.content))
    } finally {
      abortRef.current = null
      setStreaming(false)
      setSearching(false)
    }
  }

  const handleStop = () => abortRef.current?.abort()

  const handleRename = async (id: string, title: string) => {
    try {
      const updated = await api.renameThread(id, title)
      setThreads((prev) => prev.map((t) => (t.id === id ? updated : t)))
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteThread(id)
      setThreads((prev) => prev.filter((t) => t.id !== id))
      if (id === threadId) navigate('/')
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div className="flex h-svh">
      <ThreadSidebar
        threads={threads}
        activeId={threadId}
        email={session?.user.email}
        onSelect={(id) => navigate(`/t/${id}`)}
        onNew={() => navigate('/')}
        onRename={handleRename}
        onDelete={handleDelete}
        onSignOut={signOut}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        <MessageList messages={messages} streaming={streaming} searching={searching} />
        {error && (
          <p className="mx-auto w-full max-w-3xl px-4 text-sm text-destructive">{error}</p>
        )}
        <Composer streaming={streaming} onSend={handleSend} onStop={handleStop} />
      </main>
    </div>
  )
}
