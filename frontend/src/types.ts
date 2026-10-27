export type UserStatus = 'active' | 'suspended'

export type VehicleType = 'two_wheeler' | 'hatchback' | 'sedan' | 'suv' | 'large'

export interface UserProfile {
  id: string
  email: string
  full_name: string
  phone: string | null
  is_admin: boolean
  status: UserStatus
  owner_terms_version: string | null
  owner_terms_accepted_at: string | null
  created_at: string
  updated_at: string
}

export interface Vehicle {
  id: string
  vehicle_type: VehicleType
  registration_no: string | null
  length_mm: number | null
  width_mm: number | null
  height_mm: number | null
  is_ev: boolean
  created_at: string
  updated_at: string
}

export interface VehicleInput {
  vehicle_type: VehicleType
  registration_no?: string | null
  length_mm?: number | null
  width_mm?: number | null
  height_mm?: number | null
  is_ev: boolean
}

export const VEHICLE_TYPES: ReadonlyArray<{ value: VehicleType; label: string }> = [
  { value: 'two_wheeler', label: 'Two wheeler' },
  { value: 'hatchback', label: 'Hatchback' },
  { value: 'sedan', label: 'Sedan' },
  { value: 'suv', label: 'SUV' },
  { value: 'large', label: 'Large vehicle' },
]

export const VEHICLE_LABELS: Record<VehicleType, string> = {
  two_wheeler: 'Two wheeler',
  hatchback: 'Hatchback',
  sedan: 'Sedan',
  suv: 'SUV',
  large: 'Large vehicle',
}

export type ListingStatus =
  'draft' | 'pending_review' | 'active' | 'rejected' | 'paused' | 'suspended' | 'archived'

export type ParkingType =
  'driveway' | 'garage' | 'society_slot' | 'open_lot' | 'basement' | 'shop_frontage' | 'other'

export type AccessMethod = 'open' | 'guard_checkin' | 'code' | 'key_handover' | 'remote_owner'

export type PricingModel = 'hourly' | 'hourly_with_daily_cap' | 'flat_daily'

export interface ListingPhoto {
  id: string
  url: string
  width: number
  height: number
  position: number
  is_cover: boolean
  mime_type: string
}

export interface ParkingPublic {
  parking_type: ParkingType
  supported_vehicle_types: VehicleType[]
  max_length_mm: number | null
  max_width_mm: number | null
  max_height_mm: number | null
  is_covered: boolean
  access_method: AccessMethod
  amenities: string[]
  restrictions: string
  pricing_model: PricingModel
  price_hourly_paise: number | null
  price_daily_cap_paise: number | null
  min_booking_minutes: number
  max_booking_minutes: number
  advance_booking_max_days: number
}

export interface ParkingOwner extends ParkingPublic {
  access_instructions: string | null
}

export interface OwnerListingSummary {
  id: string
  title: string
  status: ListingStatus
  city: string
  locality: string
  cover_url: string | null
  photo_count: number
  updated_at: string
  moderation_note: string | null
}

