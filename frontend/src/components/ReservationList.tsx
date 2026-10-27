import { Link } from 'react-router-dom'
import { formatMoney, formatReservationDate } from '../lib/reservationFormat'
import { ReservationStatusBadge } from './ReservationStatusBadge'
import type { Reservation } from '../types'

export function ReservationList({
  reservations,
  detailBasePath,
}: {
  reservations: Reservation[]
  detailBasePath: string
}) {
  if (reservations.length === 0) {
    return (
      <section className="panel empty-panel">
        <h2>No reservations here</h2>
        <p className="muted">New reservations will appear in this list.</p>
      </section>
    )
  }

  return (
    <div className="reservation-list">
      {reservations.map((reservation) => (
        <article className="panel reservation-card" key={reservation.id}>
          <div className="reservation-card-heading">
            <div>
              <p className="eyebrow">{reservation.reference}</p>
              <h2>{reservation.listing.title}</h2>
              <p className="muted">
                {reservation.listing.locality}, {reservation.listing.city}
              </p>
            </div>
            <ReservationStatusBadge status={reservation.status} />
          </div>
          <dl className="reservation-card-meta">
            <div>
              <dt>Window</dt>
              <dd>
                {formatReservationDate(reservation.start)} →{' '}
                {formatReservationDate(reservation.end)}
              </dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{formatMoney(reservation.total_paise)}</dd>
            </div>
            {reservation.customer_name ? (
              <div>
                <dt>Customer</dt>
                <dd>{reservation.customer_name}</dd>
              </div>
            ) : null}
          </dl>
          <div className="form-actions">
            <Link className="button button-small" to={`${detailBasePath}/${reservation.id}`}>
              View reservation
            </Link>
          </div>
        </article>
      ))}
    </div>
  )
}
