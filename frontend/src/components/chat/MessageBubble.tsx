import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge } from '@/components/ui/badge'
import type { Source } from '@/lib/api'
import { cn } from '@/lib/utils'

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[] | null
  error?: boolean
}

// One chip per filename; the tooltip lists the cited chunks and the best similarity.
function groupSources(sources: Source[]) {
  const byFile = new Map<string, Source[]>()
  for (const s of sources) byFile.set(s.filename, [...(byFile.get(s.filename) ?? []), s])
  return [...byFile].map(([filename, items]) => {
    const chunks = [...new Set(items.map((s) => s.chunk_index))].sort((a, b) => a - b)
    const best = Math.max(...items.map((s) => s.similarity))
    return { filename, title: `chunks ${chunks.join(', ')} · best similarity ${best.toFixed(2)}` }
  })
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
          isUser && 'whitespace-pre-wrap bg-primary text-primary-foreground',
          !isUser && !message.error && 'bg-muted',
          message.error && 'bg-destructive/10 text-destructive',
        )}
      >
        {isUser ? (
          message.content
        ) : (
          <div className="markdown">
            <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
          </div>
        )}
        {!isUser && !message.error && !!message.sources?.length && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span>Sources:</span>
            {groupSources(message.sources).map((g) => (
              <Badge key={g.filename} variant="outline" title={g.title}>
                {g.filename}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
