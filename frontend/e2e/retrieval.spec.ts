import { expect, test } from './fixtures'

test('RET-08 searching indicator, Sources chip with tooltip, persistence, no chip when not covered @llm', async ({ asA }) => {
  await asA.goto('/')
  await asA.evaluate(() => {
    const w = window as unknown as { __sawSearch: boolean }
    w.__sawSearch = false
    new MutationObserver(() => {
      if (document.body.innerText.includes('Searching documents for')) w.__sawSearch = true
    }).observe(document.body, { subtree: true, childList: true, characterData: true })
  })
  await asA.getByLabel('Message').fill('How long can samples wait before the cold room?')
  await asA.getByLabel('Message').press('Enter')
  await expect(asA.getByText('Sources:')).toBeVisible({ timeout: 80_000 })
  await expect(asA.getByLabel('Stop')).toBeHidden({ timeout: 80_000 })
  expect(await asA.evaluate(() => (window as unknown as { __sawSearch: boolean }).__sawSearch)).toBe(true)

  const chip = asA.getByText('velmora-station.md', { exact: true })
  await expect(chip).toBeVisible()
  await expect(chip).toHaveAttribute('title', /chunks .* · best similarity 0\.\d\d/)

  await asA.reload()
  await expect(asA.getByText('velmora-station.md', { exact: true })).toBeVisible()

  await asA.getByLabel('Message').fill('What does my document say about the parking policy?')
  await asA.getByLabel('Message').press('Enter')
  await expect(asA.locator('.markdown')).toHaveCount(2, { timeout: 80_000 })
  await expect(asA.getByLabel('Stop')).toBeHidden({ timeout: 80_000 })
  const last = asA.locator('.markdown').last().locator('xpath=..')
  await expect(last).not.toContainText('Sources:')
})
