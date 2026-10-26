"""Add owner availability rules and blocked intervals.

Revision ID: 20261026_0005
Revises: 20261026_0004
Create Date: 2026-10-26 18:00:00+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0005"
down_revision: str | None = "20261026_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sthalo.availability_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            listing_id uuid NOT NULL
                REFERENCES sthalo.listings(id) ON DELETE CASCADE,
            weekday smallint NOT NULL,
            start_time time NOT NULL,
            end_time time NOT NULL,
            valid_from date,
            valid_to date,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_availability_rules_weekday
                CHECK (weekday BETWEEN 1 AND 7),
            CONSTRAINT ck_availability_rules_time_order
                CHECK (
                    end_time > start_time
                    OR (
                        end_time = time '00:00'
                        AND start_time <> time '00:00'
                    )
                ),
            CONSTRAINT ck_availability_rules_valid_range
                CHECK (
                    valid_to IS NULL
                    OR valid_from IS NULL
                    OR valid_to >= valid_from
                )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_availability_rules_listing_weekday "
        "ON sthalo.availability_rules (listing_id, weekday)"
    )
    op.execute(
        """
        CREATE TABLE sthalo.blocked_intervals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            resource_id uuid NOT NULL
                REFERENCES sthalo.resources(id) ON DELETE CASCADE,
            time_range tstzrange NOT NULL,
            reason text,
            created_by uuid REFERENCES sthalo.users(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_blocked_intervals_non_empty
                CHECK (NOT isempty(time_range)),
            CONSTRAINT ck_blocked_intervals_time_order
                CHECK (lower(time_range) < upper(time_range)),
            CONSTRAINT ck_blocked_intervals_reason_length
                CHECK (reason IS NULL OR char_length(reason) <= 500),
            CONSTRAINT ex_blocked_intervals_no_overlap
                EXCLUDE USING gist (
                    resource_id WITH =,
                    time_range WITH &&
                )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_blocked_intervals_resource_start "
        "ON sthalo.blocked_intervals (resource_id, lower(time_range))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sthalo.blocked_intervals")
    op.execute("DROP TABLE IF EXISTS sthalo.availability_rules")
