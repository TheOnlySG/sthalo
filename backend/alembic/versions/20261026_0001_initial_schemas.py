"""Create the application schema and required PostgreSQL extensions.

Revision ID: 20261026_0001
Revises:
Create Date: 2026-10-26 00:00:00+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS sthalo")
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute(
        """
        DO $$
        DECLARE
            extension_name text;
            extension_schema text;
        BEGIN
            FOR extension_name, extension_schema IN
                SELECT e.extname, n.nspname
                FROM pg_extension AS e
                JOIN pg_namespace AS n ON n.oid = e.extnamespace
                WHERE e.extname IN ('postgis', 'btree_gist', 'pgcrypto')
            LOOP
                IF extension_schema <> 'extensions' THEN
                    RAISE EXCEPTION
                        'extension % is in schema %, expected extensions',
                        extension_name, extension_schema;
                END IF;
            END LOOP;
        END
        $$;
        """
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions")


def downgrade() -> None:
    # Extensions and schemas can be shared with Supabase-managed services.
    # Dropping them would be destructive, so the baseline downgrade is a no-op.
    pass
