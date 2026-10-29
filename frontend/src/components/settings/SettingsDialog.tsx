import { Info } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  ApiError,
  api,
  type AdminSettings,
  type AdminSettingsInput,
  type SettingsTestResult,
} from '@/lib/api'

type TextKey = 'llm_model' | 'llm_base_url' | 'embedding_model' | 'embedding_base_url'
type KeyKey = 'llm_api_key' | 'embedding_api_key'

type Form = {
  text: Record<TextKey, string>
  // Fields the admin touched (typed in) or reset; only these go in the PUT/test body.
  touched: Partial<Record<TextKey, boolean>>
  reset: Partial<Record<TextKey | KeyKey, boolean>>
  keys: Record<KeyKey, string>
}

const TEXT_LABELS: Record<TextKey, string> = {
  llm_model: 'LLM model name',
  llm_base_url: 'LLM base URL',
  embedding_model: 'Embedding model name',
  embedding_base_url: 'Embedding base URL',
}

const KEY_LABELS: Record<KeyKey, string> = {
  llm_api_key: 'LLM API key',
  embedding_api_key: 'Embedding API key',
}

function formFrom(data: AdminSettings): Form {
  return {
    text: {
      llm_model: data.llm_model.value,
      llm_base_url: data.llm_base_url.value,
      embedding_model: data.embedding_model.value,
      embedding_base_url: data.embedding_base_url.value,
    },
    touched: {},
    reset: {},
    keys: { llm_api_key: '', embedding_api_key: '' },
  }
}

function buildBody(form: Form): AdminSettingsInput {
  const body: AdminSettingsInput = {}
  for (const k of Object.keys(TEXT_LABELS) as TextKey[]) {
    if (form.reset[k]) body[k] = null
    else if (form.touched[k]) body[k] = form.text[k].trim()
  }
  for (const k of Object.keys(KEY_LABELS) as KeyKey[]) {
    if (form.reset[k]) body[k] = null
    else if (form.keys[k]) body[k] = form.keys[k]
  }
  return body
}

function SourceBadge({ source }: { source: 'app' | 'env' }) {
  return (
    <Badge variant={source === 'app' ? 'default' : 'secondary'}>
      {source === 'app' ? 'App' : 'Default'}
    </Badge>
  )
}

function keyPlaceholder(f: AdminSettings['llm_api_key']): string {
  if (!f.configured) return 'Not set'
  const src = f.source === 'app' ? 'App setting' : 'Environment default'
  return `•••• ${f.last4 ?? ''} · ${src}`
}

// Mounting the body only while open resets all form state on every open.
export function SettingsDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return props.open ? <SettingsDialogBody {...props} /> : null
}

