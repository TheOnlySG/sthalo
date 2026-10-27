import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, listOwnerReservations } from '../lib/api'
import { ReservationList } from '../components/ReservationList'
import { isReservationToday } from '../lib/reservationFormat'
import { RESERVATION_STATUS_OPTIONS, type Reservation, type ReservationStatus } from '../types'

type FilterValue = ReservationStatus | 'all'

export function OwnerReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [filter, setFilter] = useState<FilterValue>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [now] = useState(() => new Date())

  useEffect(() => {
    let active = true
    listOwnerReservations()
      .then((items) => {
        if (active) {
          setReservations(items)
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
  }, [])

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading owner reservations…
      </p>
    )
  }

  const live = reservations.filter(
    (reservation) => reservation.status === 'confirmed' || reservation.status === 'active',
  )
  const today = live.filter((reservation) => isReservationToday(reservation.start, now))
  const upcoming = live.filter(
    (reservation) => reservation.status === 'confirmed' && new Date(reservation.start) > now,
  )
  const expiring = reservations.filter(
    (reservation) => reservation.status === 'pending_confirmation',
  )
  const visible =
    filter === 'all'
      ? reservations
      : reservations.filter((reservation) => reservation.status === filter)

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Owner</p>
          <h1>Reservations</h1>
          <p className="muted">
            Track today’s arrivals, upcoming bookings, and holds waiting for confirmation.
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-secondary" to="/account/listings">
            My listings
          </Link>
        </div>
      </header>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="owner-metrics">
        <div className="metric-card">
          <span>Today</span>
          <strong>{today.length}</strong>
          <small>Confirmed or active windows</small>
        </div>
        <div className="metric-card">
          <span>Upcoming</span>
          <strong>{upcoming.length}</strong>
          <small>Confirmed future bookings</small>
        </div>
        <div className="metric-card metric-warning">
          <span>Expiring holds</span>
          <strong>{expiring.length}</strong>
          <small>Awaiting customer confirmation</small>
        </div>
      </div>

      <label className="field compact-field reservation-filter">
        <span>Status</span>
        <select value={filter} onChange={(event) => setFilter(event.target.value as FilterValue)}>
          <option value="all">All reservations</option>
          {RESERVATION_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <ReservationList reservations={visible} detailBasePath="/account/reservations" />
    </section>
  )
}
