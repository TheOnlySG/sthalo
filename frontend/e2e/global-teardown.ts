import { existsSync, readFileSync, unlinkSync } from 'node:fs'
import { request } from '@playwright/test'
import { STATE_FILE, e2eEnv } from './env'

interface E2EState {
  users: Array<{ id: string; email: string }>
}

export default async function teardown() {
  if (!existsSync(STATE_FILE)) {
    return
  }
  const state = JSON.parse(readFileSync(STATE_FILE, 'utf8')) as E2EState
  const env = e2eEnv()
  const api = await request.newContext()
  try {
    for (const user of state.users) {
      const response = await api.delete(`${env.supabaseUrl}/auth/v1/admin/users/${user.id}`, {
        headers: {
          apikey: env.supabaseServiceKey,
          Authorization: `Bearer ${env.supabaseServiceKey}`,
        },
      })
      if (!response.ok() && response.status() !== 404) {
        console.warn(`Could not delete E2E user ${user.email}: ${response.status()}`)
      }
    }
  } finally {
    await api.dispose()
    unlinkSync(STATE_FILE)
  }
}
