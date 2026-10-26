import { supabase } from './supabase'
import { API_BASE_URL } from './env'
import type {
  AdminListing,
  ListingBasicsInput,
  ListingCreateInput,
  ListingPhoto,
  ListingStatus,
  OwnerListing,
  OwnerListingSummary,
  ParkingInput,
  ParkingSearchRequest,
  ParkingSearchResponse,
  PublicListing,
  UserProfile,
  Vehicle,
  VehicleInput,
} from '../types'

interface ApiErrorPayload {
  error: {
    code: string
    message: string
    details: Array<Record<string, unknown>>
    request_id: string
  }
}

export class ApiRequestError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Array<Record<string, unknown>>
  readonly requestId: string | null

  constructor(
    message: string,
    options: {
      code?: string
      status?: number
      details?: Array<Record<string, unknown>>
      requestId?: string | null
    } = {},
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = options.code ?? 'REQUEST_FAILED'
    this.status = options.status ?? 0
    this.details = options.details ?? []
    this.requestId = options.requestId ?? null
  }
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false
  }
  const error = (value as { error?: unknown }).error
  if (typeof error !== 'object' || error === null) {
    return false
  }
  const candidate = error as Record<string, unknown>
  return typeof candidate.code === 'string' && typeof candidate.message === 'string'
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
}

async function request<T>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const headers = new Headers({ Accept: 'application/json' })
  const isFormData = options.body instanceof FormData
  if (options.body !== undefined && !isFormData) {
    headers.set('Content-Type', 'application/json')
  }
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  })

  if (response.status === 401 && retry) {
    const { data: refreshed, error } = await supabase.auth.refreshSession()
    if (!error && refreshed.session) {
      return request<T>(path, options, false)
    }
  }

  if (response.status === 204) {
    return undefined as T
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isApiErrorPayload(payload)) {
      throw new ApiRequestError(payload.error.message, {
        code: payload.error.code,
        status: response.status,
        details: payload.error.details,
        requestId: payload.error.request_id,
      })
    }
    throw new ApiRequestError(`Request failed with status ${response.status}`, {
      status: response.status,
    })
  }

  return payload as T
}

export function getMe(): Promise<UserProfile> {
  return request<UserProfile>('/users/me')
}

export function updateMe(values: {
  full_name?: string
  phone?: string | null
}): Promise<UserProfile> {
  return request<UserProfile>('/users/me', { method: 'PATCH', body: values })
}

export function acceptOwnerTerms(): Promise<UserProfile> {
  return request<UserProfile>('/users/me/accept-owner-terms', { method: 'POST' })
}

export function listVehicles(): Promise<Vehicle[]> {
  return request<Vehicle[]>('/vehicles')
}

export function createVehicle(values: VehicleInput): Promise<Vehicle> {
  return request<Vehicle>('/vehicles', { method: 'POST', body: values })
}

export function updateVehicle(id: string, values: Partial<VehicleInput>): Promise<Vehicle> {
  return request<Vehicle>(`/vehicles/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: values,
  })
}

export function deleteVehicle(id: string): Promise<void> {
  return request<void>(`/vehicles/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function listOwnerListings(): Promise<OwnerListingSummary[]> {
  return request<OwnerListingSummary[]>('/owner/parking-listings')
}

export function createListing(values: ListingCreateInput): Promise<OwnerListing> {
  return request<OwnerListing>('/owner/parking-listings', { method: 'POST', body: values })
}

export function getOwnerListing(id: string): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}`)
}

export function updateListing(
  id: string,
  values: Partial<ListingBasicsInput> & { parking?: ParkingInput },
): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: values,
  })
}

export function submitListing(id: string, declarationAccepted: boolean): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}/submit`, {
    method: 'POST',
    body: { declaration_accepted: declarationAccepted },
  })
}

export function pauseListing(id: string): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}/pause`, {
    method: 'POST',
  })
}

export function resumeListing(id: string): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}/resume`, {
    method: 'POST',
  })
}

export function archiveListing(id: string): Promise<OwnerListing> {
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}/archive`, {
    method: 'POST',
  })
}

export function uploadListingPhoto(id: string, file: File): Promise<OwnerListing> {
  const body = new FormData()
  body.append('file', file)
  return request<OwnerListing>(`/owner/parking-listings/${encodeURIComponent(id)}/photos`, {
    method: 'POST',
    body,
  })
}

export function updateListingPhoto(
  listingId: string,
  photoId: string,
  values: Partial<Pick<ListingPhoto, 'position' | 'is_cover'>>,
): Promise<OwnerListing> {
  return request<OwnerListing>(
    `/owner/parking-listings/${encodeURIComponent(listingId)}/photos/${encodeURIComponent(photoId)}`,
    { method: 'PATCH', body: values },
  )
}

export function deleteListingPhoto(listingId: string, photoId: string): Promise<void> {
  return request<void>(
    `/owner/parking-listings/${encodeURIComponent(listingId)}/photos/${encodeURIComponent(photoId)}`,
    { method: 'DELETE' },
  )
}

export function getPublicListing(id: string): Promise<PublicListing> {
  return request<PublicListing>(`/parking-listings/${encodeURIComponent(id)}`)
}

export function searchParking(params: ParkingSearchRequest): Promise<ParkingSearchResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  }
  return request<ParkingSearchResponse>(`/search/parking?${query.toString()}`)
}

export function listAdminListings(status?: ListingStatus): Promise<AdminListing[]> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : ''
  return request<AdminListing[]>(`/admin/listings${suffix}`)
}

function moderateListing(
  id: string,
  action: 'approve' | 'reject' | 'suspend' | 'restore',
  note: string | null,
): Promise<AdminListing> {
  return request<AdminListing>(`/admin/listings/${encodeURIComponent(id)}/${action}`, {
    method: 'POST',
    body: { note },
  })
}

export function approveListing(id: string, note: string | null): Promise<AdminListing> {
  return moderateListing(id, 'approve', note)
}

export function rejectListing(id: string, note: string): Promise<AdminListing> {
  return moderateListing(id, 'reject', note)
}

export function suspendListing(id: string, note: string): Promise<AdminListing> {
  return moderateListing(id, 'suspend', note)
}

export function restoreListing(id: string, note: string): Promise<AdminListing> {
  return moderateListing(id, 'restore', note)
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Something went wrong. Please try again.'
}
