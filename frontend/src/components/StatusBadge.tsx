import type { ListingStatus } from '../types'
import { LISTING_STATUS_LABELS, statusTone } from '../lib/listingFormat'

export function StatusBadge({ status }: { status: ListingStatus }) {
  return <span className={statusTone(status)}>{LISTING_STATUS_LABELS[status]}</span>
}
