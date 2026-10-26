import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  archiveListing,
  createListing,
  deleteListingPhoto,
  errorMessage,
  getMe,
  getOwnerListing,
  pauseListing,
  resumeListing,
  submitListing,
  updateListing,
  updateListingPhoto,
  uploadListingPhoto,
} from '../lib/api'
import {
  ACCESS_METHOD_LABELS,
  PARKING_TYPE_LABELS,
  PRICING_MODEL_LABELS,
  formatPriceSummary,
  formatRupees,
} from '../lib/listingFormat'
import { CURRENT_OWNER_TERMS_VERSION } from '../lib/ownerTerms'
import { StatusBadge } from '../components/StatusBadge'
import type {
  AccessMethod,
  ListingBasicsInput,
  ListingStatus,
  OwnerListing,
  ParkingInput,
  ParkingType,
  PricingModel,
  UserProfile,
  VehicleType,
} from '../types'
import { VEHICLE_TYPES } from '../types'

type Step = 1 | 2 | 3 | 4

interface FormState {
  title: string
  description: string
  latitude: string
  longitude: string
  address_line: string
  locality: string
  city: string
  state: string
  pincode: string
  parking_type: ParkingType
  supported_vehicle_types: VehicleType[]
  max_length_mm: string
  max_width_mm: string
  max_height_mm: string
  is_covered: boolean
  access_method: AccessMethod
  access_instructions: string
  amenities: string
  restrictions: string
  pricing_model: PricingModel
  price_hourly: string
  price_daily_cap: string
  min_booking_minutes: string
  max_booking_minutes: string
  advance_booking_max_days: string
}

const EDITABLE_STATUSES: ListingStatus[] = ['draft', 'active', 'paused', 'rejected']
const PHOTO_EDITABLE_STATUSES: ListingStatus[] = [...EDITABLE_STATUSES, 'pending_review']
const PROTECTED_PHOTO_STATUSES: ListingStatus[] = ['active', 'paused', 'pending_review']

const EMPTY_FORM: FormState = {
  title: '',
  description: '',
  latitude: '19.9975',
  longitude: '73.7898',
  address_line: '',
  locality: '',
  city: 'Nashik',
  state: 'Maharashtra',
  pincode: '',
  parking_type: 'driveway',
  supported_vehicle_types: ['hatchback', 'sedan'],
  max_length_mm: '',
  max_width_mm: '',
  max_height_mm: '',
  is_covered: false,
  access_method: 'open',
  access_instructions: '',
  amenities: '',
  restrictions: '',
  pricing_model: 'hourly_with_daily_cap',
  price_hourly: '50',
  price_daily_cap: '300',
  min_booking_minutes: '60',
  max_booking_minutes: '1440',
  advance_booking_max_days: '30',
}

function formFromListing(listing: OwnerListing): FormState {
  const parking = listing.parking
  return {
    title: listing.title,
    description: listing.description,
    latitude: String(listing.latitude),
    longitude: String(listing.longitude),
    address_line: listing.address_line,
    locality: listing.locality,
    city: listing.city,
    state: listing.state,
    pincode: listing.pincode,
    parking_type: parking.parking_type,
    supported_vehicle_types: parking.supported_vehicle_types,
    max_length_mm: parking.max_length_mm === null ? '' : String(parking.max_length_mm),
    max_width_mm: parking.max_width_mm === null ? '' : String(parking.max_width_mm),
    max_height_mm: parking.max_height_mm === null ? '' : String(parking.max_height_mm),
    is_covered: parking.is_covered,
    access_method: parking.access_method,
    access_instructions: parking.access_instructions ?? '',
    amenities: parking.amenities.join(', '),
    restrictions: parking.restrictions,
    pricing_model: parking.pricing_model,
    price_hourly:
      parking.price_hourly_paise === null ? '' : String(parking.price_hourly_paise / 100),
    price_daily_cap:
      parking.price_daily_cap_paise === null ? '' : String(parking.price_daily_cap_paise / 100),
    min_booking_minutes: String(parking.min_booking_minutes),
    max_booking_minutes: String(parking.max_booking_minutes),
    advance_booking_max_days: String(parking.advance_booking_max_days),
  }
}

