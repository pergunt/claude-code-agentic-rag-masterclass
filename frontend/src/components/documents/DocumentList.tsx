import { Loader2, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { DocumentRow } from '@/lib/api'

type Props = {
  documents: DocumentRow[]
  onDelete: (id: string) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function StatusBadge({ status }: { status: DocumentRow['status'] }) {
  switch (status) {
    case 'pending':
      return <Badge variant="secondary">Pending</Badge>
    case 'processing':
      return (
        <Badge variant="outline">
          <Loader2 className="animate-spin" /> Processing
        </Badge>
      )
    case 'completed':
      return <Badge>Completed</Badge>
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>
  }
}

export function DocumentList({ documents, onDelete }: Props) {
  if (documents.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No documents yet. Upload a .txt or .md file.
      </p>
    )
  }

  return (
    <ul className="flex flex-col divide-y">
      {documents.map((doc) => (
        <li key={doc.id} className="flex items-start gap-3 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium" title={doc.filename}>
              {doc.filename}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatSize(doc.size_bytes)} · {new Date(doc.created_at).toLocaleString()}
            </p>
            {doc.status === 'failed' && doc.error && (
              <p className="mt-1 text-xs text-destructive">{doc.error}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {doc.status === 'completed' && (
              <span className="text-xs text-muted-foreground">{doc.chunk_count} {doc.chunk_count === 1 ? 'chunk' : 'chunks'}</span>
            )}
            <StatusBadge status={doc.status} />
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="Delete document"
              onClick={() => onDelete(doc.id)}
            >
              <Trash2 />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}
