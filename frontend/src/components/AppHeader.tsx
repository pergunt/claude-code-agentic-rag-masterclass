import { FileText, LogOut, MessageSquare } from 'lucide-react'
import { Link, useLocation } from 'react-router'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthProvider'

export function AppHeader() {
  const { session, signOut } = useAuth()
  const { pathname } = useLocation()
  const onDocuments = pathname.startsWith('/documents')

  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b px-4">
      <Link to="/" className="text-sm font-semibold">
        Agentic RAG
      </Link>
      <nav className="flex items-center gap-1">
        <Button size="sm" variant={onDocuments ? 'ghost' : 'secondary'} asChild>
          <Link to="/" aria-current={onDocuments ? undefined : 'page'}>
            <MessageSquare /> Chat
          </Link>
        </Button>
        <Button size="sm" variant={onDocuments ? 'secondary' : 'ghost'} asChild>
          <Link to="/documents" aria-current={onDocuments ? 'page' : undefined}>
            <FileText /> Documents
          </Link>
        </Button>
      </nav>
      <div className="flex-1" />
      <span className="truncate text-xs text-muted-foreground">{session?.user.email}</span>
      <Button size="sm" variant="ghost" onClick={() => void signOut()}>
        <LogOut /> Sign out
      </Button>
    </header>
  )
}
