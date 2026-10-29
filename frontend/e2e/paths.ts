import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

// Same computation as playwright.config.ts (frontend/ is the parent of this dir).
export const reportDir = path.resolve(
  here,
  '..',
  process.env.VALIDATION_REPORT_DIR ?? '../validation-report/dev',
)
export const fixturesFile = path.join(reportDir, 'fixtures.json')
export const authFile = (key: 'a' | 'b' | 'admin') => path.join(reportDir, '.auth', `${key}.json`)
export const backendDir = path.resolve(here, '../../backend')
export const PASSWORD = 'TestPass123!'
export const APP_URL = 'http://localhost:5173'
