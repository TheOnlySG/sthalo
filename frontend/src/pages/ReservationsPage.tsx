import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, listMyReservations } from '../lib/api'
import { ReservationList } from '../components/ReservationList'
import { RESERVATION_STATUS_OPTIONS, type Reservation, type ReservationStatus } from '../types'

type FilterValue = ReservationStatus | 'all'

export function ReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [filter, setFilter] = useState<FilterValue>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listMyReservations()
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

  const visible =
    filter === 'all'
      ? reservations
      : reservations.filter((reservation) => reservation.status === filter)

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading your bookings…
      </p>
    )
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Customer</p>
          <h1>My bookings</h1>
          <p className="muted">
            Holds last 10 minutes. Confirmed reservations reveal the exact address and access
            details.
          </p>
        </div>
        <div className="header-actions">
          <Link className="button" to="/search">
            Find parking
          </Link>
        </div>
      </header>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

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

      <ReservationList reservations={visible} detailBasePath="/account/bookings" />
    </section>
  )
}
