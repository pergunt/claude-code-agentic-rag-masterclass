import { allowConsoleErrors, expect, signIn, test } from './fixtures'

// Sign-in/sign-out flows use the suite's own sign-in account (created by validation_fixtures setup):
// a sign-out revokes the user's sessions server-side, which would break the saved val-a/val-b sessions.
const SPARE_USER = 'rag-test-val-c@example.com'

test.describe('auth', () => {
  test('AUTH-03 sign-in UI: valid creds reach / with email, wrong password shows error @smoke', async ({ page }) => {
    allowConsoleErrors() // the rejected password request logs a failed-resource error
    await page.goto('/login')
    await signIn(page, SPARE_USER, 'WrongPass999!')
    await expect(page.getByText(/invalid login credentials/i)).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)

    await signIn(page, SPARE_USER)
    await expect(page).toHaveURL(/localhost:5173\/$/)
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(SPARE_USER)
  })

  test('AUTH-04 session persists on reload; sign out returns to /login @smoke', async ({ page }) => {
    await page.goto('/login')
    await signIn(page, SPARE_USER)
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(SPARE_USER)
    await page.reload()
    await expect(page).toHaveURL(/localhost:5173\/$/)
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(SPARE_USER)

    await page.getByRole('button', { name: 'Account menu' }).click()
    await page.getByRole('menuitem', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('AUTH-05 deep link /documents survives sign-in', async ({ page }) => {
    await page.goto('/documents')
    await expect(page).toHaveURL(/\/login$/)
    await signIn(page, SPARE_USER)
    await expect(page).toHaveURL(/\/documents$/)
  })

  test('AUTH-06 backend 401 clears the session and goes to /login', async ({ page }) => {
    allowConsoleErrors()
    // The app signs the session out server-side (its own session id), so use a spare user's own
    // session rather than the storage state shared with the other specs.
    await page.goto('/login')
    await signIn(page, SPARE_USER)
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(SPARE_USER)
    await page.route('**/api/threads', (r) =>
      r.fulfill({
        status: 401,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({ detail: 'Invalid token' }),
      }),
    )
    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('AUTH-07 sign-up with an existing email shows "already registered"', async ({ page, fx }) => {
    allowConsoleErrors()
    await page.goto('/login')
    await page.getByRole('button', { name: "Don't have an account? Sign up" }).click()
    await page.getByPlaceholder('Email').fill(fx.a.email)
    await page.getByPlaceholder('Password').fill('TestPass123!')
    await page.getByRole('button', { name: 'Sign up', exact: true }).click()
    await expect(page.getByText(/already registered/i)).toBeVisible()
  })
})
