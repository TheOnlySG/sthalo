import type { ReactNode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const mapMock = vi.hoisted(() => ({
  getBounds: () => ({
    getWest: () => 73.75,
    getSouth: () => 19.96,
    getEast: () => 73.82,
    getNorth: () => 20.02,
  }),
  getZoom: () => 13,
  setView: vi.fn(),
  fitBounds: vi.fn(),
  panTo: vi.fn(),
}))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children?: ReactNode }) => (
    <div data-testid="map-canvas">{children}</div>
  ),
  TileLayer: () => null,
  Circle: () => null,
  Rectangle: () => null,
  Tooltip: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  CircleMarker: ({
    children,
    eventHandlers,
  }: {
    children?: ReactNode
    eventHandlers: { click: () => void }
  }) => (
    <button type="button" aria-label="Map marker" onClick={() => eventHandlers.click()}>
      {children}
    </button>
  ),
  useMap: () => mapMock,
}))

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      refreshSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
    },
  },
}))

const searchResult = {
  items: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      title: 'Covered driveway near College Road',
      description: 'A quiet covered driveway close to the main road.',
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
        amenities: ['CCTV'],
        restrictions: 'No commercial vehicles.',
        pricing_model: 'hourly_with_daily_cap',
        price_hourly_paise: 5000,
        price_daily_cap_paise: 30000,
        min_booking_minutes: 60,
        max_booking_minutes: 1440,
        advance_booking_max_days: 30,
      },
      cover_url: null,
      distance_m: 180,
      updated_at: new Date().toISOString(),
    },
  ],
  next_cursor: null,
  mode: 'radius',
  center_latitude: 19.9975,
  center_longitude: 73.7898,
  radius_m: 2000,
  bbox: null,
  sort: 'distance',
}

describe('V3 search page', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/search')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('loads active results with approximate distance and privacy messaging', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(searchResult), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'Find parking in Nashik' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('link', { name: searchResult.items[0].title }),
    ).toBeInTheDocument()
    expect(screen.getByText('180 m away')).toBeInTheDocument()
    expect(screen.getByText(/exact addresses and access details stay private/i)).toBeInTheDocument()
    expect(screen.getByText(/pins are approximate/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'OpenStreetMap' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Map marker' })).toHaveLength(1)

    const requestedUrl = String(fetchMock.mock.calls[0]?.[0])
    expect(requestedUrl).toContain('/search/parking?')
    expect(requestedUrl).toContain('lat=19.9975')
    expect(requestedUrl).toContain('lng=73.7898')
    expect(requestedUrl).toContain('radius_m=2000')
    expect(requestedUrl).toContain('sort=distance')
  })

  it('switches to a bounding-box search when searching the visible map area', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(searchResult), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByRole('link', { name: searchResult.items[0].title })

    fireEvent.click(screen.getByRole('button', { name: 'Search this map area' }))

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2))
    const requestedUrl = String(fetchMock.mock.calls.at(-1)?.[0])
    expect(requestedUrl).toContain('bbox=73.750000%2C19.960000%2C73.820000%2C20.020000')
    expect(requestedUrl).not.toContain('radius_m=')
  })
})
