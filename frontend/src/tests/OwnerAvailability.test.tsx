import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { OwnerAvailabilityPage } from '../pages/OwnerAvailabilityPage'
import type { OwnerListing } from '../types'

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    getOwnerListing: vi.fn(),
    getAvailabilityRules: vi.fn(),
    listBlockedIntervals: vi.fn(),
    replaceAvailabilityRules: vi.fn(),
  }
})

const listing: OwnerListing = {
  id: '22222222-2222-2222-2222-222222222222',
  title: 'Covered driveway near college road',
  description: 'A quiet covered driveway with easy access from the main road.',
  status: 'draft',
  latitude: 19.9981,
  longitude: 73.7902,
  address_line: '12 College Road',
  locality: 'College Road',
  city: 'Nashik',
  state: 'Maharashtra',
  pincode: '422005',
  parking: {
    parking_type: 'driveway',
    supported_vehicle_types: ['hatchback'],
    max_length_mm: null,
    max_width_mm: null,
    max_height_mm: null,
    is_covered: true,
    access_method: 'open',
    access_instructions: null,
    amenities: [],
    restrictions: '',
    pricing_model: 'hourly',
    price_hourly_paise: 5000,
    price_daily_cap_paise: null,
    min_booking_minutes: 60,
    max_booking_minutes: 1440,
    advance_booking_max_days: 30,
  },
  photos: [],
  moderation_note: null,
  submitted_at: null,
  approved_at: null,
  rejected_at: null,
  paused_at: null,
  archived_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('OwnerAvailabilityPage', () => {
  it('saves a weekly window added for Monday', async () => {
    vi.mocked(api.getOwnerListing).mockResolvedValue(listing)
    vi.mocked(api.getAvailabilityRules).mockResolvedValue([])
    vi.mocked(api.listBlockedIntervals).mockResolvedValue([])
    vi.mocked(api.replaceAvailabilityRules).mockResolvedValue([])
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={[`/account/listings/${listing.id}/availability`]}>
        <Routes>
          <Route
            path="/account/listings/:listingId/availability"
            element={<OwnerAvailabilityPage />}
          />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: listing.title })
    await user.click(screen.getAllByRole('button', { name: 'Add window' })[0])
    await user.click(screen.getByRole('button', { name: 'Save weekly rules' }))

    expect(api.replaceAvailabilityRules).toHaveBeenCalledWith(listing.id, [
      {
        weekday: 1,
        start_time: '09:00:00',
        end_time: '18:00:00',
        valid_from: null,
        valid_to: null,
      },
    ])
    expect(await screen.findByText('Weekly availability saved.')).toBeInTheDocument()
  })
})
