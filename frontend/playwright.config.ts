import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const reportDir = path.resolve(here, process.env.VALIDATION_REPORT_DIR ?? '../validation-report/dev')

export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.ts',
  workers: 1,
  retries: 1,
  timeout: 90_000,
  outputDir: path.join(reportDir, 'playwright-artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(reportDir, 'playwright.json') }]],
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
