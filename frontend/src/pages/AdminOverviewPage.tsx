import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AdminNav } from '../components/AdminNav'
import { errorMessage, getAdminOverview } from '../lib/api'
import type { AdminOverview } from '../types'

export function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getAdminOverview()
      .then((next) => {
        if (active) {
          setOverview(next)
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
  }, [])

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Operations overview</h1>
          <p className="muted">Read-only counts for moderation and live booking activity.</p>
        </div>
      </header>
      <AdminNav />
      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="status-message" role="status">
          Loading overview…
        </p>
      ) : overview ? (
        <div className="owner-metrics">
          <div className="metric-card">
            <span>Pending listings</span>
            <strong>{overview.pending_listings}</strong>
            <small>Waiting for moderation</small>
          </div>
          <div className="metric-card">
            <span>Live reservations</span>
            <strong>{overview.live_reservations}</strong>
            <small>Confirmed or in progress</small>
          </div>
          <div className="metric-card metric-warning">
            <span>Expiring holds</span>
            <strong>{overview.expiring_holds}</strong>
            <small>Waiting for customer confirmation</small>
          </div>
        </div>
      ) : null}
      <div className="admin-quick-links">
        <Link className="button" to="/admin/listings">
          Moderate listings
        </Link>
        <Link className="button button-secondary" to="/admin/reservations">
          Inspect reservations
        </Link>
        <Link className="button button-secondary" to="/admin/audit">
          Read audit log
        </Link>
      </div>
    </section>
  )
}
