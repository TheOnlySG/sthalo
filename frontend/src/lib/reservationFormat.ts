import { RESERVATION_STATUS_LABELS, type ReservationStatus } from '../types'

export function formatMoney(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(paise / 100)
}

export function formatReservationDate(value: string): string {
  return new Date(value).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function reservationStatusLabel(status: ReservationStatus): string {
  return RESERVATION_STATUS_LABELS[status]
}

export function reservationStatusTone(
  status: ReservationStatus,
): 'active' | 'pending' | 'danger' | 'muted' {
  if (status === 'confirmed' || status === 'active') {
    return 'active'
  }
  if (status === 'pending_confirmation') {
    return 'pending'
  }
  if (status === 'cancelled' || status === 'expired') {
    return 'danger'
  }
  return 'muted'
}

export function roundToNextQuarter(date: Date): Date {
  const rounded = new Date(date)
  rounded.setSeconds(0, 0)
  const remainder = rounded.getMinutes() % 15
  if (remainder !== 0) {
    rounded.setMinutes(rounded.getMinutes() + (15 - remainder))
  }
  return rounded
}

export function defaultBookingWindow(): { start: string; end: string } {
  const start = roundToNextQuarter(new Date(Date.now() + 24 * 60 * 60 * 1000))
  start.setMinutes(0, 0, 0)
  start.setHours(9)
  const end = new Date(start)
  end.setHours(12)
  return {
    start: toDateTimeLocal(start),
    end: toDateTimeLocal(end),
  }
}

export function toDateTimeLocal(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function localInputToIso(value: string): string {
  return new Date(value).toISOString()
}

export function countdownLabel(expiresAt: string | null, now = Date.now()): string {
  if (!expiresAt) {
    return ''
  }
  const remaining = new Date(expiresAt).getTime() - now
  if (remaining <= 0) {
    return 'Expired'
  }
  const totalSeconds = Math.ceil(remaining / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')} remaining`
}

export function isReservationToday(start: string, now = new Date()): boolean {
  const startDate = new Date(start)
  return (
    startDate.getFullYear() === now.getFullYear() &&
    startDate.getMonth() === now.getMonth() &&
    startDate.getDate() === now.getDate()
  )
}