function SettingsDialogBody({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [data, setData] = useState<AdminSettings | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<SettingsTestResult | null>(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)

  const load = useCallback(async () => {
    try {
      const d = await api.getAdminSettings()
      setData(d)
      setForm(formFrom(d))
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load settings')
    }
  }, [])

  // Only fetch when the dialog opens, so non-admins (who never open it) never hit /api/admin/*.
  useEffect(() => {
    if (!open) return
    api.getAdminSettings().then(
      (d) => {
        setData(d)
        setForm(formFrom(d))
      },
      (e: unknown) => setLoadError(e instanceof Error ? e.message : 'Failed to load settings'),
    )
  }, [open])

  const body = form ? buildBody(form) : {}
  const dirty = Object.keys(body).length > 0

  function requestClose(next: boolean) {
    if (next) return onOpenChange(true)
    if (dirty && !confirmDiscard) return setConfirmDiscard(true)
    onOpenChange(false)
  }

  function edit(fn: (f: Form) => Form) {
    setForm((f) => (f ? fn(f) : f))
    setTestResult(null)
    setConfirmDiscard(false)
  }

  function setText(k: TextKey, v: string) {
    edit((f) => ({
      ...f,
      text: { ...f.text, [k]: v },
      touched: { ...f.touched, [k]: true },
      reset: { ...f.reset, [k]: false },
    }))
  }

  function resetText(k: TextKey) {
    if (!data) return
    edit((f) => ({
      ...f,
      text: { ...f.text, [k]: data[k].default },
      touched: { ...f.touched, [k]: false },
      reset: { ...f.reset, [k]: true },
    }))
  }

  function setKey(k: KeyKey, v: string) {
    edit((f) => ({ ...f, keys: { ...f.keys, [k]: v }, reset: { ...f.reset, [k]: false } }))
  }

  function clearKey(k: KeyKey) {
    edit((f) => ({ ...f, keys: { ...f.keys, [k]: '' }, reset: { ...f.reset, [k]: true } }))
  }

  async function save() {
    setSaving(true)
    setFormError(null)
    setFieldErrors({})
    try {
      await api.updateAdminSettings(body)
      onOpenChange(false) // saved: close (the body remounts with fresh values on the next open)
    } catch (e) {
      if (e instanceof ApiError) {
        setFieldErrors(e.fieldErrors)
        if (Object.keys(e.fieldErrors).length === 0) setFormError(e.message)
      } else {
        setFormError('Failed to save settings')
      }
    } finally {
      setSaving(false)
    }
  }

  async function runTest() {
    setTesting(true)
    setFormError(null)
    setTestResult(null)
    try {
      setTestResult(await api.testAdminSettings(body))
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Test failed')
    } finally {
      setTesting(false)
    }
  }

  function textField(k: TextKey) {
    if (!data || !form) return null
    const id = `settings-${k}`
    const f = data[k]
    const showSource = form.reset[k] ? 'env' : f.source
    const locked = data.embedding_locked && (k === 'embedding_model' || k === 'embedding_base_url')
    const canReset = (f.source === 'app' || form.touched[k]) && !form.reset[k] && !locked
    return (
      <div key={k} className="space-y-1.5" data-testid={`field-${k}`}>
        <div className="flex items-center gap-2">
          <Label htmlFor={id}>{TEXT_LABELS[k]}</Label>
          <SourceBadge source={showSource} />
          {canReset && (
            <Button
              type="button"
              variant="link"
              size="sm"
              className="ml-auto h-auto p-0 text-xs"
              onClick={() => resetText(k)}
            >
              Reset to default
            </Button>
          )}
        </div>
        <Input
          id={id}
          type="text"
          value={form.text[k]}
          onChange={(e) => setText(k, e.target.value)}
          disabled={locked}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={fieldErrors[k] ? true : undefined}
        />
        {fieldErrors[k] && <p className="text-xs text-destructive">{fieldErrors[k]}</p>}
      </div>
    )
  }

  function keyField(k: KeyKey) {
    if (!data || !form) return null
    const id = `settings-${k}`
    const f = data[k]
    const showSource = form.reset[k] ? 'env' : f.source
    const canClear = f.source === 'app' && !form.reset[k]
    return (
      <div key={k} className="space-y-1.5" data-testid={`field-${k}`}>
        <div className="flex items-center gap-2">
          <Label htmlFor={id}>{KEY_LABELS[k]}</Label>
          <SourceBadge source={showSource} />
          {canClear && (
            <Button
              type="button"
              variant="link"
              size="sm"
              className="ml-auto h-auto p-0 text-xs"
              onClick={() => clearKey(k)}
            >
              Clear
            </Button>
          )}
        </div>
        <Input
          id={id}
          type="password"
          value={form.keys[k]}
          onChange={(e) => setKey(k, e.target.value)}
          placeholder={form.reset[k] ? 'Will revert to the environment default on Save' : keyPlaceholder(f)}
          autoComplete="new-password"
          aria-invalid={fieldErrors[k] ? true : undefined}
        />
        {fieldErrors[k] && <p className="text-xs text-destructive">{fieldErrors[k]}</p>}
      </div>
    )
  }

  function testRow(testId: string, label: string, r: { ok: boolean; error?: string }, extra?: string) {
    return (
      <p
        data-testid={testId}
        className={r.ok ? 'text-sm text-green-600' : 'text-sm text-destructive'}
      >
        {r.ok ? '✓' : '✗'} {label}: {r.ok ? `OK${extra ?? ''}` : (r.error ?? 'Failed')}
      </p>
    )
  }

  const testFailed = testResult !== null && (!testResult.chat.ok || !testResult.embeddings.ok)

  return (
    <Dialog open={open} onOpenChange={requestClose}>
      <DialogContent className="flex max-h-[90vh] flex-col gap-4 sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            App-wide model configuration. Values override the environment defaults.
          </DialogDescription>
        </DialogHeader>

        <div className="-mx-1 min-h-0 flex-1 space-y-6 overflow-y-auto px-1">
          {loadError && (
            <div className="space-y-2">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button variant="outline" size="sm" onClick={() => {
                  setLoadError(null)
                  void load()
                }}>
                Retry
              </Button>
            </div>
          )}
          {!data && !loadError && <p className="text-sm text-muted-foreground">Loading…</p>}
          {data && form && (
            <>
              <section className="space-y-3">
                <h3 className="text-sm font-semibold">LLM configuration</h3>
                {textField('llm_model')}
                {textField('llm_base_url')}
                {keyField('llm_api_key')}
              </section>

              <section className="space-y-3">
                <h3 className="text-sm font-semibold">Embedding configuration</h3>
                {textField('embedding_model')}
                {textField('embedding_base_url')}
                {data.embedding_locked && (
                  <div
                    data-testid="embedding-lock-hint"
                    className="flex gap-2 rounded-md border bg-muted/50 p-3 text-xs text-muted-foreground"
                  >
                    <Info className="mt-0.5 size-4 shrink-0" />
                    <div className="space-y-1">
                      <p className="font-medium text-foreground">
                        Model and base URL are locked: {data.chunk_count} chunks already exist.
                      </p>
                      <p>
                        Those chunks were embedded with the current model. Vectors from a different
                        model or provider can&apos;t be compared with them, so search would return
                        wrong results.
                      </p>
                      <p>
                        To change them, delete all documents first, then upload them again. The API
                        key can still be changed.
                      </p>
                    </div>
                  </div>
                )}
                {keyField('embedding_api_key')}
                <div className="space-y-1.5">
                  <Label htmlFor="settings-embedding-dimensions">Dimensions</Label>
                  <Input
                    id="settings-embedding-dimensions"
                    value={String(data.embedding_dimensions)}
                    disabled
                    readOnly
                  />
                  <p className="text-xs text-muted-foreground">Fixed by the database schema</p>
                </div>
              </section>
            </>
          )}
        </div>

        <div className="space-y-1">
          {testResult && (
            <>
              {testRow('settings-test-chat', 'Chat', testResult.chat, ` (${testResult.chat.model})`)}
              {testRow(
                'settings-test-embeddings',
                'Embeddings',
                testResult.embeddings,
                testResult.embeddings.dimensions ? ` (${testResult.embeddings.dimensions} dims)` : '',
              )}
            </>
          )}
          {testFailed && (
            <p className="text-xs text-amber-700">
              The last connection test failed. You can still save, but chat or ingestion may break.
            </p>
          )}
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          {confirmDiscard && (
            <div className="flex items-center gap-2 text-sm">
              <span>Discard changes?</span>
              <Button size="sm" variant="destructive" onClick={() => onOpenChange(false)}>
                Discard
              </Button>
              <Button size="sm" variant="outline" onClick={() => setConfirmDiscard(false)}>
                Keep editing
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => void runTest()}
            disabled={!form || testing || saving}
          >
            {testing ? 'Testing…' : 'Test connection'}
          </Button>
          <Button onClick={() => void save()} disabled={!dirty || saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="ghost" onClick={() => requestClose(false)}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
