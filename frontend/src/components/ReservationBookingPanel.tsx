import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { createReservation, errorMessage, listVehicles, quoteReservation } from '../lib/api'
import { defaultBookingWindow, formatMoney, localInputToIso } from '../lib/reservationFormat'
import { VEHICLE_LABELS, type PublicListing, type ReservationQuote, type Vehicle } from '../types'

export function ReservationBookingPanel({ listing }: { listing: PublicListing }) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const initialWindow = defaultBookingWindow()
  const sessionId = session?.user.id ?? null
  const [vehicleState, setVehicleState] = useState<{
    sessionId: string | null
    items: Vehicle[]
    error: string | null
  }>({ sessionId: null, items: [], error: null })
  const [vehicleId, setVehicleId] = useState('')
  const [start, setStart] = useState(initialWindow.start)
  const [end, setEnd] = useState(initialWindow.end)
  const [quote, setQuote] = useState<ReservationQuote | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (!sessionId) {
      return
    }
    listVehicles()
      .then((items) => {
        if (!active) {
          return
        }
        setVehicleState({ sessionId, items, error: null })
        setVehicleId(items[0]?.id ?? '')
      })
      .catch((loadError: unknown) => {
        if (active) {
          setVehicleState({
            sessionId,
            items: [],
            error: errorMessage(loadError),
          })
        }
      })
    return () => {
      active = false
    }
  }, [sessionId])

  function changeWindow(nextStart: string, nextEnd: string) {
    setStart(nextStart)
    setEnd(nextEnd)
    setQuote(null)
    setError(null)
  }

  async function handleQuote() {
    setQuoting(true)
    setError(null)
    setQuote(null)
    try {
      const nextQuote = await quoteReservation({
        listing_id: listing.id,
        vehicle_id: effectiveVehicleId,
        start: localInputToIso(start),
        end: localInputToIso(end),
      })
      setQuote(nextQuote)
    } catch (quoteError) {
      setError(errorMessage(quoteError))
    } finally {
      setQuoting(false)
    }
  }

  async function handleHold() {
    setCreating(true)
    setError(null)
    try {
      const reservation = await createReservation(
        {
          listing_id: listing.id,
          vehicle_id: effectiveVehicleId,
          start: localInputToIso(start),
          end: localInputToIso(end),
        },
        crypto.randomUUID(),
      )
      navigate(`/account/bookings/${reservation.id}`)
    } catch (createError) {
      setError(errorMessage(createError))
      setQuote(null)
    } finally {
      setCreating(false)
    }
  }

  const vehicles = vehicleState.items
  const loadingVehicles = Boolean(sessionId) && vehicleState.sessionId !== sessionId
  const vehicleError = vehicleState.error
  const supportedVehicles = vehicles.filter((vehicle) =>
    listing.parking.supported_vehicle_types.includes(vehicle.vehicle_type),
  )
  const selectedVehicle =
    vehicles.find((vehicle) => vehicle.id === vehicleId) ?? supportedVehicles[0] ?? null
  const effectiveVehicleId = selectedVehicle?.id ?? ''

  return (
    <section className="panel booking-panel" id="book">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Reserve</p>
          <h2>Request this parking space</h2>
        </div>
        <span className="status-badge status-neutral">No payment</span>
      </div>

      {!session ? (
        <div className="booking-empty">
          <p>Sign in to get an exact price and hold this space for 10 minutes.</p>
          <Link className="button" to="/login">
            Sign in to book
          </Link>
        </div>
      ) : loadingVehicles ? (
        <p className="status-message" role="status">
          Loading your vehicles…
        </p>
      ) : vehicleError ? (
        <p className="alert alert-error" role="alert">
          {vehicleError}
        </p>
      ) : vehicles.length === 0 ? (
        <div className="booking-empty">
          <p>Add a vehicle to check fit and request this bay.</p>
          <Link className="button" to="/account/vehicles">
            Add a vehicle
          </Link>
        </div>
      ) : supportedVehicles.length === 0 ? (
        <p className="alert alert-error" role="alert">
          None of your saved vehicles fit this listing. Add a supported vehicle type first.
        </p>
      ) : (
        <form
          className="form booking-form"
          onSubmit={(event) => {
            event.preventDefault()
            void handleQuote()
          }}
        >
          <label className="field">
            <span>Vehicle</span>
            <select
              value={effectiveVehicleId}
              onChange={(event) => {
                setVehicleId(event.target.value)
                setQuote(null)
              }}
              required
            >
              {supportedVehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {VEHICLE_LABELS[vehicle.vehicle_type]}
                  {vehicle.registration_no ? ` · ${vehicle.registration_no}` : ''}
                </option>
              ))}
            </select>
            <small>Only vehicle types supported by this listing are shown.</small>
          </label>

          <div className="two-field-grid">
            <label className="field">
              <span>Start</span>
              <input
                type="datetime-local"
                step="900"
                value={start}
                onChange={(event) => changeWindow(event.target.value, end)}
                required
              />
            </label>
            <label className="field">
              <span>End</span>
              <input
                type="datetime-local"
                step="900"
                value={end}
                onChange={(event) => changeWindow(start, event.target.value)}
                required
              />
            </label>
          </div>
          <p className="muted booking-time-note">
            Times use your device timezone. Bookings are rounded to 15-minute boundaries.
          </p>

          {error ? (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="form-actions">
            <button className="button button-secondary" type="submit" disabled={quoting || !end}>
              {quoting ? 'Checking…' : 'Get quote'}
            </button>
          </div>

          {quote ? (
            <div className="quote-box" aria-live="polite">
              <div className="quote-heading">
                <span>Informational total</span>
                <strong>{formatMoney(quote.total_paise)}</strong>
              </div>
              <p>{quote.price.calculation}</p>
              <p className="muted">
                This demo does not collect money. The price is recorded with the reservation.
              </p>
              <button
                className="button"
                type="button"
                onClick={() => void handleHold()}
                disabled={creating}
              >
                {creating ? 'Holding…' : 'Hold for 10 minutes'}
              </button>
            </div>
          ) : null}
        </form>
      )}
    </section>
  )
}
