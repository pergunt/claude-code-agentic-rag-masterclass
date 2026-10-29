import { allowConsoleErrors, apiCall, expect, test, type Fx } from './fixtures'

const RESET_ALL = JSON.stringify({
  llm_base_url: null,
  llm_model: null,
  llm_api_key: null,
  embedding_base_url: null,
  embedding_model: null,
  embedding_api_key: null,
})

async function resetSettings(fx: Fx) {
  await apiCall(fx.admin, '/api/admin/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: RESET_ALL,
  }).catch(() => undefined)
}

async function openSettings(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('menuitem', { name: 'Settings' }).click()
  const dialog = page.getByRole('dialog', { name: 'Settings' })
  await expect(dialog.getByLabel('LLM model name')).toBeVisible()
  return dialog
}

test.describe('settings', () => {
  test('UI-03 settings dialog: two sections, password keys, dimensions, source badges', async ({
    asA,
    asAdmin,
    fx,
  }) => {
    // Non-admin: no Settings item, and no /api/admin/* request.
    const adminCalls: string[] = []
    asA.on('request', (r) => {
      if (r.url().includes('/api/admin/')) adminCalls.push(r.url())
    })
    await asA.goto('/')
    await asA.getByRole('button', { name: 'Account menu' }).click()
    await expect(asA.getByRole('menuitem', { name: 'Settings' })).toHaveCount(0)
    expect(adminCalls).toEqual([])

    try {
      let dialog = await openSettings(asAdmin)
      await expect(dialog.getByRole('heading', { name: 'LLM configuration' })).toBeVisible()
      await expect(dialog.getByRole('heading', { name: 'Embedding configuration' })).toBeVisible()

      for (const name of ['LLM API key', 'Embedding API key']) {
        const input = dialog.getByLabel(name)
        await expect(input).toHaveAttribute('type', 'password')
        await expect(input).toHaveValue('')
        const placeholder = (await input.getAttribute('placeholder')) ?? ''
        expect(placeholder).toMatch(/^(•••• .{4} · (App setting|Environment default)|Not set)$/)
      }
      const dims = dialog.getByLabel('Dimensions')
      await expect(dims).toBeDisabled()
      await expect(dims).toHaveValue('1536')

      // Embedding model/base URL are locked while chunks exist (the suite seeds documents).
      await expect(dialog.getByLabel('Embedding model name')).toBeDisabled()
      await expect(dialog.getByLabel('Embedding base URL')).toBeDisabled()
      const hint = dialog.getByTestId('embedding-lock-hint')
      await expect(hint).toBeVisible()
      await expect(hint).toContainText('chunks already exist')
      await expect(hint).toContainText("can't be compared")
      await expect(dialog.getByLabel('Embedding API key')).toBeEnabled()

      // A rejected save keeps the dialog open with the error; then undo the edit.
      allowConsoleErrors() // the browser logs the intended 422
      const baseUrl = dialog.getByLabel('LLM base URL')
      const currentUrl = await baseUrl.inputValue()
      await baseUrl.fill('ftp://not-allowed')
      await dialog.getByRole('button', { name: 'Save', exact: true }).click()
      await expect(dialog.getByText(/must start with https/)).toBeVisible()
      await expect(dialog).toBeVisible()
      await baseUrl.fill(currentUrl)

      // Touch the LLM model without changing its value, then save: becomes an App setting.
      const model = dialog.getByLabel('LLM model name')
      const current = await model.inputValue()
      await model.press('End')
      await model.pressSequentially('x')
      await model.press('Backspace')
      await expect(model).toHaveValue(current)
      await dialog.getByRole('button', { name: 'Save', exact: true }).click()
      await expect(dialog).toBeHidden() // a successful save closes the dialog

      await asAdmin.reload()
      dialog = await openSettings(asAdmin)
      await expect(dialog.getByLabel('LLM model name')).toHaveValue(current)
      const llmRow = dialog.getByTestId('field-llm_model')
      await expect(llmRow.getByText('App', { exact: true })).toBeVisible()

      // Reset to default, save: Default badge.
      await llmRow.getByRole('button', { name: 'Reset to default' }).click()
      await dialog.getByRole('button', { name: 'Save', exact: true }).click()
      await expect(dialog).toBeHidden() // a successful save closes the dialog
      await asAdmin.reload()
      dialog = await openSettings(asAdmin)
      const row2 = dialog.getByTestId('field-llm_model')
      await expect(row2.getByText('Default', { exact: true })).toBeVisible()
    } finally {
      await resetSettings(fx)
    }
  })

  test('UI-04 test connection shows OK for chat and embeddings', async ({ asAdmin, fx }) => {
    test.setTimeout(90_000)
    try {
      const dialog = await openSettings(asAdmin)
      await dialog.getByRole('button', { name: 'Test connection' }).click()
      await expect(dialog.getByTestId('settings-test-chat')).toContainText('OK', { timeout: 60_000 })
      await expect(dialog.getByTestId('settings-test-embeddings')).toContainText('OK', {
        timeout: 60_000,
      })
    } finally {
      await resetSettings(fx)
    }
  })
})
