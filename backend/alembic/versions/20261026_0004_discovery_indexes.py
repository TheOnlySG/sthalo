"""Add discovery indexes for active public-location search.

Revision ID: 20261026_0004
Revises: 20261026_0003
Create Date: 2026-10-26 16:20:00+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0004"
down_revision: str | None = "20261026_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_listings_active_public_location_gist "
        "ON sthalo.listings USING gist (public_location) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX ix_parking_listings_supported_vehicle_types_gin "
        "ON sthalo.parking_listings USING gin (supported_vehicle_types)"
    )
    op.execute(
        "CREATE INDEX ix_parking_listings_effective_price "
        "ON sthalo.parking_listings "
        "((COALESCE(price_hourly_paise, price_daily_cap_paise)))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sthalo.ix_parking_listings_effective_price")
    op.execute("DROP INDEX IF EXISTS sthalo.ix_parking_listings_supported_vehicle_types_gin")
    op.execute("DROP INDEX IF EXISTS sthalo.ix_listings_active_public_location_gist")
