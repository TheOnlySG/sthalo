import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AdminNav } from '../components/AdminNav'
import { ReservationStatusBadge } from '../components/ReservationStatusBadge'
import { errorMessage, getAdminReservation } from '../lib/api'
import { formatMoney, formatReservationDate } from '../lib/reservationFormat'
import { VEHICLE_LABELS, type AdminReservationDetail } from '../types'

export function AdminReservationDetailPage() {
  const { reservationId } = useParams()
  const [detail, setDetail] = useState<AdminReservationDetail | null>(null)
  const [loading, setLoading] = useState(Boolean(reservationId))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (!reservationId) {
      return
    }
    getAdminReservation(reservationId)
      .then((next) => {
        if (active) {
          setDetail(next)
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
  }, [reservationId])

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading reservation inspection…
      </p>
    )
  }

  if (!detail) {
    return (
      <section className="page-stack">
        <AdminNav />
        <div className="panel narrow-panel">
          <h1>Reservation unavailable</h1>
          <p className="alert alert-error" role="alert">
            {error ?? 'This reservation could not be loaded.'}
          </p>
          <Link className="button" to="/admin/reservations">
            Back to reservations
          </Link>
        </div>
      </section>
    )
  }

  const reservation = detail.reservation
  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin · {reservation.reference}</p>
          <h1>{reservation.listing.title}</h1>
          <div className="reservation-heading-meta">
            <ReservationStatusBadge status={reservation.status} />
            <span className="muted">{reservation.customer_name}</span>
          </div>
        </div>
        <Link className="button button-secondary" to="/admin/reservations">
          Back to reservations
        </Link>
      </header>
      <AdminNav />

      <div className="two-column">
        <section className="panel">
          <h2>Reservation</h2>
          <dl className="definition-list">
            <div>
              <dt>Customer</dt>
              <dd>{reservation.customer_name ?? 'Unknown'}</dd>
            </div>
            <div>
              <dt>Owner</dt>
              <dd>{reservation.owner_name}</dd>
            </div>
            <div>
              <dt>Vehicle</dt>
              <dd>
                {VEHICLE_LABELS[reservation.vehicle.vehicle_type]}
                {reservation.vehicle.registration_no
                  ? ` · ${reservation.vehicle.registration_no}`
                  : ''}
              </dd>
            </div>
            <div>
              <dt>Start</dt>
              <dd>{formatReservationDate(reservation.start)}</dd>
            </div>
            <div>
              <dt>End</dt>
              <dd>{formatReservationDate(reservation.end)}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{formatMoney(reservation.total_paise)}</dd>
            </div>
            <div>
              <dt>Exact address</dt>
              <dd>
                {reservation.exact_address ?? 'Unavailable'}
                {reservation.pincode ? `, ${reservation.pincode}` : ''}
              </dd>
            </div>
            <div>
              <dt>Access</dt>
              <dd>{reservation.access_instructions ?? 'None supplied'}</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <h2>Audit timeline</h2>
          {detail.audit.length === 0 ? (
            <p className="muted">No audit events were recorded for this reservation.</p>
          ) : (
            <ol className="audit-timeline">
              {detail.audit.map((event) => (
                <li key={event.id}>
                  <div className="audit-timeline-heading">
                    <strong>{event.action}</strong>
                    <span className="muted">{formatReservationDate(event.created_at)}</span>
                  </div>
                  <p className="muted">
                    {event.actor_name ?? event.actor_type}
                    {event.actor_email ? ` · ${event.actor_email}` : ''}
                  </p>
                  {event.after ? (
                    <pre className="audit-json">{JSON.stringify(event.after, null, 2)}</pre>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </section>
  )
}
