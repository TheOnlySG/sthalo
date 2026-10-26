import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { createVehicle, deleteVehicle, errorMessage, listVehicles, updateVehicle } from '../lib/api'
import type { Vehicle, VehicleInput, VehicleType } from '../types'
import { VEHICLE_LABELS, VEHICLE_TYPES } from '../types'

const MAX_VEHICLES = 10

function parseDimension(value: string): number | null {
  if (!value.trim()) {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 10_000) {
    throw new Error('Dimensions must be between 1 and 10,000 mm.')
  }
  return Math.round(parsed)
}

export function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [vehicleType, setVehicleType] = useState<VehicleType>('sedan')
  const [registrationNo, setRegistrationNo] = useState('')
  const [lengthMm, setLengthMm] = useState('')
  const [widthMm, setWidthMm] = useState('')
  const [heightMm, setHeightMm] = useState('')
  const [isEv, setIsEv] = useState(false)

  useEffect(() => {
    let active = true
    listVehicles()
      .then((items) => {
        if (active) {
          setVehicles(items)
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

  function resetForm() {
    setEditingId(null)
    setVehicleType('sedan')
    setRegistrationNo('')
    setLengthMm('')
    setWidthMm('')
    setHeightMm('')
    setIsEv(false)
  }

  function startEdit(vehicle: Vehicle) {
    setEditingId(vehicle.id)
    setVehicleType(vehicle.vehicle_type)
    setRegistrationNo(vehicle.registration_no ?? '')
    setLengthMm(vehicle.length_mm === null ? '' : String(vehicle.length_mm))
    setWidthMm(vehicle.width_mm === null ? '' : String(vehicle.width_mm))
    setHeightMm(vehicle.height_mm === null ? '' : String(vehicle.height_mm))
    setIsEv(vehicle.is_ev)
    setError(null)
    setNotice(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const input: VehicleInput = {
        vehicle_type: vehicleType,
        registration_no: registrationNo.trim() ? registrationNo.trim() : null,
        length_mm: parseDimension(lengthMm),
        width_mm: parseDimension(widthMm),
        height_mm: parseDimension(heightMm),
        is_ev: isEv,
      }
      if (editingId) {
        const updated = await updateVehicle(editingId, input)
        setVehicles((current) =>
          current.map((vehicle) => (vehicle.id === updated.id ? updated : vehicle)),
        )
        setNotice('Vehicle updated.')
      } else {
        const created = await createVehicle(input)
        setVehicles((current) => [...current, created])
        setNotice('Vehicle added.')
      }
      resetForm()
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(vehicle: Vehicle) {
    if (!window.confirm(`Remove the ${VEHICLE_LABELS[vehicle.vehicle_type].toLowerCase()}?`)) {
      return
    }
    setDeletingId(vehicle.id)
    setError(null)
    setNotice(null)
    try {
      await deleteVehicle(vehicle.id)
      setVehicles((current) => current.filter((item) => item.id !== vehicle.id))
      if (editingId === vehicle.id) {
        resetForm()
      }
      setNotice('Vehicle removed.')
    } catch (deleteError) {
      setError(errorMessage(deleteError))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Account</p>
          <h1>Your vehicles</h1>
          <p className="muted">
            {vehicles.length} of {MAX_VEHICLES} vehicles. Registration details stay private.
          </p>
        </div>
        <Link className="button button-secondary" to="/account/profile">
          Back to profile
        </Link>
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

      <div className="two-column vehicles-layout">
        <section className="panel">
          <h2>{editingId ? 'Edit vehicle' : 'Add a vehicle'}</h2>
          <form className="form" onSubmit={handleSubmit}>
            <label className="field">
              <span>Vehicle type</span>
              <select
                value={vehicleType}
                onChange={(event) => setVehicleType(event.target.value as VehicleType)}
              >
                {VEHICLE_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Registration number (optional)</span>
              <input
                type="text"
                value={registrationNo}
                onChange={(event) => setRegistrationNo(event.target.value)}
                maxLength={32}
                placeholder="MH12AB1234"
              />
              <small>Never shown publicly.</small>
            </label>
            <div className="dimension-grid">
              <label className="field">
                <span>Length (mm)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={10000}
                  value={lengthMm}
                  onChange={(event) => setLengthMm(event.target.value)}
                />
              </label>
              <label className="field">
                <span>Width (mm)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={10000}
                  value={widthMm}
                  onChange={(event) => setWidthMm(event.target.value)}
                />
              </label>
              <label className="field">
                <span>Height (mm)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={10000}
                  value={heightMm}
                  onChange={(event) => setHeightMm(event.target.value)}
                />
              </label>
            </div>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={isEv}
                onChange={(event) => setIsEv(event.target.checked)}
              />
              <span>Electric vehicle</span>
            </label>
            <div className="form-actions">
              <button className="button" type="submit" disabled={saving}>
                {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add vehicle'}
              </button>
              {editingId ? (
                <button className="button button-quiet" type="button" onClick={resetForm}>
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>Saved vehicles</h2>
          {loading ? (
            <p className="status-message" role="status">
              Loading vehicles…
            </p>
          ) : vehicles.length === 0 ? (
            <p className="muted">No vehicles yet. Add one to use later booking flows.</p>
          ) : (
            <ul className="vehicle-list">
              {vehicles.map((vehicle) => (
                <li className="vehicle-card" key={vehicle.id}>
                  <div>
                    <h3>{VEHICLE_LABELS[vehicle.vehicle_type]}</h3>
                    <p className="muted">
                      {vehicle.registration_no ?? 'No registration'} ·{' '}
                      {vehicle.is_ev ? 'Electric' : 'Petrol/diesel'}
                    </p>
                    <p className="muted">
                      {vehicle.length_mm ?? '—'} × {vehicle.width_mm ?? '—'} ×{' '}
                      {vehicle.height_mm ?? '—'} mm
                    </p>
                  </div>
                  <div className="card-actions">
                    <button
                      className="button button-small button-secondary"
                      type="button"
                      onClick={() => startEdit(vehicle)}
                    >
                      Edit
                    </button>
                    <button
                      className="button button-small button-danger"
                      type="button"
                      onClick={() => void handleDelete(vehicle)}
                      disabled={deletingId === vehicle.id}
                    >
                      {deletingId === vehicle.id ? 'Removing…' : 'Remove'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  )
}
