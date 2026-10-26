import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, getMe, listOwnerListings } from '../lib/api'
import { CURRENT_OWNER_TERMS_VERSION } from '../lib/ownerTerms'
import { StatusBadge } from '../components/StatusBadge'
import type { OwnerListingSummary, UserProfile } from '../types'

export function OwnerListingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [listings, setListings] = useState<OwnerListingSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([getMe(), listOwnerListings()])
      .then(([nextProfile, nextListings]) => {
        if (!active) {
          return
        }
        setProfile(nextProfile)
        setListings(nextListings)
        setError(null)
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
  }, [])

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading your listings…
      </p>
    )
  }

  if (error || !profile) {
    return (
      <section className="panel narrow-panel">
        <h1>Listings unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error ?? 'Could not load your listings.'}
        </p>
      </section>
    )
  }

  const termsAccepted = profile.owner_terms_version === CURRENT_OWNER_TERMS_VERSION

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Owner dashboard</p>
          <h1>Your parking listings</h1>
          <p className="muted">
            Draft, submit, and manage the spaces you want to list. Public pages hide exact addresses
            and access instructions.
          </p>
        </div>
        {termsAccepted ? (
          <Link className="button" to="/account/listings/new">
            Add a parking space
          </Link>
        ) : null}
      </header>

      {!termsAccepted ? (
        <section className="panel callout-panel">
          <h2>Accept owner terms first</h2>
          <p>
            The current owner terms version is <strong>{CURRENT_OWNER_TERMS_VERSION}</strong>.
            Accept it on your profile before creating or submitting a listing.
          </p>
          <Link className="button" to="/account/profile">
            Go to owner terms
          </Link>
        </section>
      ) : null}

      {termsAccepted && listings.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No listings yet</h2>
          <p className="muted">
            Add a driveway, garage, or society slot. You will choose photos and pricing before
            submitting it for review.
          </p>
          <Link className="button" to="/account/listings/new">
            Create your first listing
          </Link>
        </section>
      ) : null}

      {listings.length > 0 ? (
        <div className="listing-grid">
          {listings.map((listing) => (
            <article className="panel listing-card" key={listing.id}>
              <div className="listing-card-cover">
                {listing.cover_url ? (
                  <img src={listing.cover_url} alt="" loading="lazy" />
                ) : (
                  <span>No photo yet</span>
                )}
              </div>
              <div className="listing-card-body">
                <div className="listing-card-heading">
                  <h2>{listing.title}</h2>
                  <StatusBadge status={listing.status} />
                </div>
                <p className="muted">
                  {listing.locality}, {listing.city} · {listing.photo_count} photo
                  {listing.photo_count === 1 ? '' : 's'}
                </p>
                {listing.moderation_note ? (
                  <p className="alert alert-error" role="status">
                    Moderator note: {listing.moderation_note}
                  </p>
                ) : null}
                <div className="card-actions">
                  <Link
                    className="button button-small button-secondary"
                    to={`/account/listings/${listing.id}/edit`}
                  >
                    Manage
                  </Link>
                  <Link
                    className="button button-small button-secondary"
                    to={`/account/listings/${listing.id}/availability`}
                  >
                    Availability
                  </Link>
                  {listing.status === 'active' ? (
                    <Link className="button button-small" to={`/parking/${listing.id}`}>
                      View public page
                    </Link>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  )
}
