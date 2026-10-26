import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { OwnerListingEditorPage } from '../pages/OwnerListingEditorPage'
import type { OwnerListing, UserProfile } from '../types'

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    getMe: vi.fn(),
    getOwnerListing: vi.fn(),
  }
})

const profile: UserProfile = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'owner@example.test',
  full_name: 'Demo Owner',
  phone: null,
  is_admin: false,
  status: 'active',
  owner_terms_version: '2026-10-26',
  owner_terms_accepted_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const listing: OwnerListing = {
  id: '22222222-2222-2222-2222-222222222222',
  title: 'Covered driveway near college road',
  description: 'A quiet covered driveway with easy access from the main road.',
  status: 'pending_review',
  latitude: 19.9981,
  longitude: 73.7902,
  address_line: '12 College Road',
  locality: 'College Road',
  city: 'Nashik',
  state: 'Maharashtra',
  pincode: '422005',
  parking: {
    parking_type: 'driveway',
    supported_vehicle_types: ['hatchback', 'sedan'],
    max_length_mm: 4700,
    max_width_mm: 1900,
    max_height_mm: 1800,
    is_covered: true,
    access_method: 'code',
    access_instructions: 'Use gate code 4455.',
    amenities: ['cctv', 'lighting'],
    restrictions: 'No commercial vehicles.',
    pricing_model: 'hourly_with_daily_cap',
    price_hourly_paise: 5000,
    price_daily_cap_paise: 30000,
    min_booking_minutes: 60,
    max_booking_minutes: 1440,
    advance_booking_max_days: 30,
  },
  photos: [
    {
      id: '33333333-3333-3333-3333-333333333333',
      url: 'https://example.test/photo.jpg',
      width: 320,
      height: 240,
      position: 0,
      is_cover: true,
      mime_type: 'image/jpeg',
    },
  ],
  moderation_note: null,
  submitted_at: new Date().toISOString(),
  approved_at: null,
  rejected_at: null,
  paused_at: null,
  archived_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('OwnerListingEditorPage', () => {
  it('allows pending photos to change without unlocking listing fields', async () => {
    vi.mocked(api.getMe).mockResolvedValue(profile)
    vi.mocked(api.getOwnerListing).mockResolvedValue(listing)
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={[`/account/listings/${listing.id}/edit`]}>
        <Routes>
          <Route path="/account/listings/:listingId/edit" element={<OwnerListingEditorPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByLabelText('Listing title')).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Photos and status' }))

    expect(screen.getByLabelText('Upload a photo')).toBeEnabled()
    expect(screen.getByText(/photos can still be adjusted while/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled()
  })
})
