"""Import all ORM models so Alembic and application code share one metadata."""

from app.modules.audit.models import AuditEvent
from app.modules.availability.models import AvailabilityRule, BlockedInterval
from app.modules.identity.models import User
from app.modules.listings.models import (
    Listing,
    ListingPhoto,
    ParkingListing,
    Reservation,
    Resource,
)
from app.modules.profiles.models import Vehicle

__all__ = [
    "AuditEvent",
    "AvailabilityRule",
    "BlockedInterval",
    "Listing",
    "ListingPhoto",
    "ParkingListing",
    "Reservation",
    "Resource",
    "User",
    "Vehicle",
]
