import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readState, signIn, signOut } from './helpers'

const state = readState()

async function expectNoCriticalA11y(page: Page) {
  const results = await new AxeBuilder({ page }).analyze()
  const critical = results.violations.filter((violation) => violation.impact === 'critical')
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([])
}

test.describe.configure({ mode: 'serial' })

test('customer books and confirms, owner cancels, admin audits', async ({ page, request }) => {
  await signIn(page, state.customer.email)
  await page.goto(`/parking/${state.listingId}`)
  await expect(page.getByRole('heading', { name: state.title })).toBeVisible()
  await expect(page.getByLabel('Vehicle')).toBeVisible()
  await expect(page.getByText('This is a Phase 1 demo. Reservations are free')).toBeVisible()

  await page.getByRole('button', { name: 'Get quote' }).click()
  await expect(page.getByText('This demo does not collect money.')).toBeVisible()
  await page.getByRole('button', { name: 'Hold for 10 minutes' }).click()

  await expect(page).toHaveURL(/\/account\/bookings\/[0-9a-f-]+$/)
  const reservationId = page.url().split('/').at(-1)
  expect(reservationId).toBeTruthy()
  await expect(
    page.getByText(
      'Exact address and access instructions appear here after the reservation is confirmed.',
    ),
  ).toBeVisible()
  await expect(page.getByText('123 E2E Test Lane')).toHaveCount(0)
  await expectNoCriticalA11y(page)

  await page.getByRole('button', { name: 'Confirm reservation' }).click()
  await expect(
    page.getByText(
      'Reservation confirmed. The exact address and access details are now available.',
    ),
  ).toBeVisible()
  await expect(page.getByText('123 E2E Test Lane')).toBeVisible()
  await expect(page.getByText('Use gate code 9090 and park in bay two.')).toBeVisible()
  await expect(page.getByText('Confirmed', { exact: true })).toBeVisible()

  const confirmedResponse = await request.get(`${state.apiBaseUrl}/reservations/${reservationId}`, {
    headers: { Authorization: `Bearer ${state.customer.token}` },
  })
  expect(confirmedResponse.ok()).toBeTruthy()
  const confirmed = (await confirmedResponse.json()) as { start: string; end: string }
  await signOut(page)

  await signIn(page, state.owner.email)
  await page.goto('/account/reservations')
  await expect(page.getByRole('heading', { name: 'Reservations' })).toBeVisible()
  await expect(page.getByText('E2E Customer')).toBeVisible()
  await page.getByRole('link', { name: 'View reservation' }).first().click()
  await expect(page.getByText('123 E2E Test Lane')).toBeVisible()
  await page.getByLabel(/Reason/).fill('Owner demo cancellation')
  await page.getByRole('button', { name: 'Cancel reservation' }).click()
  await expect(page.getByText('Reservation cancelled.')).toBeVisible()
  await expect(page.getByText('Cancelled', { exact: true })).toBeVisible()
  await signOut(page)

  const released = await request.post(`${state.apiBaseUrl}/reservations/quote`, {
    headers: { Authorization: `Bearer ${state.customer.token}` },
    data: {
      listing_id: state.listingId,
      vehicle_id: state.vehicleId,
      start: confirmed.start,
      end: confirmed.end,
    },
  })
  expect(released.ok(), await released.text()).toBeTruthy()

  await signIn(page, state.admin.email)
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Operations overview' })).toBeVisible()
  await expect(page.getByText('Pending listings')).toBeVisible()
  await expectNoCriticalA11y(page)

  await page.goto(`/admin/reservations/${reservationId}`)
  await expect(page.getByRole('heading', { name: state.title })).toBeVisible()
  await expect(page.getByText('Audit timeline')).toBeVisible()
  await expect(page.getByText('reservation.cancelled')).toBeVisible()
  await expect(page.getByText('Owner demo cancellation')).toBeVisible()

  await page.goto('/admin/audit')
  await expect(page.getByRole('heading', { name: 'Audit log' })).toBeVisible()
  await page.getByLabel('Entity type').fill('reservation')
  await page.getByLabel('Entity ID').fill(String(reservationId))
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect(
    page.locator('article.audit-event-card').filter({ hasText: 'reservation.cancelled' }),
  ).toHaveCount(1)
  await signOut(page)
})

test('mobile layout and keyboard sign-in work at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await signIn(page, state.customer.email)
  await page.goto(`/parking/${state.listingId}`)
  await expect(page.getByRole('heading', { name: state.title })).toBeVisible()
  await expectNoCriticalA11y(page)

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
