import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  approveListing,
  errorMessage,
  getMe,
  listAdminListings,
  rejectListing,
  restoreListing,
  suspendListing,
} from '../lib/api'
import {
  LISTING_STATUS_LABELS,
  LISTING_STATUS_OPTIONS,
  formatPriceSummary,
  formatVehicleTypes,
} from '../lib/listingFormat'
import { AdminNav } from '../components/AdminNav'
import { StatusBadge } from '../components/StatusBadge'
import type { AdminListing, ListingStatus, UserProfile } from '../types'

type FilterValue = ListingStatus | 'all'

export function AdminListingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [listings, setListings] = useState<AdminListing[]>([])
  const [filter, setFilter] = useState<FilterValue>('pending_review')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getMe()
      .then((nextProfile) => {
        if (!active) {
          return
        }
        setProfile(nextProfile)
        if (!nextProfile.is_admin) {
          setError('Administrator access is required.')
          setLoading(false)
          return
        }
        return listAdminListings(filter === 'all' ? undefined : filter).then((items) => {
          if (active) {
            setListings(items)
          }
        })
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
  }, [filter])

  async function moderate(
    listing: AdminListing,
    action: 'approve' | 'reject' | 'suspend' | 'restore',
  ) {
    const note = (notes[listing.id] ?? '').trim()
    if (action !== 'approve' && note.length < 3) {
      setError('Add a moderation note of at least 3 characters.')
      return
    }
    setBusyId(listing.id)
    setError(null)
    setNotice(null)
    try {
      const updated =
        action === 'approve'
          ? await approveListing(listing.id, note || null)
          : action === 'reject'
            ? await rejectListing(listing.id, note)
            : action === 'suspend'
              ? await suspendListing(listing.id, note)
              : await restoreListing(listing.id, note)
      setListings((current) => {
        if (filter !== 'all' && updated.status !== filter) {
          return current.filter((item) => item.id !== updated.id)
        }
        return current.map((item) => (item.id === updated.id ? updated : item))
      })
      setNotes((current) => ({ ...current, [listing.id]: '' }))
      setNotice(`${listing.title}: ${LISTING_STATUS_LABELS[updated.status]}.`)
    } catch (moderationError) {
      setError(errorMessage(moderationError))
    } finally {
      setBusyId(null)
    }
  }

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading the moderation queue…
      </p>
    )
  }

  if (!profile?.is_admin) {
    return (
      <section className="panel narrow-panel">
        <h1>Admin only</h1>
        <p className="alert alert-error" role="alert">
          {error ?? 'Administrator access is required.'}
        </p>
        <Link className="button" to="/">
          Back home
        </Link>
      </section>
    )
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Local admin</p>
          <h1>Listing moderation</h1>
          <p className="muted">
            Approve, reject, suspend, or restore owner listings. Every action is recorded in the
            audit log.
          </p>
        </div>
        <label className="field compact-field">
          <span>Status</span>
          <select value={filter} onChange={(event) => setFilter(event.target.value as FilterValue)}>
            <option value="all">All statuses</option>
            {LISTING_STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </header>
      <AdminNav />

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="alert alert-success" role="status">
          {notice}
        </p>
      ) : null}

      {listings.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No listings in this queue</h2>
          <p className="muted">Nothing needs moderation for the selected status.</p>
        </section>
      ) : null}

      <div className="admin-list">
        {listings.map((listing) => (
          <article className="panel admin-card" key={listing.id}>
            <div className="admin-card-main">
              <div className="admin-card-heading">
                <div>
                  <h2>{listing.title}</h2>
                  <p className="muted">
                    {listing.owner.full_name} · {listing.owner.email}
                  </p>
                </div>
                <StatusBadge status={listing.status} />
              </div>
              <p>{listing.description}</p>
              <dl className="admin-details">
                <div>
                  <dt>Exact address</dt>
                  <dd>
                    {listing.address_line}, {listing.locality}, {listing.city}, {listing.state}{' '}
                    {listing.pincode}
                  </dd>
                </div>
                <div>
                  <dt>Coordinates</dt>
                  <dd>
                    {listing.latitude.toFixed(5)}, {listing.longitude.toFixed(5)}
                  </dd>
                </div>
                <div>
                  <dt>Price</dt>
                  <dd>{formatPriceSummary(listing.parking)}</dd>
                </div>
                <div>
                  <dt>Vehicles</dt>
                  <dd>{formatVehicleTypes(listing.parking.supported_vehicle_types)}</dd>
                </div>
                <div>
                  <dt>Access instructions</dt>
                  <dd>{listing.parking.access_instructions ?? 'None supplied'}</dd>
                </div>
                <div>
                  <dt>Submitted</dt>
                  <dd>
                    {listing.submitted_at
                      ? new Date(listing.submitted_at).toLocaleString()
                      : 'Not submitted'}
                  </dd>
                </div>
              </dl>
              {listing.photos.length > 0 ? (
                <div className="admin-photos">
                  {listing.photos.map((photo) => (
                    <a href={photo.url} target="_blank" rel="noreferrer" key={photo.id}>
                      <img src={photo.url} alt="Listing evidence" />
                    </a>
                  ))}
                </div>
              ) : (
                <p className="alert alert-error" role="alert">
                  No photos attached.
                </p>
              )}
            </div>

            <aside className="admin-card-actions">
              <label className="field">
                <span>Moderation note</span>
                <textarea
                  rows={4}
                  maxLength={500}
                  value={notes[listing.id] ?? ''}
                  onChange={(event) =>
                    setNotes((current) => ({ ...current, [listing.id]: event.target.value }))
                  }
                  placeholder="Required for rejection, suspension, and restore."
                />
              </label>
              <div className="form-actions">
                {listing.status === 'pending_review' ? (
                  <>
                    <button
                      className="button"
                      type="button"
                      onClick={() => void moderate(listing, 'approve')}
                      disabled={busyId === listing.id}
                    >
                      Approve
                    </button>
                    <button
                      className="button button-danger"
                      type="button"
                      onClick={() => void moderate(listing, 'reject')}
                      disabled={busyId === listing.id}
                    >
                      Reject
                    </button>
                  </>
                ) : null}
                {listing.status === 'active' ||
                listing.status === 'paused' ||
                listing.status === 'rejected' ? (
                  <button
                    className="button button-danger"
                    type="button"
                    onClick={() => void moderate(listing, 'suspend')}
                    disabled={busyId === listing.id}
                  >
                    Suspend
                  </button>
                ) : null}
                {listing.status === 'suspended' ? (
                  <button
                    className="button"
                    type="button"
                    onClick={() => void moderate(listing, 'restore')}
                    disabled={busyId === listing.id}
                  >
                    Restore
                  </button>
                ) : null}
                {listing.status === 'active' ? (
                  <Link className="button button-secondary" to={`/parking/${listing.id}`}>
                    Public page
                  </Link>
                ) : null}
              </div>
            </aside>
          </article>
        ))}
      </div>
    </section>
  )
}
