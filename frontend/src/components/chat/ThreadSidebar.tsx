import { Check, Pencil, SquarePen, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Thread } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = {
  threads: Thread[]
  activeId: string | undefined
  onSelect: (id: string) => void
  onNew: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

export function ThreadSidebar({
  threads,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const startEditing = (thread: Thread) => {
    setEditingId(thread.id)
    setDraft(thread.title)
  }

  const submitRename = (event: FormEvent) => {
    event.preventDefault()
    const title = draft.trim()
    if (editingId && title) onRename(editingId, title)
    setEditingId(null)
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-muted/30">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNew}>
          <SquarePen /> New chat
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <nav className="flex flex-col gap-0.5 px-2 pb-2">
          {threads.map((thread) =>
            editingId === thread.id ? (
              <form key={thread.id} onSubmit={submitRename} className="flex items-center gap-1">
                <Input
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === 'Escape' && setEditingId(null)}
                  className="h-8"
                  aria-label="Thread title"
                />
                <Button type="submit" size="icon-sm" variant="ghost" aria-label="Save title">
                  <Check />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label="Cancel rename"
                  onClick={() => setEditingId(null)}
                >
                  <X />
                </Button>
              </form>
            ) : (
              <div
                key={thread.id}
                className={cn(
                  'group flex items-center rounded-md hover:bg-muted',
                  thread.id === activeId && 'bg-muted',
                )}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm"
                  onClick={() => onSelect(thread.id)}
                  title={thread.title}
                >
                  {thread.title}
                </button>
                <div className="hidden shrink-0 group-hover:flex">
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    aria-label="Rename thread"
                    onClick={() => startEditing(thread)}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    aria-label="Delete thread"
                    onClick={() => onDelete(thread.id)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>
            ),
          )}
        </nav>
      </ScrollArea>
    </aside>
  )
}
