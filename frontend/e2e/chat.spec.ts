import { API, allowConsoleErrors, apiCall, expect, test } from './fixtures'
import type { Page } from '@playwright/test'

const SHORT = 'Reply with the single word: ok'

async function send(page: Page, text: string) {
  await page.getByLabel('Message').fill(text)
  await page.getByLabel('Message').press('Enter')
}

async function waitIdle(page: Page) {
  await expect(page.getByLabel('Stop')).toBeHidden({ timeout: 80_000 })
}

test.describe('chat', () => {
  test('UI-01 app sidebar, active nav, no page scroll, composer @smoke', async ({ page, asA, fx }) => {
    await page.goto('/login')
    await expect(page.locator('aside')).toHaveCount(0)

    const thread = (await (await apiCall(fx.a, '/api/threads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })).json()) as { id: string }

    const checkSidebar = async (path: string, active: 'Chat' | 'Documents') => {
      await asA.goto(path)
      const header = asA.locator('aside').first()
      await expect(header).toBeVisible()
      await expect(header.getByRole('link', { name: 'Chat' })).toBeVisible()
      await expect(header.getByRole('link', { name: 'Documents' })).toBeVisible()
      await expect(header.getByRole('button', { name: 'Account menu' })).toContainText(fx.a.email)
      const other = active === 'Chat' ? 'Documents' : 'Chat'
      await expect(header.getByRole('link', { name: active })).toHaveAttribute('aria-current', 'page')
      await expect(header.getByRole('link', { name: other })).not.toHaveAttribute('aria-current', 'page')
    }
    const noScroll = async () =>
      expect(await asA.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true)

    await checkSidebar('/', 'Chat')
    await noScroll()
    await expect(asA.getByLabel('Message')).toBeVisible()
    await checkSidebar(`/t/${thread.id}`, 'Chat')
    await checkSidebar('/documents', 'Documents')
    await expect(asA.getByText('velmora-station.md')).toBeVisible()
    await noScroll()
  })

  test('THR-05 thread created from first message; rename persists; delete removes @llm', async ({ asA }) => {
    await asA.goto('/')
    await send(asA, SHORT)
    await expect(asA).toHaveURL(/\/t\/[0-9a-f-]{36}$/)
    await waitIdle(asA)
    const row = asA.locator('aside div.group', { hasText: SHORT })
    await expect(row).toHaveCount(1)
    expect(SHORT.length).toBeLessThanOrEqual(60)

    await row.hover()
    await row.getByLabel('Rename thread').click()
    await asA.getByLabel('Thread title').fill('Renamed by e2e')
    await asA.getByLabel('Save title').click()
    await expect(asA.locator('aside').getByText('Renamed by e2e')).toBeVisible()
    await asA.reload()
    await expect(asA.locator('aside').getByText('Renamed by e2e')).toBeVisible()

    const renamed = asA.locator('aside div.group', { hasText: 'Renamed by e2e' })
    await renamed.hover()
    await renamed.getByLabel('Delete thread').click()
    await expect(asA.locator('aside').getByText('Renamed by e2e')).toHaveCount(0)
  })

  test('CHAT-06 streaming progressive, Stop keeps partial, reload keeps it, follow-up works @llm', async ({ asA }) => {
    await asA.goto('/')
    await send(asA, 'Write a very long, detailed essay of at least 4000 words, with many numbered sections about the history of the bicycle.')
    await expect(asA.getByLabel('Stop')).toBeVisible({ timeout: 30_000 })
    const bubble = asA.locator('.markdown').last()
    await expect(bubble).not.toHaveText('', { timeout: 30_000 })
    const len1 = (await bubble.innerText()).length
    // Text must keep growing across samples (progressive streaming), and Stop must still be there.
    await expect.poll(async () => (await bubble.innerText()).length, { timeout: 30_000 }).toBeGreaterThan(len1)
    await expect(asA.getByLabel('Stop')).toBeVisible()
    await asA.getByLabel('Stop').click()
    await expect(asA.getByLabel('Send')).toBeVisible()
    const partial = (await bubble.innerText()).trim()
    expect(partial.length).toBeGreaterThan(0)

    await expect(async () => {
      await asA.reload()
      await expect(asA.locator('.markdown').last()).not.toHaveText('', { timeout: 3000 })
    }).toPass({ timeout: 30_000 })

    await send(asA, SHORT)
    await expect(asA.locator('.markdown')).toHaveCount(2, { timeout: 60_000 })
    await waitIdle(asA)
    await expect(asA.locator('.markdown').last()).not.toHaveText('')
  })

  test('CHAT-07 unreachable backend shows "Can\'t reach the server"', async ({ asA }) => {
    allowConsoleErrors()
    await asA.goto('/')
    await expect(asA.getByLabel('Message')).toBeVisible()
    await asA.route(`${API}/**`, (r) => r.abort())
    await send(asA, 'hello')
    await expect(asA.getByText(/Can't reach the server/)).toBeVisible()
  })

  test('CHAT-08 composer: Send disabled when empty, Shift+Enter newline, Enter sends @smoke', async ({ asA }) => {
    const posts: string[] = []
    await asA.route('**/api/threads/*/messages', (r) => {
      if (r.request().method() !== 'POST') return r.fallback()
      posts.push(r.request().url())
      return r.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: { 'access-control-allow-origin': '*' },
        body: 'data: {"type":"delta","delta":"Hi"}\n\ndata: {"type":"done","text":"Hi","sources":[]}\n\n',
      })
    })
    await asA.goto('/')
    const box = asA.getByLabel('Message')
    await expect(asA.getByLabel('Send')).toBeDisabled()
    await box.click()
    await asA.keyboard.type('line1')
    await expect(asA.getByLabel('Send')).toBeEnabled()
    await asA.keyboard.press('Shift+Enter')
    await asA.keyboard.type('line2')
    expect(await box.inputValue()).toContain('\n')
    await asA.waitForTimeout(500)
    expect(posts).toHaveLength(0)

    await asA.keyboard.press('Enter')
    await expect.poll(() => posts.length).toBe(1)
    await expect(asA.locator('.markdown').last()).toHaveText('Hi')
  })
})
