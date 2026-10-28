import fs from 'node:fs'
import { test as base, expect, type Page } from '@playwright/test'

import { APP_URL, PASSWORD, authFile, fixturesFile } from './paths'

export type FxUser = { email: string; token: string; id: string; doc_id: string }
export type Fx = { api: string; supabase_url: string; anon_key: string; a: FxUser; b: FxUser }

export const API = 'http://localhost:8000'
export { PASSWORD, APP_URL }

/** Call from a test whose scenario legitimately produces console.error (401s, aborted requests). */
export function allowConsoleErrors() {
  base.info().annotations.push({ type: 'allow-console-error' })
}

export async function apiCall(user: FxUser, path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${user.token}`, ...(init.headers ?? {}) },
  })
}

export async function uploadViaApi(user: FxUser, filename: string, content: string) {
  const body = new FormData()
  body.append('file', new Blob([content], { type: 'text/markdown' }), filename)
  const res = await apiCall(user, '/api/documents', { method: 'POST', body })
  if (!res.ok) throw new Error(`upload failed: ${res.status}`)
  return (await res.json()) as { id: string; status: string }
}

export async function waitDocStatus(user: FxUser, id: string, status = 'completed', timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const res = await apiCall(user, `/api/documents/${id}`)
    const doc = (await res.json()) as { status: string }
    if (doc.status === status) return
    if (doc.status === 'failed') throw new Error('document failed')
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error(`document did not reach ${status}`)
}

async function cleanup(fx: Fx) {
  for (const user of [fx.a, fx.b]) {
    for (const t of (await (await apiCall(user, '/api/threads')).json()) as { id: string }[]) {
      await apiCall(user, `/api/threads/${t.id}`, { method: 'DELETE' })
    }
    for (const d of (await (await apiCall(user, '/api/documents')).json()) as { id: string }[]) {
      if (d.id !== user.doc_id) await apiCall(user, `/api/documents/${d.id}`, { method: 'DELETE' })
    }
  }
}

export async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.getByPlaceholder('Email').fill(email)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
}

type Fixtures = {
  fx: Fx
  asA: Page
  asB: Page
  consoleGuard: void
}

export const test = base.extend<Fixtures>({
  fx: async ({ baseURL }, provide) => {
    void baseURL
    await provide(JSON.parse(fs.readFileSync(fixturesFile, 'utf8')) as Fx)
  },

  consoleGuard: [
    async ({ context, fx }, provide, testInfo) => {
      const errors: string[] = []
      const watch = (p: Page) => {
        p.on('console', (m) => {
          if (m.type() === 'error') errors.push(m.text())
        })
        p.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
      }
      watch0 = watch
      context.on('page', watch)
      await provide()
      watch0 = null
      await cleanup(fx).catch(() => undefined)
      const allowed = testInfo.annotations.some((a) => a.type === 'allow-console-error')
      if (!allowed && errors.length) {
        throw new Error(`console.error during test:\n${errors.join('\n')}`)
      }
    },
    { auto: true },
  ],

  asA: async ({ browser, consoleGuard }, provide) => {
    void consoleGuard
    const ctx = await browser.newContext({ storageState: authFile('a') })
    const page = await ctx.newPage()
    watch0?.(page)
    await provide(page)
    await ctx.close()
  },
  asB: async ({ browser, consoleGuard }, provide) => {
    void consoleGuard
    const ctx = await browser.newContext({ storageState: authFile('b') })
    const page = await ctx.newPage()
    watch0?.(page)
    await provide(page)
    await ctx.close()
  },
})

// Console watcher of the running test, so pages from extra contexts are covered too.
let watch0: ((p: Page) => void) | null = null

export { expect }