function requiredNumber(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label} must be between ${min} and ${max}.`)
  }
  return parsed
}

function optionalInteger(value: string, label: string): number | null {
  if (!value.trim()) {
    return null
  }
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 10_000) {
    throw new Error(`${label} must be a positive whole number up to 10,000.`)
  }
  return parsed
}

function optionalPaise(value: string, label: string): number | null {
  if (!value.trim()) {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${label} must be zero or more.`)
  }
  return Math.round(parsed * 100)
}

function buildBasics(form: FormState): ListingBasicsInput {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    latitude: requiredNumber(form.latitude, 'Latitude', 6, 38),
    longitude: requiredNumber(form.longitude, 'Longitude', 68, 98),
    address_line: form.address_line.trim(),
    locality: form.locality.trim(),
    city: form.city.trim(),
    state: form.state.trim(),
    pincode: form.pincode.trim(),
  }
}

function buildParking(form: FormState): ParkingInput {
  if (form.supported_vehicle_types.length === 0) {
    throw new Error('Choose at least one supported vehicle type.')
  }
  return {
    parking_type: form.parking_type,
    supported_vehicle_types: form.supported_vehicle_types,
    max_length_mm: optionalInteger(form.max_length_mm, 'Maximum length'),
    max_width_mm: optionalInteger(form.max_width_mm, 'Maximum width'),
    max_height_mm: optionalInteger(form.max_height_mm, 'Maximum height'),
    is_covered: form.is_covered,
    access_method: form.access_method,
    access_instructions: form.access_instructions.trim() || null,
    amenities: form.amenities
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    restrictions: form.restrictions.trim(),
    pricing_model: form.pricing_model,
    price_hourly_paise:
      form.pricing_model === 'flat_daily' ? null : optionalPaise(form.price_hourly, 'Hourly price'),
    price_daily_cap_paise:
      form.pricing_model === 'hourly' ? null : optionalPaise(form.price_daily_cap, 'Daily cap'),
    min_booking_minutes: requiredNumber(form.min_booking_minutes, 'Minimum booking', 30, 10_080),
    max_booking_minutes: requiredNumber(form.max_booking_minutes, 'Maximum booking', 30, 10_080),
    advance_booking_max_days: requiredNumber(
      form.advance_booking_max_days,
      'Advance booking window',
      1,
      90,
    ),
  }
}

function stepTitle(step: Step): string {
  if (step === 1) {
    return 'Basics and location'
  }
  if (step === 2) {
    return 'Parking details'
  }
  if (step === 3) {
    return 'Pricing and limits'
  }
  return 'Photos and publishing'
}

