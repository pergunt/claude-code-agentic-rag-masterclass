import { useEffect, useState } from 'react'

import { DocumentList } from '@/components/documents/DocumentList'
import { UploadDropzone } from '@/components/documents/UploadDropzone'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useAuth } from '@/context/AuthProvider'
import { useDocuments } from '@/hooks/useDocuments'
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES, api } from '@/lib/api'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function DocumentsPage() {
  const { session } = useAuth()
  const userId = session?.user.id ?? ''
  const { documents, loadError, upsert, remove } = useDocuments(userId)
  const [uploading, setUploading] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  // A near-miss drop outside the dropzone would otherwise navigate the tab to the file.
  useEffect(() => {
    const prevent = (event: Event) => event.preventDefault()
    window.addEventListener('dragover', prevent)
    window.addEventListener('drop', prevent)
    return () => {
      window.removeEventListener('dragover', prevent)
      window.removeEventListener('drop', prevent)
    }
  }, [])

  const handleFiles = async (files: File[]) => {
    const problems: string[] = []
    const accepted: File[] = []
    for (const file of files) {
      const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      if (!ACCEPTED_EXTENSIONS.includes(extension)) {
        problems.push(`${file.name}: unsupported file type`)
      } else if (file.size > MAX_UPLOAD_BYTES) {
        problems.push(`${file.name}: larger than ${MAX_UPLOAD_BYTES / (1024 * 1024)} MiB`)
      } else {
        accepted.push(file)
      }
    }
    setErrors(problems)

    for (const file of accepted) {
      setUploading(file.name)
      try {
        upsert(await api.uploadDocument(file))
      } catch (e) {
        problems.push(`${file.name}: ${errorMessage(e)}`)
        setErrors([...problems])
      }
    }
    setUploading(null)
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteDocument(id)
      remove(id)
    } catch (e) {
      setErrors([`Delete failed: ${errorMessage(e)}`])
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4 p-6">
      <header className="flex items-center gap-3">
        <h1 className="flex-1 text-lg font-semibold">Documents</h1>
      </header>
      <UploadDropzone onFiles={(files) => void handleFiles(files)} disabled={uploading !== null} />
      {uploading && <p className="text-sm text-muted-foreground">Uploading {uploading}…</p>}
      {errors.length > 0 && (
        <ul className="text-sm text-destructive">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
      {loadError && <p className="text-sm text-destructive">Could not load documents: {loadError}</p>}
      <ScrollArea className="min-h-0 flex-1">
        <DocumentList documents={documents} onDelete={(id) => void handleDelete(id)} />
      </ScrollArea>
    </div>
  )
}
