import { supabase } from './supabase'
import { API_BASE_URL } from './env'
import type { UserProfile, Vehicle, VehicleInput } from '../types'

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
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
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

export function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Something went wrong. Please try again.'
}
