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
