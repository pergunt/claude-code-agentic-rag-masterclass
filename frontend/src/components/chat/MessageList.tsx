import { LoaderCircle, Search } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { MessageBubble, type ChatMessage } from '@/components/chat/MessageBubble'
import { ScrollArea } from '@/components/ui/scroll-area'

type Props = {
  messages: ChatMessage[]
  streaming: boolean
  searching: boolean
}

export function MessageList({ messages, streaming, searching }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, searching])

  const last = messages.at(-1)
  const waitingForFirstToken = streaming && last?.role === 'assistant' && !last.content

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
        {messages.length === 0 && (
          <p className="mt-24 text-center text-muted-foreground">
            Ask a question about your documents.
          </p>
        )}
        {messages
          .filter((message) => message.content || message.role === 'user')
          .map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        {searching && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Search className="size-4 animate-pulse" /> Searching documents…
          </p>
        )}
        {waitingForFirstToken && !searching && (
          <LoaderCircle className="size-4 animate-spin text-muted-foreground" />
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
