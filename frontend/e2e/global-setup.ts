import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { request } from '@playwright/test'
import { BACKEND_ROOT, DEMO_PASSWORD, REPO_ROOT, STATE_FILE, e2eEnv } from './env'

interface DemoUser {
  id: string
  email: string
  token: string
}

interface E2EState {
  apiBaseUrl: string
  listingId: string
  title: string
  customer: DemoUser
  owner: DemoUser
  admin: DemoUser
  vehicleId: string
  users: Array<{ id: string; email: string }>
}

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGOUqzjBQApgIkn1qIZRDUNKAwBgxgF+DAqMFgAAAABJRU5ErkJggg==',
  'base64',
)

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

async function main() {
  const env = e2eEnv()
  if (!env.supabaseUrl || !env.supabaseAnonKey || !env.supabaseServiceKey) {
    throw new Error('Missing local Supabase configuration in backend/.env')
  }
  const runId = `${Date.now()}-${process.pid}`
  const api = await request.newContext()
  const serviceHeaders = {
    apikey: env.supabaseServiceKey,
    Authorization: `Bearer ${env.supabaseServiceKey}`,
    'Content-Type': 'application/json',
  }

  async function createUser(label: string, fullName: string): Promise<DemoUser> {
    const email = `e2e-${label}-${runId}@example.invalid`
    const created = await api.post(`${env.supabaseUrl}/auth/v1/admin/users`, {
      headers: serviceHeaders,
      data: {
        email,
        password: DEMO_PASSWORD,
        email_confirm: true,
        user_metadata: { full_name: fullName },
      },
    })
    if (!created.ok()) {
      throw new Error(`create ${label} failed: ${created.status()} ${await created.text()}`)
    }
    const createdBody = (await created.json()) as { id: string }
    const signedIn = await api.post(`${env.supabaseUrl}/auth/v1/token?grant_type=password`, {
      headers: { apikey: env.supabaseAnonKey, 'Content-Type': 'application/json' },
      data: { email, password: DEMO_PASSWORD },
    })
    if (!signedIn.ok()) {
      throw new Error(`sign in ${label} failed: ${signedIn.status()} ${await signedIn.text()}`)
    }
    const tokenBody = (await signedIn.json()) as { access_token: string }
    return { id: createdBody.id, email, token: tokenBody.access_token }
  }

  const owner = await createUser('owner', 'E2E Owner')
  const customer = await createUser('customer', 'E2E Customer')
  const admin = await createUser('admin', 'E2E Admin')

  execFileSync(
    resolve(BACKEND_ROOT, '.venv/bin/python'),
    [resolve(BACKEND_ROOT, 'scripts/make_admin.py'), '--email', admin.email],
    { cwd: REPO_ROOT, stdio: 'pipe' },
  )

  const terms = await api.post(`${env.apiBaseUrl}/users/me/accept-owner-terms`, {
    headers: authHeaders(owner.token),
  })
  if (!terms.ok()) {
    throw new Error(`accept terms failed: ${terms.status()} ${await terms.text()}`)
  }

  const title = `[DEMO] E2E parking bay ${runId}`
  const listing = await api.post(`${env.apiBaseUrl}/owner/parking-listings`, {
    headers: authHeaders(owner.token),
    data: {
      title,
      description: 'Synthetic E2E demo driveway used only for local browser journey evidence.',
      latitude: 19.9975,
      longitude: 73.7898,
      address_line: '123 E2E Test Lane',
      locality: 'College Road',
      city: 'Nashik',
      state: 'Maharashtra',
      pincode: '422005',
      owner_terms_accepted: true,
      parking: {
        parking_type: 'driveway',
        supported_vehicle_types: ['hatchback', 'sedan'],
        max_length_mm: 4700,
        max_width_mm: 1900,
        max_height_mm: 1800,
        is_covered: true,
        access_method: 'code',
        access_instructions: 'Use gate code 9090 and park in bay two.',
        amenities: ['cctv', 'lighting'],
        restrictions: 'No commercial vehicles.',
        pricing_model: 'hourly_with_daily_cap',
        price_hourly_paise: 5000,
        price_daily_cap_paise: 30000,
        min_booking_minutes: 60,
        max_booking_minutes: 1440,
        advance_booking_max_days: 30,
      },
    },
  })
  if (!listing.ok()) {
    throw new Error(`create listing failed: ${listing.status()} ${await listing.text()}`)
  }
  const listingBody = await listing.json()

  const photo = await api.post(
    `${env.apiBaseUrl}/owner/parking-listings/${listingBody.id}/photos`,
    {
      headers: authHeaders(owner.token),
      multipart: {
        file: { name: 'demo.png', mimeType: 'image/png', buffer: TINY_PNG },
      },
    },
  )
  if (!photo.ok()) {
    throw new Error(`upload photo failed: ${photo.status()} ${await photo.text()}`)
  }

  const submitted = await api.post(
    `${env.apiBaseUrl}/owner/parking-listings/${listingBody.id}/submit`,
    { headers: authHeaders(owner.token), data: { declaration_accepted: true } },
  )
  if (!submitted.ok()) {
    throw new Error(`submit listing failed: ${submitted.status()} ${await submitted.text()}`)
  }

  const approved = await api.post(`${env.apiBaseUrl}/admin/listings/${listingBody.id}/approve`, {
    headers: authHeaders(admin.token),
    data: { note: 'E2E approval' },
  })
  if (!approved.ok()) {
    throw new Error(`approve listing failed: ${approved.status()} ${await approved.text()}`)
  }

  const rules = await api.put(
    `${env.apiBaseUrl}/owner/parking-listings/${listingBody.id}/availability-rules`,
    {
      headers: authHeaders(owner.token),
      data: {
        rules: [1, 2, 3, 4, 5, 6, 7].map((weekday) => ({
          weekday,
          start_time: '09:00:00',
          end_time: '18:00:00',
        })),
      },
    },
  )
  if (!rules.ok()) {
    throw new Error(`availability rules failed: ${rules.status()} ${await rules.text()}`)
  }

  const vehicle = await api.post(`${env.apiBaseUrl}/vehicles`, {
    headers: authHeaders(customer.token),
    data: {
      vehicle_type: 'hatchback',
      registration_no: `E2E${runId.slice(-6)}`,
      length_mm: 4000,
      width_mm: 1800,
      height_mm: 1600,
    },
  })
  if (!vehicle.ok()) {
    throw new Error(`create vehicle failed: ${vehicle.status()} ${await vehicle.text()}`)
  }

  const state: E2EState = {
    apiBaseUrl: env.apiBaseUrl,
    listingId: listingBody.id,
    title,
    customer,
    owner,
    admin,
    vehicleId: ((await vehicle.json()) as { id: string }).id,
    users: [owner, customer, admin].map(({ id, email }) => ({ id, email })),
  }
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2))
  await api.dispose()
  console.log(`Seeded E2E demo listing ${listingBody.id}`)
}

export default main
