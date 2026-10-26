import type { AccessMethod, ListingStatus, ParkingType, PricingModel, VehicleType } from '../types'

export const LISTING_STATUS_LABELS: Record<ListingStatus, string> = {
  draft: 'Draft',
  pending_review: 'Pending review',
  active: 'Active',
  rejected: 'Rejected',
  paused: 'Paused',
  suspended: 'Suspended',
  archived: 'Archived',
}

export const PARKING_TYPE_LABELS: Record<ParkingType, string> = {
  driveway: 'Driveway',
  garage: 'Garage',
  society_slot: 'Society slot',
  open_lot: 'Open lot',
  basement: 'Basement',
  shop_frontage: 'Shop frontage',
  other: 'Other',
}

export const ACCESS_METHOD_LABELS: Record<AccessMethod, string> = {
  open: 'Open access',
  guard_checkin: 'Guard check-in',
  code: 'Gate code',
  key_handover: 'Key handover',
  remote_owner: 'Remote owner opens',
}

export const PRICING_MODEL_LABELS: Record<PricingModel, string> = {
  hourly: 'Hourly',
  hourly_with_daily_cap: 'Hourly with a daily cap',
  flat_daily: 'Flat daily',
}

export const LISTING_STATUS_OPTIONS = Object.entries(LISTING_STATUS_LABELS) as Array<
  [ListingStatus, string]
>

export function formatRupees(paise: number | null): string {
  if (paise === null) {
    return 'Not set'
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: paise % 100 === 0 ? 0 : 2,
  }).format(paise / 100)
}

export function formatPriceSummary(parking: {
  pricing_model: PricingModel
  price_hourly_paise: number | null
  price_daily_cap_paise: number | null
}): string {
  if (parking.pricing_model === 'hourly') {
    return `${formatRupees(parking.price_hourly_paise)} / hour`
  }
  if (parking.pricing_model === 'hourly_with_daily_cap') {
    return `${formatRupees(parking.price_hourly_paise)} / hour · ${formatRupees(
      parking.price_daily_cap_paise,
    )} daily cap`
  }
  return `${formatRupees(parking.price_daily_cap_paise)} / day`
}

export function formatVehicleTypes(types: VehicleType[]): string {
  const labels: Record<VehicleType, string> = {
    two_wheeler: 'Two wheeler',
    hatchback: 'Hatchback',
    sedan: 'Sedan',
    suv: 'SUV',
    large: 'Large',
  }
  return types.map((type) => labels[type]).join(', ')
}

export function statusTone(status: ListingStatus): string {
  if (status === 'active') {
    return 'status-badge status-active'
  }
  if (status === 'pending_review') {
    return 'status-badge status-pending'
  }
  if (status === 'rejected' || status === 'suspended') {
    return 'status-badge status-danger'
  }
  if (status === 'archived') {
    return 'status-badge status-muted'
  }
  return 'status-badge status-neutral'
}
