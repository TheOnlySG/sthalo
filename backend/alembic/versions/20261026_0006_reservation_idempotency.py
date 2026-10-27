"""Add reservation idempotency keys and lifecycle sweep indexes.

Revision ID: 20261026_0006
Revises: 20261026_0005
Create Date: 2026-10-26 21:00:00+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0006"
down_revision: str | None = "20261026_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sthalo.idempotency_keys (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL
                REFERENCES sthalo.users(id) ON DELETE CASCADE,
            key varchar(128) NOT NULL,
            request_hash varchar(64) NOT NULL,
            response_status smallint,
            response_body jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            CONSTRAINT ck_idempotency_key_length
                CHECK (char_length(key) BETWEEN 1 AND 128),
            CONSTRAINT ck_idempotency_response_pair
                CHECK (
                    (response_status IS NULL AND response_body IS NULL)
                    OR (response_status IS NOT NULL AND response_body IS NOT NULL)
                ),
            CONSTRAINT uq_idempotency_user_key UNIQUE (user_id, key)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_idempotency_keys_expires_at ON sthalo.idempotency_keys (expires_at)"
    )
    op.execute(
        "CREATE INDEX ix_reservations_status_end ON sthalo.reservations (status, upper(time_range))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sthalo.ix_reservations_status_end")
    op.execute("DROP TABLE IF EXISTS sthalo.idempotency_keys")
