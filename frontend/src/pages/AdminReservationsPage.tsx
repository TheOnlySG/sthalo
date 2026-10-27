import { useEffect, useState } from 'react'
import { AdminNav } from '../components/AdminNav'
import { ReservationList } from '../components/ReservationList'
import { errorMessage, listAdminReservations } from '../lib/api'
import { RESERVATION_STATUS_OPTIONS, type Reservation, type ReservationStatus } from '../types'

type FilterValue = ReservationStatus | 'all'

export function AdminReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [filter, setFilter] = useState<FilterValue>('all')
  const [loadedFilter, setLoadedFilter] = useState<FilterValue | null>(null)
  const [error, setError] = useState<string | null>(null)
  const loading = loadedFilter !== filter

  useEffect(() => {
    let active = true
    listAdminReservations(filter === 'all' ? undefined : filter)
      .then((items) => {
        if (active) {
          setReservations(items)
          setError(null)
        }
      })
      .catch((loadError: unknown) => {
        if (active) {
          setReservations([])
          setError(errorMessage(loadError))
        }
      })
      .finally(() => {
        if (active) {
          setLoadedFilter(filter)
        }
      })
    return () => {
      active = false
    }
  }, [filter])

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Reservations</h1>
          <p className="muted">Read-only inspection with customer and pricing details.</p>
        </div>
      </header>
      <AdminNav />
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
      {loading ? (
        <p className="status-message" role="status">
          Loading reservations…
        </p>
      ) : (
        <ReservationList reservations={reservations} detailBasePath="/admin/reservations" />
      )}
    </section>
  )
}
