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
