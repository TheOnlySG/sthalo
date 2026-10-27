import { describe, expect, it } from 'vitest'
import {
  countdownLabel,
  formatMoney,
  isReservationToday,
  reservationStatusLabel,
  reservationStatusTone,
  roundToNextQuarter,
} from '../lib/reservationFormat'

describe('reservation formatting helpers', () => {
  it('formats paise as rupees', () => {
    expect(formatMoney(12345)).toContain('123.45')
  })

  it('rounds timestamps up to a quarter-hour boundary', () => {
    const rounded = roundToNextQuarter(new Date('2026-10-26T10:01:20'))
    expect(rounded.getMinutes()).toBe(15)
    expect(rounded.getSeconds()).toBe(0)
  })

  it('renders a countdown and treats elapsed holds as expired', () => {
    const now = Date.parse('2026-10-26T10:00:00Z')
    expect(countdownLabel('2026-10-26T10:02:05Z', now)).toBe('2:05 remaining')
    expect(countdownLabel('2026-10-26T09:59:00Z', now)).toBe('Expired')
    expect(countdownLabel(null, now)).toBe('')
  })

  it('keeps customer-facing status labels and tones stable', () => {
    expect(reservationStatusLabel('pending_confirmation')).toBe('Awaiting confirmation')
    expect(reservationStatusTone('confirmed')).toBe('active')
    expect(reservationStatusTone('expired')).toBe('danger')
    expect(reservationStatusTone('completed')).toBe('muted')
  })

  it('detects reservations that start today', () => {
    const now = new Date('2026-10-26T12:00:00')
    expect(isReservationToday('2026-10-26T18:00:00', now)).toBe(true)
    expect(isReservationToday('2026-10-27T09:00:00', now)).toBe(false)
  })
})