export interface OwnerListing {
  id: string
  title: string
  description: string
  status: ListingStatus
  latitude: number
  longitude: number
  address_line: string
  locality: string
  city: string
  state: string
  pincode: string
  parking: ParkingOwner
  photos: ListingPhoto[]
  moderation_note: string | null
  submitted_at: string | null
  approved_at: string | null
  rejected_at: string | null
  paused_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface PublicListing {
  id: string
  title: string
  description: string
  latitude: number
  longitude: number
  locality: string
  city: string
  state: string
  parking: ParkingPublic
  photos: ListingPhoto[]
  updated_at: string
}

export interface AdminOwner {
  id: string
  email: string
  full_name: string
}

export interface AdminListing extends OwnerListing {
  owner: AdminOwner
}

export interface ListingBasicsInput {
  title: string
  description: string
  latitude: number
  longitude: number
  address_line: string
  locality: string
  city: string
  state: string
  pincode: string
}

export interface ParkingInput {
  parking_type: ParkingType
  supported_vehicle_types: VehicleType[]
  max_length_mm: number | null
  max_width_mm: number | null
  max_height_mm: number | null
  is_covered: boolean
  access_method: AccessMethod
  access_instructions: string | null
  amenities: string[]
  restrictions: string
  pricing_model: PricingModel
  price_hourly_paise: number | null
  price_daily_cap_paise: number | null
  min_booking_minutes: number
  max_booking_minutes: number
  advance_booking_max_days: number
}

export type ListingCreateInput = ListingBasicsInput & {
  owner_terms_accepted: boolean
  parking: ParkingInput
}

export type SearchSort = 'distance' | 'price'
export type SearchMode = 'radius' | 'bbox'

export interface ParkingSearchItem {
  id: string
  title: string
  description: string
  latitude: number
  longitude: number
  locality: string
  city: string
  state: string
  parking: ParkingPublic
  cover_url: string | null
  distance_m: number
  updated_at: string
}

export interface ParkingSearchResponse {
  items: ParkingSearchItem[]
  next_cursor: string | null
  mode: SearchMode
  center_latitude: number
  center_longitude: number
  radius_m: number | null
  bbox: number[] | null
  sort: SearchSort
}

export interface ParkingSearchRequest {
  lat?: number
  lng?: number
  radius_m?: number
  bbox?: string
  vehicle_type?: VehicleType
  max_price_paise?: number
  covered?: boolean
  sort: SearchSort
  limit: number
  cursor?: string
  start?: string
  end?: string
}

export interface AvailabilityRule {
  id: string
  weekday: number
  start_time: string
  end_time: string
  valid_from: string | null
  valid_to: string | null
}

export interface AvailabilityRuleInput {
  weekday: number
  start_time: string
  end_time: string
  valid_from: string | null
  valid_to: string | null
}

export interface BlockedInterval {
  id: string
  start: string
  end: string
  reason: string | null
  created_at: string
}

export interface AvailabilityWindow {
  start: string
  end: string
}

export interface AvailabilityResponse {
  listing_id: string
  timezone: string
  from: string
  to: string
  windows: AvailabilityWindow[]
}

export type ReservationStatus =
  'pending_confirmation' | 'confirmed' | 'active' | 'completed' | 'cancelled' | 'expired'

export type ReservationViewerRole = 'customer' | 'owner' | 'admin'

export interface ReservationListing {
  id: string
  title: string
  locality: string
  city: string
  latitude: number
  longitude: number
}

export interface ReservationVehicle {
  id: string
  vehicle_type: VehicleType
  registration_no: string | null
  length_mm: number | null
  width_mm: number | null
  height_mm: number | null
  is_ev: boolean
}

export interface PriceBreakdown {
  pricing_model: PricingModel
  duration_minutes: number
  billable_minutes: number
  chargeable_days: number
  hourly_rate_paise: number | null
  daily_cap_paise: number | null
  hourly_component_paise: number
  cap_component_paise: number
  total_paise: number
  calculation: string
}

export interface ReservationQuote {
  listing_id: string
  start: string
  end: string
  currency: 'INR'
  base_amount_paise: number
  total_paise: number
  price: PriceBreakdown
}

export interface Reservation {
  id: string
  reference: string
  status: ReservationStatus
  viewer_role: ReservationViewerRole
  listing: ReservationListing
  vehicle: ReservationVehicle
  customer_name: string | null
  owner_name: string
  start: string
  end: string
  hold_expires_at: string | null
  currency: 'INR'
  base_amount_paise: number
  total_paise: number
  price_snapshot: Record<string, unknown>
  can_confirm: boolean
  can_cancel: boolean
  exact_address: string | null
  pincode: string | null
  exact_latitude: number | null
  exact_longitude: number | null
  access_instructions: string | null
  cancel_reason: string | null
  confirmed_at: string | null
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  expired_at: string | null
  created_at: string
}

export interface ReservationWindowInput {
  listing_id: string
  vehicle_id: string
  start: string
  end: string
}

export const RESERVATION_STATUS_LABELS: Record<ReservationStatus, string> = {
  pending_confirmation: 'Awaiting confirmation',
  confirmed: 'Confirmed',
  active: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
  expired: 'Expired',
}

export const RESERVATION_STATUS_OPTIONS: ReadonlyArray<{
  value: ReservationStatus
  label: string
}> = [
  { value: 'pending_confirmation', label: 'Awaiting confirmation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'active', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'expired', label: 'Expired' },
]

export interface AdminOverview {
  pending_listings: number
  live_reservations: number
  expiring_holds: number
}

export interface AuditEvent {
  id: string
  actor_id: string | null
  actor_type: 'user' | 'admin' | 'system'
  actor_name: string | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  request_id: string | null
  created_at: string
}

export interface AdminReservationDetail {
  reservation: Reservation
  audit: AuditEvent[]
}
