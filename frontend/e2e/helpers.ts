import { expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { STATE_FILE, DEMO_PASSWORD } from './env'

export interface DemoUser {
  id: string
  email: string
  token: string
}

export interface E2EState {
  apiBaseUrl: string
  listingId: string
  title: string
  customer: DemoUser
  owner: DemoUser
  admin: DemoUser
  vehicleId: string
}

export function readState(): E2EState {
  return JSON.parse(readFileSync(STATE_FILE, 'utf8')) as E2EState
}

export async function signIn(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(DEMO_PASSWORD)
  await page.getByLabel('Password').press('Enter')
  await expect(page).toHaveURL(/\/account\/profile$/)
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
}

export async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
}
