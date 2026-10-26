const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '')

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000/api/v1',
)

export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL?.trim() || 'http://127.0.0.1:54321'

export const SUPABASE_ANON_KEY =
  import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || 'local-anon-key-placeholder'
