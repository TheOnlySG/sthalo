import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, getPublicListing } from '../lib/api'
import {
  ACCESS_METHOD_LABELS,
  PARKING_TYPE_LABELS,
  formatPriceSummary,
  formatVehicleTypes,
} from '../lib/listingFormat'
import { ListingPhotoGallery } from '../components/ListingPhotoGallery'
import type { PublicListing } from '../types'

export function PublicListingPage() {
  const { listingId } = useParams()
  const [listing, setListing] = useState<PublicListing | null>(null)
  const [loading, setLoading] = useState(Boolean(listingId))
  const [error, setError] = useState<string | null>(listingId ? null : 'Listing not found.')

  useEffect(() => {
    let active = true
    if (!listingId) {
      return
    }
    getPublicListing(listingId)
      .then((nextListing) => {
        if (active) {
          setListing(nextListing)
          setError(null)
        }
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(errorMessage(loadError))
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [listingId])

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading this parking space…
      </p>
    )
  }

  if (!listing) {
    return (
      <section className="panel narrow-panel">
        <p className="eyebrow">Parking listing</p>
        <h1>Listing unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error ?? 'This listing is not active or does not exist.'}
        </p>
        <Link className="button" to="/">
          Back home
        </Link>
      </section>
    )
  }

  const parking = listing.parking

  return (
    <section className="page-stack public-listing">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {listing.locality}, {listing.city}
          </p>
          <h1>{listing.title}</h1>
          <p className="listing-price">{formatPriceSummary(parking)}</p>
        </div>
        <Link className="button button-secondary" to="/">
          Back home
        </Link>
      </header>

      <ListingPhotoGallery photos={listing.photos} />

      <div className="two-column">
        <section className="panel">
          <h2>About this space</h2>
          <p>{listing.description}</p>
          <dl className="definition-list">
            <div>
              <dt>Parking type</dt>
              <dd>{PARKING_TYPE_LABELS[parking.parking_type]}</dd>
            </div>
            <div>
              <dt>Covered</dt>
              <dd>{parking.is_covered ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt>Access</dt>
              <dd>{ACCESS_METHOD_LABELS[parking.access_method]}</dd>
            </div>
            <div>
              <dt>Supported vehicles</dt>
              <dd>{formatVehicleTypes(parking.supported_vehicle_types)}</dd>
            </div>
            <div>
              <dt>Booking window</dt>
              <dd>
                {parking.min_booking_minutes}–{parking.max_booking_minutes} minutes
              </dd>
            </div>
            <div>
              <dt>Advance booking</dt>
              <dd>Up to {parking.advance_booking_max_days} days</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <h2>Location and rules</h2>
          <p className="muted">
            The map point is approximate. The exact address and access instructions are shared only
            after a reservation flow is added.
          </p>
          <p>
            Approximate point: {listing.latitude.toFixed(4)}, {listing.longitude.toFixed(4)}
          </p>
          {parking.amenities.length > 0 ? (
            <>
              <h3>Amenities</h3>
              <ul className="tag-list">
                {parking.amenities.map((amenity) => (
                  <li className="tag" key={amenity}>
                    {amenity}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <h3>Restrictions</h3>
          <p>{parking.restrictions || 'No extra restrictions listed.'}</p>
          <p className="alert alert-success" role="status">
            This is a Phase 1 demo. Payments and reservations are not enabled yet.
          </p>
        </section>
      </div>
    </section>
  )
}
