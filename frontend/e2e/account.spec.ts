import { expect, signIn, test } from './fixtures'

// Sign-out revokes the user's sessions server-side, so that step uses val-c (the sign-in/out account),
// never val-a or val-admin whose tokens/sessions other tests hold.
const SPARE_USER = 'rag-test-val-c@example.com'

test.describe('account', () => {
  test('UI-02 account menu: initials button bottom-left, email, Settings admin-only, sign out @smoke', async ({
    page,
    asA,
    asAdmin,
    fx,
  }) => {
    const button = (p: typeof asA) => p.getByRole('button', { name: 'Account menu' })

    for (const path of ['/', '/documents']) {
      await asA.goto(path)
      const btn = button(asA)
      await expect(btn).toBeVisible()
      await expect(btn).toContainText(fx.a.email)
      const side = await asA.locator('aside').first().boundingBox()
      const box = await btn.boundingBox()
      const viewport = asA.viewportSize()!
      expect(side).not.toBeNull()
      expect(box).not.toBeNull()
      expect(box!.x).toBeLessThan(viewport.width / 3)
      expect(box!.y + box!.height).toBeGreaterThan(viewport.height * 0.8)
    }

    // val-a is not an admin: email shown, no Settings item.
    await asA.goto('/')
    await button(asA).click()
    await expect(asA.getByRole('menu').getByText(fx.a.email)).toBeVisible()
    await expect(asA.getByRole('menuitem', { name: 'Sign out' })).toBeVisible()
    await expect(asA.getByRole('menuitem', { name: 'Settings' })).toHaveCount(0)

    // val-admin: Settings present and opens a dialog titled "Settings".
    await asAdmin.goto('/')
    await button(asAdmin).click()
    await expect(asAdmin.getByRole('menu').getByText(fx.admin.email)).toBeVisible()
    await asAdmin.getByRole('menuitem', { name: 'Settings' }).click()
    await expect(asAdmin.getByRole('dialog').getByText('Settings', { exact: true }).first()).toBeVisible()

    // Sign out (val-c): back to /login.
    await page.goto('/login')
    // Wait for the chat page's first threads load: a sign-out revokes the token server-side, so a
    // request still pending at that moment would 401 (and trip the console-error guard).
    const threadsLoaded = page.waitForResponse((r) => r.url().endsWith('/api/threads') && r.ok())
    await signIn(page, SPARE_USER)
    await expect(page).toHaveURL(/localhost:5173\/$/)
    await threadsLoaded
    await button(page).click()
    await page.getByRole('menuitem', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)
  })
})
