import { FileText, MessageSquare } from 'lucide-react'
import { Link, useLocation } from 'react-router'

import { AccountMenu } from '@/components/AccountMenu'
import { Button } from '@/components/ui/button'

export function AppSidebar({ slotRef }: { slotRef: (el: HTMLDivElement | null) => void }) {
  const { pathname } = useLocation()
  const onDocuments = pathname.startsWith('/documents')

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-muted/30">
      <div className="px-3 pt-3">
        <Link to="/" className="text-sm font-semibold">
          Agentic RAG
        </Link>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        <Button variant={onDocuments ? 'ghost' : 'secondary'} className="justify-start" asChild>
          <Link to="/" aria-current={onDocuments ? undefined : 'page'}>
            <MessageSquare /> Chat
          </Link>
        </Button>
        <Button variant={onDocuments ? 'secondary' : 'ghost'} className="justify-start" asChild>
          <Link to="/documents" aria-current={onDocuments ? 'page' : undefined}>
            <FileText /> Documents
          </Link>
        </Button>
      </nav>
      {/* Pages portal their own sidebar content here (ChatPage: thread list). */}
      <div ref={slotRef} className="flex min-h-0 flex-1 flex-col" />
      <div className="border-t p-2">
        <AccountMenu />
      </div>
    </aside>
  )
}
