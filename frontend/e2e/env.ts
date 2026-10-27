import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const REPO_ROOT = resolve(process.cwd(), '..')
export const BACKEND_ROOT = resolve(REPO_ROOT, 'backend')
export const STATE_FILE = resolve(process.cwd(), 'e2e/.state.json')

export function readEnvFile(path: string): Record<string, string> {
  const values: Record<string, string> = {}
  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) {
      continue
    }
    const index = trimmed.indexOf('=')
    if (index <= 0) {
      continue
    }
    values[trimmed.slice(0, index)] = trimmed.slice(index + 1)
  }
  return values
}

export function e2eEnv() {
  const backend = readEnvFile(resolve(BACKEND_ROOT, '.env'))
  const frontend = readEnvFile(resolve(process.cwd(), '.env.local'))
  return {
    apiBaseUrl: frontend.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
    supabaseUrl: backend.SUPABASE_URL,
    supabaseAnonKey: backend.SUPABASE_ANON_KEY,
    supabaseServiceKey: backend.SUPABASE_SERVICE_ROLE_KEY,
  }
}

export const DEMO_PASSWORD = 'SthaloDemo123!'
