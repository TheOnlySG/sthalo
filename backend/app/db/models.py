"""Import all ORM models so Alembic and application code share one metadata."""

from app.modules.identity.models import User
from app.modules.profiles.models import Vehicle

__all__ = ["User", "Vehicle"]
