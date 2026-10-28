import { Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Props = {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

export function UploadDropzone({ onFiles, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handleDrag = (event: DragEvent) => {
    event.preventDefault()
    if (!disabled) setDragging(true)
  }

  const handleDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    const files = Array.from(event.dataTransfer.files)
    if (files.length) onFiles(files)
  }

  return (
    <div
      data-testid="upload-dropzone"
      onDragEnter={handleDrag}
      onDragOver={handleDrag}
      onDragLeave={(event) => {
        event.preventDefault()
        setDragging(false)
      }}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors',
        dragging && 'border-primary bg-muted/50',
        disabled && 'opacity-60',
      )}
    >
      <Upload className="size-6 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Drop .txt or .md files here, or</p>
      <Button type="button" variant="outline" disabled={disabled} onClick={() => inputRef.current?.click()}>
        Choose files
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        accept=".txt,.md,.markdown,text/plain,text/markdown"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          event.target.value = ''
          if (files.length) onFiles(files)
        }}
      />
    </div>
  )
}
