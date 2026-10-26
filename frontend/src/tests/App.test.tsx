import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const unsubscribe = vi.fn()

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe } },
      })),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      refreshSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
    },
  },
}))

describe('App routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
  })

  it('renders the landing page and demo notice', async () => {
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: /parking reservations, without/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no payments are collected/i)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Sign in' })).toHaveLength(2)
  })

  it('renders the login route', async () => {
    window.history.pushState({}, '', '/login')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('renders the password reset request route', async () => {
    window.history.pushState({}, '', '/reset-password')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Reset password' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeInTheDocument()
  })
})

describe('V2 listing routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects an anonymous visitor away from owner listings', async () => {
    window.history.pushState({}, '', '/account/listings')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('renders an active public listing from the API', async () => {
    const listing = {
      id: '11111111-1111-1111-1111-111111111111',
      title: 'Covered driveway near college road',
      description: 'A quiet covered driveway with easy access from the main road.',
      latitude: 19.9981,
      longitude: 73.7902,
      locality: 'College Road',
      city: 'Nashik',
      state: 'Maharashtra',
      parking: {
        parking_type: 'driveway',
        supported_vehicle_types: ['hatchback', 'sedan'],
        max_length_mm: 4700,
        max_width_mm: 1900,
        max_height_mm: 1800,
        is_covered: true,
        access_method: 'code',
        amenities: ['CCTV', 'lighting'],
        restrictions: 'No commercial vehicles.',
        pricing_model: 'hourly_with_daily_cap',
        price_hourly_paise: 5000,
        price_daily_cap_paise: 30000,
        min_booking_minutes: 60,
        max_booking_minutes: 1440,
        advance_booking_max_days: 30,
      },
      photos: [],
      updated_at: new Date().toISOString(),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(listing), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    window.history.pushState({}, '', `/parking/${listing.id}`)
    render(<App />)

    expect(await screen.findByRole('heading', { name: listing.title })).toBeInTheDocument()
    expect(
      screen.getByText(/exact address and access instructions are shared only/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/₹50 \/ hour/i)).toBeInTheDocument()
  })
})