export function OwnerListingEditorPage() {
  const { listingId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const isNew = !listingId
  const initialStep = (location.state as { step?: Step; notice?: string } | null)?.step ?? 1
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [listing, setListing] = useState<OwnerListing | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [step, setStep] = useState<Step>(initialStep)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [action, setAction] = useState<string | null>(null)
  const [declaration, setDeclaration] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(
    (location.state as { notice?: string } | null)?.notice ?? null,
  )

  useEffect(() => {
    let active = true
    const requests: [Promise<UserProfile>, Promise<OwnerListing> | null] = [
      getMe(),
      listingId ? getOwnerListing(listingId) : null,
    ]
    Promise.all([requests[0], requests[1] ?? Promise.resolve(null)])
      .then(([nextProfile, nextListing]) => {
        if (!active) {
          return
        }
        setProfile(nextProfile)
        if (nextListing) {
          setListing(nextListing)
          setForm(formFromListing(nextListing))
        }
        setError(null)
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
  }, [listingId])

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function toggleVehicleType(type: VehicleType) {
    setForm((current) => {
      const selected = current.supported_vehicle_types.includes(type)
      return {
        ...current,
        supported_vehicle_types: selected
          ? current.supported_vehicle_types.filter((item) => item !== type)
          : [...current.supported_vehicle_types, type],
      }
    })
  }

  async function saveBasics(): Promise<boolean> {
    setError(null)
    setNotice(null)
    try {
      buildBasics(form)
      if (!isNew && !listing) {
        return false
      }
      setStep(2)
      return true
    } catch (saveError) {
      setError(errorMessage(saveError))
      return false
    }
  }

  async function saveParking(): Promise<boolean> {
    setError(null)
    setNotice(null)
    try {
      buildParking(form)
      if (!isNew && !listing) {
        return false
      }
      setStep(3)
      return true
    } catch (saveError) {
      setError(errorMessage(saveError))
      return false
    }
  }

  async function savePricing(): Promise<boolean> {
    setError(null)
    setNotice(null)
    try {
      const basics = buildBasics(form)
      const parking = buildParking(form)
      if (isNew) {
        setSaving(true)
        const created = await createListing({
          ...basics,
          owner_terms_accepted: true,
          parking,
        })
        navigate(`/account/listings/${created.id}/edit`, {
          replace: true,
          state: {
            step: 4,
            notice: 'Draft created. Add at least one photo before submitting.',
          },
        })
        return true
      }
      if (!listing) {
        return false
      }
      if (!editable) {
        setStep(4)
        return true
      }
      setSaving(true)
      const updated = await updateListing(listing.id, { ...basics, parking })
      setListing(updated)
      setNotice(
        updated.status === 'pending_review'
          ? 'Changes saved. The listing is back in review.'
          : 'Listing details saved.',
      )
      setStep(4)
      return true
    } catch (saveError) {
      setError(errorMessage(saveError))
      return false
    } finally {
      setSaving(false)
    }
  }

  function replaceListing(updated: OwnerListing, message: string) {
    setListing(updated)
    setNotice(message)
    setError(null)
  }

  async function handlePhotoUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !listing) {
      return
    }
    setUploading(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await uploadListingPhoto(listing.id, file)
      replaceListing(updated, 'Photo uploaded.')
    } catch (uploadError) {
      setError(errorMessage(uploadError))
    } finally {
      setUploading(false)
    }
  }

  async function handlePhotoPatch(
    photoId: string,
    values: { position?: number; is_cover?: boolean },
  ) {
    if (!listing) {
      return
    }
    setAction(photoId)
    setError(null)
    try {
      const updated = await updateListingPhoto(listing.id, photoId, values)
      replaceListing(updated, 'Photo updated.')
    } catch (patchError) {
      setError(errorMessage(patchError))
    } finally {
      setAction(null)
    }
  }

  async function handlePhotoDelete(photoId: string) {
    if (!listing || !window.confirm('Delete this photo?')) {
      return
    }
    setAction(photoId)
    setError(null)
    try {
      await deleteListingPhoto(listing.id, photoId)
      const updated = await getOwnerListing(listing.id)
      replaceListing(updated, 'Photo deleted.')
    } catch (deleteError) {
      setError(errorMessage(deleteError))
    } finally {
      setAction(null)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!listing) {
      return
    }
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await submitListing(listing.id, declaration)
      replaceListing(updated, 'Listing submitted for review.')
    } catch (submitError) {
      setError(errorMessage(submitError))
    } finally {
      setSaving(false)
    }
  }

  async function handleLifecycle(nextAction: 'pause' | 'resume' | 'archive') {
    if (!listing) {
      return
    }
    if (nextAction === 'archive' && !window.confirm('Archive this listing?')) {
      return
    }
    setAction(nextAction)
    setError(null)
    setNotice(null)
    try {
      const updated =
        nextAction === 'pause'
          ? await pauseListing(listing.id)
          : nextAction === 'resume'
            ? await resumeListing(listing.id)
            : await archiveListing(listing.id)
      replaceListing(updated, `Listing ${nextAction}d.`)
    } catch (lifecycleError) {
      setError(errorMessage(lifecycleError))
    } finally {
      setAction(null)
    }
  }

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading the listing editor…
      </p>
    )
  }

  if (error && !profile) {
    return (
      <section className="panel narrow-panel">
        <h1>Listing unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error}
        </p>
        <Link className="button" to="/account/listings">
          Back to listings
        </Link>
      </section>
    )
  }

  if (isNew && profile?.owner_terms_version !== CURRENT_OWNER_TERMS_VERSION) {
    return (
      <section className="panel narrow-panel">
        <p className="eyebrow">Owner terms</p>
        <h1>Accept owner terms first</h1>
        <p>
          The current owner terms version is <strong>{CURRENT_OWNER_TERMS_VERSION}</strong>.
        </p>
        <Link className="button" to="/account/profile">
          Go to owner terms
        </Link>
      </section>
    )
  }

  const editable = listing ? EDITABLE_STATUSES.includes(listing.status) : true
  const photosEditable = listing ? PHOTO_EDITABLE_STATUSES.includes(listing.status) : true
  const lastPhotoLocked =
    listing !== null &&
    PROTECTED_PHOTO_STATUSES.includes(listing.status) &&
    listing.photos.length === 1
  const termsCurrent = profile?.owner_terms_version === CURRENT_OWNER_TERMS_VERSION

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">{isNew ? 'New listing' : 'Manage listing'}</p>
          <h1>{isNew ? 'Create a parking space' : (listing?.title ?? 'Listing editor')}</h1>
          <p className="muted">
            {listing ? (
              <>
                <StatusBadge status={listing.status} /> Last updated{' '}
                {new Date(listing.updated_at).toLocaleString()}
              </>
            ) : (
              'Three short steps, then photos and moderation.'
            )}
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-secondary" to="/account/listings">
            Back to listings
          </Link>
          {listing && step !== 4 ? (
            <button className="button button-secondary" type="button" onClick={() => setStep(4)}>
              Photos and status
            </button>
          ) : null}
          {listing?.status === 'active' ? (
            <Link className="button" to={`/parking/${listing.id}`}>
              Public page
            </Link>
          ) : null}
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
      {!termsCurrent && !isNew ? (
        <p className="alert alert-error" role="alert">
          Owner terms need to be accepted again before this listing can be submitted.
        </p>
      ) : null}
      {listing && !editable ? (
        <p className="alert alert-error" role="alert">
          This listing is {listing.status.replace('_', ' ')} and cannot be edited. You can review
          its details and photos below.
        </p>
      ) : null}
      {listing && listing.moderation_note ? (
        <p className="alert alert-error" role="status">
          Moderator note: {listing.moderation_note}
        </p>
      ) : null}

      <ol className="step-indicator" aria-label="Listing progress">
        {([1, 2, 3, 4] as Step[]).map((item) => (
          <li
            className={item === step ? 'step-current' : item < step ? 'step-done' : ''}
            key={item}
          >
            <span>{item}</span>
            {stepTitle(item)}
          </li>
        ))}
      </ol>

      {step === 1 ? (
        <section className="panel">
          <h2>Basics and location</h2>
          <p className="muted">
            Use the actual location for moderation. Public pages only show an approximate point
            roughly 80–200 metres away.
          </p>
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault()
              void saveBasics()
            }}
          >
            <label className="field">
              <span>Listing title</span>
              <input
                value={form.title}
                onChange={(event) => updateField('title', event.target.value)}
                minLength={5}
                maxLength={80}
                required
                disabled={!editable}
                placeholder="Covered driveway near college road"
              />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea
                value={form.description}
                onChange={(event) => updateField('description', event.target.value)}
                minLength={20}
                maxLength={2000}
                rows={4}
                required
                disabled={!editable}
              />
            </label>
            <div className="two-field-grid">
              <label className="field">
                <span>Latitude</span>
                <input
                  type="number"
                  step="any"
                  value={form.latitude}
                  onChange={(event) => updateField('latitude', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Longitude</span>
                <input
                  type="number"
                  step="any"
                  value={form.longitude}
                  onChange={(event) => updateField('longitude', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
            </div>
            <label className="field">
              <span>Address line</span>
              <input
                value={form.address_line}
                onChange={(event) => updateField('address_line', event.target.value)}
                minLength={3}
                maxLength={240}
                required
                disabled={!editable}
              />
              <small>Only visible to you and moderators.</small>
            </label>
            <div className="two-field-grid">
              <label className="field">
                <span>Locality</span>
                <input
                  value={form.locality}
                  onChange={(event) => updateField('locality', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>City</span>
                <input
                  value={form.city}
                  onChange={(event) => updateField('city', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>State</span>
                <input
                  value={form.state}
                  onChange={(event) => updateField('state', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Pincode</span>
                <input
                  value={form.pincode}
                  onChange={(event) => updateField('pincode', event.target.value)}
                  pattern="[0-9]{6}"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  disabled={!editable}
                />
              </label>
            </div>
            <div className="form-actions">
              <button className="button" type="submit" disabled={saving}>
                Continue to parking
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {step === 2 ? (
        <section className="panel">
          <h2>Parking details</h2>
          <p className="muted">Share fit limits and practical access notes for the moderator.</p>
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault()
              void saveParking()
            }}
          >
            <div className="two-field-grid">
              <label className="field">
                <span>Parking type</span>
                <select
                  value={form.parking_type}
                  onChange={(event) =>
                    updateField('parking_type', event.target.value as ParkingType)
                  }
                  disabled={!editable}
                >
                  {Object.entries(PARKING_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Access method</span>
                <select
                  value={form.access_method}
                  onChange={(event) =>
                    updateField('access_method', event.target.value as AccessMethod)
                  }
                  disabled={!editable}
                >
                  {Object.entries(ACCESS_METHOD_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <fieldset className="check-grid" disabled={!editable}>
              <legend>Supported vehicles</legend>
              {VEHICLE_TYPES.map((vehicle) => (
                <label className="checkbox-field" key={vehicle.value}>
                  <input
                    type="checkbox"
                    checked={form.supported_vehicle_types.includes(vehicle.value)}
                    onChange={() => toggleVehicleType(vehicle.value)}
                  />
                  <span>{vehicle.label}</span>
                </label>
              ))}
            </fieldset>
            <div className="dimension-grid">
              <label className="field">
                <span>Max length (mm)</span>
                <input
                  type="number"
                  value={form.max_length_mm}
                  onChange={(event) => updateField('max_length_mm', event.target.value)}
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Max width (mm)</span>
                <input
                  type="number"
                  value={form.max_width_mm}
                  onChange={(event) => updateField('max_width_mm', event.target.value)}
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Max height (mm)</span>
                <input
                  type="number"
                  value={form.max_height_mm}
                  onChange={(event) => updateField('max_height_mm', event.target.value)}
                  disabled={!editable}
                />
              </label>
            </div>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.is_covered}
                onChange={(event) => updateField('is_covered', event.target.checked)}
                disabled={!editable}
              />
              <span>Covered parking</span>
            </label>
            <label className="field">
              <span>Access instructions</span>
              <textarea
                value={form.access_instructions}
                onChange={(event) => updateField('access_instructions', event.target.value)}
                rows={3}
                maxLength={1000}
                disabled={!editable}
                placeholder="Gate code, landmark, or who to call on arrival."
              />
              <small>Never shown on the public listing.</small>
            </label>
            <label className="field">
              <span>Amenities</span>
              <input
                value={form.amenities}
                onChange={(event) => updateField('amenities', event.target.value)}
                disabled={!editable}
                placeholder="CCTV, lighting, EV socket"
              />
              <small>Comma-separated.</small>
            </label>
            <label className="field">
              <span>Restrictions</span>
              <textarea
                value={form.restrictions}
                onChange={(event) => updateField('restrictions', event.target.value)}
                rows={3}
                maxLength={1000}
                disabled={!editable}
                placeholder="No commercial vehicles, no overnight parking, and so on."
              />
            </label>
            <div className="form-actions">
              <button className="button button-secondary" type="button" onClick={() => setStep(1)}>
                Back
              </button>
              <button className="button" type="submit" disabled={saving}>
                Continue to pricing
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {step === 3 ? (
        <section className="panel">
          <h2>Pricing and limits</h2>
          <p className="muted">
            Prices are shown in rupees. No payments are collected in this demo.
          </p>
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault()
              void savePricing()
            }}
          >
            <label className="field">
              <span>Pricing model</span>
              <select
                value={form.pricing_model}
                onChange={(event) =>
                  updateField('pricing_model', event.target.value as PricingModel)
                }
                disabled={!editable}
              >
                {Object.entries(PRICING_MODEL_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div className="two-field-grid">
              {form.pricing_model !== 'flat_daily' ? (
                <label className="field">
                  <span>Hourly price (₹)</span>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={form.price_hourly}
                    onChange={(event) => updateField('price_hourly', event.target.value)}
                    required
                    disabled={!editable}
                  />
                </label>
              ) : null}
              {form.pricing_model !== 'hourly' ? (
                <label className="field">
                  <span>Daily cap (₹)</span>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={form.price_daily_cap}
                    onChange={(event) => updateField('price_daily_cap', event.target.value)}
                    required
                    disabled={!editable}
                  />
                </label>
              ) : null}
            </div>
            <div className="dimension-grid">
              <label className="field">
                <span>Minimum booking (minutes)</span>
                <input
                  type="number"
                  min={30}
                  max={10080}
                  value={form.min_booking_minutes}
                  onChange={(event) => updateField('min_booking_minutes', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Maximum booking (minutes)</span>
                <input
                  type="number"
                  min={30}
                  max={10080}
                  value={form.max_booking_minutes}
                  onChange={(event) => updateField('max_booking_minutes', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
              <label className="field">
                <span>Advance window (days)</span>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={form.advance_booking_max_days}
                  onChange={(event) => updateField('advance_booking_max_days', event.target.value)}
                  required
                  disabled={!editable}
                />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-secondary" type="button" onClick={() => setStep(2)}>
                Back
              </button>
              <button className="button" type="submit" disabled={saving}>
                {saving
                  ? 'Saving…'
                  : isNew
                    ? 'Create draft'
                    : editable
                      ? 'Save and continue'
                      : 'View photos and status'}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {step === 4 ? (
        listing ? (
          <div className="two-column editor-columns">
            <section className="panel">
              <h2>Photos</h2>
              <p className="muted">
                Add 1–8 JPEG, PNG, or WebP photos. Images are re-encoded and metadata is removed.
              </p>
              {listing.status === 'active' || listing.status === 'paused' ? (
                <p className="alert alert-error" role="alert">
                  Adding or changing photos will return this listing to review.
                </p>
              ) : null}
              {listing.status === 'pending_review' ? (
                <p className="alert alert-success" role="status">
                  Photos can still be adjusted while this listing is in review.
                </p>
              ) : null}
              <label className="field">
                <span>Upload a photo</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => void handlePhotoUpload(event)}
                  disabled={uploading || !photosEditable}
                />
              </label>
              {uploading ? (
                <p className="status-message" role="status">
                  Uploading and checking the photo…
                </p>
              ) : null}
              {listing.photos.length === 0 ? (
                <p className="muted">No photos uploaded yet.</p>
              ) : (
                <div className="photo-manager">
                  {[...listing.photos]
                    .sort((left, right) => left.position - right.position)
                    .map((photo, index) => (
                      <article className="photo-manager-item" key={photo.id}>
                        <img src={photo.url} alt={`Listing photo ${index + 1}`} />
                        <div className="photo-manager-meta">
                          <span>
                            {photo.is_cover ? 'Cover photo' : `Photo ${index + 1}`} · {photo.width}×
                            {photo.height}
                          </span>
                          <div className="card-actions">
                            {!photo.is_cover ? (
                              <button
                                className="button button-small button-secondary"
                                type="button"
                                onClick={() => void handlePhotoPatch(photo.id, { is_cover: true })}
                                disabled={action !== null || !photosEditable}
                              >
                                Make cover
                              </button>
                            ) : null}
                            <button
                              className="button button-small button-secondary"
                              type="button"
                              onClick={() =>
                                void handlePhotoPatch(photo.id, {
                                  position: Math.max(0, photo.position - 1),
                                })
                              }
                              disabled={index === 0 || action !== null || !photosEditable}
                            >
                              Move up
                            </button>
                            <button
                              className="button button-small button-secondary"
                              type="button"
                              onClick={() =>
                                void handlePhotoPatch(photo.id, {
                                  position: photo.position + 1,
                                })
                              }
                              disabled={
                                index === listing.photos.length - 1 ||
                                action !== null ||
                                !photosEditable
                              }
                            >
                              Move down
                            </button>
                            <button
                              className="button button-small button-danger"
                              type="button"
                              onClick={() => void handlePhotoDelete(photo.id)}
                              disabled={action !== null || !photosEditable || lastPhotoLocked}
                              title={
                                lastPhotoLocked
                                  ? 'Add a replacement photo before deleting the last one.'
                                  : undefined
                              }
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </article>
                    ))}
                </div>
              )}
            </section>

            <section className="panel">
              <h2>Publish</h2>
              <dl className="definition-list">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge status={listing.status} />
                  </dd>
                </div>
                <div>
                  <dt>Price</dt>
                  <dd>{formatPriceSummary(listing.parking)}</dd>
                </div>
                <div>
                  <dt>Photos</dt>
                  <dd>{listing.photos.length} of 8</dd>
                </div>
                <div>
                  <dt>Hourly price</dt>
                  <dd>{formatRupees(listing.parking.price_hourly_paise)}</dd>
                </div>
                <div>
                  <dt>Daily cap</dt>
                  <dd>{formatRupees(listing.parking.price_daily_cap_paise)}</dd>
                </div>
              </dl>

              {listing.status === 'draft' || listing.status === 'rejected' ? (
                <form className="form" onSubmit={(event) => void handleSubmit(event)}>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={declaration}
                      onChange={(event) => setDeclaration(event.target.checked)}
                    />
                    <span>
                      I confirm the listing details are accurate and I have the right to list this
                      space.
                    </span>
                  </label>
                  <button className="button" type="submit" disabled={saving || !declaration}>
                    {saving ? 'Submitting…' : 'Submit for review'}
                  </button>
                </form>
              ) : null}

              {listing.status === 'pending_review' ? (
                <p className="alert alert-success" role="status">
                  Submitted for moderation. Listing details are locked, but photos can still be
                  adjusted.
                </p>
              ) : null}
              {listing.status === 'active' ? (
                <div className="form-actions">
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void handleLifecycle('pause')}
                    disabled={action !== null}
                  >
                    Pause listing
                  </button>
                  <button
                    className="button button-danger"
                    type="button"
                    onClick={() => void handleLifecycle('archive')}
                    disabled={action !== null}
                  >
                    Archive
                  </button>
                </div>
              ) : null}
              {listing.status === 'paused' ? (
                <div className="form-actions">
                  <button
                    className="button"
                    type="button"
                    onClick={() => void handleLifecycle('resume')}
                    disabled={action !== null}
                  >
                    Resume listing
                  </button>
                  <button
                    className="button button-danger"
                    type="button"
                    onClick={() => void handleLifecycle('archive')}
                    disabled={action !== null}
                  >
                    Archive
                  </button>
                </div>
              ) : null}
              {listing.status === 'pending_review' ||
              listing.status === 'rejected' ||
              listing.status === 'draft' ? (
                <button
                  className="button button-quiet"
                  type="button"
                  onClick={() => void handleLifecycle('archive')}
                  disabled={action !== null}
                >
                  Archive listing
                </button>
              ) : null}

              <div className="form-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => setStep(3)}
                >
                  Back to pricing
                </button>
              </div>
            </section>
          </div>
        ) : (
          <section className="panel">
            <h2>Create the draft first</h2>
            <p className="muted">Photos can be added after the draft exists.</p>
            <button className="button" type="button" onClick={() => setStep(3)}>
              Back to pricing
            </button>
          </section>
        )
      ) : null}
    </section>
  )
}
