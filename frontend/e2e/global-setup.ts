import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { chromium, type FullConfig } from '@playwright/test'

import { APP_URL, PASSWORD, authFile, backendDir, fixturesFile, reportDir } from './paths'

export default async function globalSetup(_config: FullConfig) {
  fs.mkdirSync(path.join(reportDir, '.auth'), { recursive: true })

  const out = execFileSync(
    path.join(backendDir, 'venv/bin/python'),
    ['-m', 'app.scripts.validation_fixtures', 'setup'],
    { cwd: backendDir, encoding: 'utf8', timeout: 180_000, maxBuffer: 10 * 1024 * 1024 },
  )
  // Take the last non-empty line in case something logs before the JSON.
  const line = out.trim().split('\n').filter(Boolean).at(-1) ?? '{}'
  const fx = JSON.parse(line) as { a: { email: string }; b: { email: string }; admin: { email: string } }
  fs.writeFileSync(fixturesFile, JSON.stringify(fx, null, 2))

  const browser = await chromium.launch()
  try {
    for (const key of ['a', 'b', 'admin'] as const) {
      const context = await browser.newContext()
      const page = await context.newPage()
      await page.goto(`${APP_URL}/login`)
      await page.getByPlaceholder('Email').fill(fx[key].email)
      await page.getByPlaceholder('Password').fill(PASSWORD)
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
      await page.waitForURL(`${APP_URL}/`)
      await context.storageState({ path: authFile(key) })
      await context.close()
    }
  } finally {
    await browser.close()
  }
}
