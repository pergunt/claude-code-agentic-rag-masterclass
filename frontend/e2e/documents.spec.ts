import { expect, test, uploadViaApi, waitDocStatus } from './fixtures'
import type { Page } from '@playwright/test'

const uniq = (p: string) => `${p}-${Date.now()}-${Math.floor(Math.random() * 1e4)}.md`
const row = (page: Page, name: string) => page.locator('li', { hasText: name })

async function waitReady(page: Page, fx: { a: { doc_id: string } }) {
  void fx
  await expect(page.getByText('velmora-station.md')).toBeVisible()
}

test.describe('documents', () => {
  test('ING-10 file-picker upload reaches Completed without reload or polling', async ({ asA, fx }) => {
    const reqs: string[] = []
    asA.on('request', (r) => {
      if (/\/api\/documents(\?|$)/.test(r.url())) reqs.push(`${r.method()}`)
    })
    await asA.goto('/documents')
    await waitReady(asA, fx)
    const name = uniq('ing10')
    reqs.length = 0
    await asA.locator('[data-testid=upload-dropzone] input[type=file]').setInputFiles({
      name,
      mimeType: 'text/markdown',
      buffer: Buffer.from(`# Ingest ten\n\nUnique content ${name} about harbour lighthouses.\n`),
    })
    await expect(row(asA, name)).toBeVisible()
    await expect(row(asA, name).getByText('Completed')).toBeVisible({ timeout: 60_000 })
    expect(reqs.filter((m) => m === 'POST')).toHaveLength(1)
    expect(reqs.filter((m) => m === 'GET')).toHaveLength(0)
    await row(asA, name).getByLabel('Delete document').click()
    await expect(row(asA, name)).toHaveCount(0)
  })

  test('ING-11 drop uploads; dropped .pdf is rejected client-side', async ({ asA, fx }) => {
    let posts = 0
    asA.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/api/documents')) posts++
    })
    await asA.goto('/documents')
    await waitReady(asA, fx)
    const drop = async (fname: string, mime: string, content: string) => {
      const dt = await asA.evaluateHandle(
        ([n, m, c]) => {
          const d = new DataTransfer()
          d.items.add(new File([c], n, { type: m }))
          return d
        },
        [fname, mime, content],
      )
      await asA.getByTestId('upload-dropzone').dispatchEvent('drop', { dataTransfer: dt })
    }
    await drop('drop-test.md', 'text/markdown', '# Drop test\n\nContent dropped onto the zone about tidal pools.\n')
    await expect(row(asA, 'drop-test.md').getByText('Completed')).toBeVisible({ timeout: 60_000 })
    expect(posts).toBe(1)

    await drop('x.pdf', 'application/pdf', '%PDF-1.4')
    await expect(asA.getByText(/x\.pdf: unsupported file type/)).toBeVisible()
    await asA.waitForTimeout(500)
    expect(posts).toBe(1)
  })

  test('ING-12 failed document shows Failed status and error text', async ({ asA }) => {
    const now = new Date().toISOString()
    await asA.route('**/api/documents', (r) => {
      if (r.request().method() !== 'GET') return r.fallback()
      return r.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify([
          {
            id: '00000000-0000-0000-0000-000000000001',
            filename: 'broken.md',
            mime_type: 'text/markdown',
            size_bytes: 12,
            status: 'failed',
            error: 'Embedding provider exploded',
            chunk_count: 0,
            created_at: now,
            updated_at: now,
          },
        ]),
      })
    })
    await asA.goto('/documents')
    await expect(row(asA, 'broken.md').getByText('Failed')).toBeVisible()
    await expect(asA.getByText('Embedding provider exploded')).toBeVisible()
  })

  test('ING-13 rows survive reload; delete persists', async ({ asA, fx }) => {
    await asA.goto('/documents')
    await waitReady(asA, fx)
    const name = uniq('ing13')
    await asA.locator('[data-testid=upload-dropzone] input[type=file]').setInputFiles({
      name,
      mimeType: 'text/markdown',
      buffer: Buffer.from(`# Ing thirteen\n\nUnique ${name} text about desert foxes.\n`),
    })
    await expect(row(asA, name).getByText('Completed')).toBeVisible({ timeout: 60_000 })
    await asA.reload()
    await expect(row(asA, name)).toBeVisible()
    await row(asA, name).getByLabel('Delete document').click()
    await expect(row(asA, name)).toHaveCount(0)
    await asA.reload()
    await expect(asA.getByText('velmora-station.md')).toBeVisible()
    await expect(row(asA, name)).toHaveCount(0)
  })

  test("ING-14 A's upload never appears in B's list", async ({ asB, fx }) => {
    await asB.goto('/documents')
    await expect(asB.getByText('b-recipes.md')).toBeVisible()
    const name = uniq('ing14-secret')
    const doc = await uploadViaApi(fx.a, name, `# Secret\n\nA only: ${name} about glacier mapping.\n`)
    await waitDocStatus(fx.a, doc.id)
    await asB.waitForTimeout(3000)
    await expect(asB.getByText(name)).toHaveCount(0)
    await expect(asB.getByText('velmora-station.md')).toHaveCount(0)
  })
})
