import { reservationStatusLabel, reservationStatusTone } from '../lib/reservationFormat'
import type { ReservationStatus } from '../types'

export function ReservationStatusBadge({ status }: { status: ReservationStatus }) {
  return (
    <span className={`status-badge status-${reservationStatusTone(status)}`}>
      {reservationStatusLabel(status)}
    </span>
  )
}
