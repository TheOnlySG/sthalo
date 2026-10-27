import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { cancelReservation, confirmReservation, errorMessage, getReservation } from '../lib/api'
import { countdownLabel, formatMoney, formatReservationDate } from '../lib/reservationFormat'
import { ReservationStatusBadge } from '../components/ReservationStatusBadge'
import { VEHICLE_LABELS, type Reservation } from '../types'

export function ReservationDetailPage() {
  const { reservationId } = useParams()
  const [reservation, setReservation] = useState<Reservation | null>(null)
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(Boolean(reservationId))
  const [busy, setBusy] = useState<'confirm' | 'cancel' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let active = true
    if (!reservationId) {
      return
    }
    getReservation(reservationId)
      .then((nextReservation) => {
        if (active) {
          setReservation(nextReservation)
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

  useEffect(() => {
    if (reservation?.status !== 'pending_confirmation') {
      return
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [reservation?.status])

  async function refresh() {
    if (!reservationId) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      setReservation(await getReservation(reservationId))
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm() {
    if (!reservation) {
      return
    }
    setBusy('confirm')
    setError(null)
    setNotice(null)
    try {
      const confirmed = await confirmReservation(reservation.id, crypto.randomUUID())
      setReservation(confirmed)
      setNotice('Reservation confirmed. The exact address and access details are now available.')
    } catch (confirmError) {
      setError(errorMessage(confirmError))
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  async function handleCancel() {
    if (!reservation) {
      return
    }
    const trimmed = reason.trim()
    if (reservation.viewer_role !== 'customer' && trimmed.length < 3) {
      setError('Add a cancellation reason of at least 3 characters.')
      return
    }
    setBusy('cancel')
    setError(null)
    setNotice(null)
    try {
      const cancelled = await cancelReservation(
        reservation.id,
        trimmed || null,
        crypto.randomUUID(),
      )
      setReservation(cancelled)
      setReason('')
      setNotice('Reservation cancelled.')
    } catch (cancelError) {
      setError(errorMessage(cancelError))
    } finally {
      setBusy(null)
    }
  }

  if (loading && !reservation) {
    return (
      <p className="status-message" role="status">
        Loading reservation…
      </p>
    )
  }

  if (!reservation) {
    return (
      <section className="panel narrow-panel">
        <h1>Reservation unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error ?? 'This reservation does not exist or you do not have access.'}
        </p>
        <Link className="button" to="/account/bookings">
          Back to bookings
        </Link>
      </section>
    )
  }

  const pending = reservation.status === 'pending_confirmation'
  const countdown = countdownLabel(reservation.hold_expires_at, now)
  const priceCalculation =
    typeof reservation.price_snapshot.calculation === 'string'
      ? reservation.price_snapshot.calculation
      : null

  return (
    <section className="page-stack reservation-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Reservation {reservation.reference}</p>
          <h1>{reservation.listing.title}</h1>
          <div className="reservation-heading-meta">
            <ReservationStatusBadge status={reservation.status} />
            <span className="muted">
              {reservation.listing.locality}, {reservation.listing.city}
            </span>
          </div>
        </div>
        <div className="header-actions">
          <Link
            className="button button-secondary"
            to={
              reservation.viewer_role === 'customer' ? '/account/bookings' : '/account/reservations'
            }
          >
            Back to list
          </Link>
          <button className="button button-quiet" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
      </header>

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

      {pending ? (
        <section className="panel hold-panel">
          <div>
            <p className="eyebrow">10-minute hold</p>
            <h2>{countdown}</h2>
            <p className="muted">
              Confirm for free before the hold expires. No payment is collected in this demo.
            </p>
          </div>
          {reservation.can_confirm ? (
            <button
              className="button"
              type="button"
              onClick={() => void handleConfirm()}
              disabled={busy !== null}
            >
              {busy === 'confirm' ? 'Confirming…' : 'Confirm reservation'}
            </button>
          ) : (
            <span className="status-badge status-danger">Hold no longer active</span>
          )}
        </section>
      ) : null}

      <div className="two-column">
        <section className="panel">
          <h2>Booking details</h2>
          <dl className="definition-list">
            <div>
              <dt>Start</dt>
              <dd>{formatReservationDate(reservation.start)}</dd>
            </div>
            <div>
              <dt>End</dt>
              <dd>{formatReservationDate(reservation.end)}</dd>
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
              <dt>Owner</dt>
              <dd>{reservation.owner_name}</dd>
            </div>
            {reservation.customer_name ? (
              <div>
                <dt>Customer</dt>
                <dd>{reservation.customer_name}</dd>
              </div>
            ) : null}
            <div>
              <dt>Informational total</dt>
              <dd>{formatMoney(reservation.total_paise)}</dd>
            </div>
            {priceCalculation ? (
              <div>
                <dt>Price basis</dt>
                <dd>{priceCalculation}</dd>
              </div>
            ) : null}
            {reservation.cancel_reason ? (
              <div>
                <dt>Cancellation reason</dt>
                <dd>{reservation.cancel_reason}</dd>
              </div>
            ) : null}
          </dl>
          <p className="muted reservation-disclaimer">
            No money is collected. This is not a payment receipt.
          </p>
        </section>

        <section className="panel">
          <h2>Address and access</h2>
          {reservation.exact_address ? (
            <dl className="definition-list">
              <div>
                <dt>Exact address</dt>
                <dd>
                  {reservation.exact_address}
                  {reservation.pincode ? `, ${reservation.pincode}` : ''}
                </dd>
              </div>
              {reservation.exact_latitude !== null && reservation.exact_longitude !== null ? (
                <div>
                  <dt>Exact point</dt>
                  <dd>
                    {reservation.exact_latitude.toFixed(5)},{' '}
                    {reservation.exact_longitude.toFixed(5)}
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>Access</dt>
                <dd>
                  {reservation.access_instructions ?? 'The owner has not added instructions.'}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="muted">
              Exact address and access instructions appear here after the reservation is confirmed.
            </p>
          )}
          <p className="alert alert-success" role="status">
            Demo only — no payment is collected.
          </p>
        </section>
      </div>

      {reservation.can_cancel ? (
        <section className="panel">
          <h2>Cancel reservation</h2>
          <p className="muted">
            {reservation.viewer_role === 'customer'
              ? 'You can cancel before the booking starts. A reason is optional.'
              : 'Owner cancellations require a reason and are written to the audit log.'}
          </p>
          <div className="cancel-form">
            <label className="field">
              <span>
                Reason {reservation.viewer_role === 'customer' ? '(optional)' : '(required)'}
              </span>
              <textarea
                rows={3}
                maxLength={500}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Share why this reservation is being cancelled."
              />
            </label>
            <button
              className="button button-danger"
              type="button"
              onClick={() => void handleCancel()}
              disabled={busy !== null}
            >
              {busy === 'cancel' ? 'Cancelling…' : 'Cancel reservation'}
            </button>
          </div>
        </section>
      ) : null}
    </section>
  )
}
