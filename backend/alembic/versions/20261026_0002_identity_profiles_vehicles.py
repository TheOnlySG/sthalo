"""Create local user profiles, auth provisioning, and vehicles.

Revision ID: 20261026_0002
Revises: 20261026_0001
Create Date: 2026-10-26 00:00:00+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0002"
down_revision: str | None = "20261026_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('auth.users') IS NULL THEN
                RAISE EXCEPTION
                    'auth.users is missing; use Supabase or create the auth schema for tests';
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE TABLE sthalo.users (
            id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            email text NOT NULL,
            full_name text NOT NULL,
            phone text,
            is_admin boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'active',
            owner_terms_version text,
            owner_terms_accepted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_users_full_name_length
                CHECK (char_length(full_name) BETWEEN 2 AND 120),
            CONSTRAINT ck_users_status CHECK (status IN ('active', 'suspended')),
            CONSTRAINT ck_users_owner_terms_pair
                CHECK ((owner_terms_version IS NULL) = (owner_terms_accepted_at IS NULL))
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ux_users_email_lower ON sthalo.users (lower(email))")

    op.execute(
        """
        CREATE TABLE sthalo.vehicles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES sthalo.users(id) ON DELETE CASCADE,
            vehicle_type text NOT NULL,
            registration_no text,
            length_mm integer,
            width_mm integer,
            height_mm integer,
            is_ev boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_vehicles_vehicle_type CHECK (
                vehicle_type IN ('two_wheeler', 'hatchback', 'sedan', 'suv', 'large')
            ),
            CONSTRAINT ck_vehicles_length_positive
                CHECK (length_mm IS NULL OR length_mm > 0),
            CONSTRAINT ck_vehicles_width_positive
                CHECK (width_mm IS NULL OR width_mm > 0),
            CONSTRAINT ck_vehicles_height_positive
                CHECK (height_mm IS NULL OR height_mm > 0)
        )
        """
    )
    op.execute("CREATE INDEX ix_vehicles_user_id ON sthalo.vehicles (user_id)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION sthalo.set_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, sthalo
        AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON sthalo.users
        FOR EACH ROW EXECUTE FUNCTION sthalo.set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_vehicles_updated_at
        BEFORE UPDATE ON sthalo.vehicles
        FOR EACH ROW EXECUTE FUNCTION sthalo.set_updated_at()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION sthalo.handle_new_auth_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, sthalo
        AS $$
        DECLARE
            normalized_email text;
            display_name text;
        BEGIN
            normalized_email := lower(
                coalesce(
                    nullif(btrim(NEW.email), ''),
                    NEW.id::text || '@invalid.local'
                )
            );
            display_name := coalesce(
                nullif(btrim(NEW.raw_user_meta_data ->> 'full_name'), ''),
                nullif(btrim(NEW.raw_user_meta_data ->> 'name'), ''),
                nullif(split_part(normalized_email, '@', 1), ''),
                'Sthalo user'
            );
            display_name := left(display_name, 120);
            IF char_length(display_name) < 2 THEN
                display_name := 'Sthalo user';
            END IF;

            INSERT INTO sthalo.users (id, email, full_name)
            VALUES (NEW.id, normalized_email, display_name)
            ON CONFLICT (id) DO NOTHING;

            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        INSERT INTO sthalo.users (id, email, full_name)
        SELECT
            u.id,
            lower(coalesce(nullif(btrim(u.email), ''), u.id::text || '@invalid.local')),
            CASE
                WHEN char_length(
                    left(
                        coalesce(
                            nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
                            nullif(btrim(u.raw_user_meta_data ->> 'name'), ''),
                            nullif(split_part(coalesce(u.email, ''), '@', 1), ''),
                            'Sthalo user'
                        ),
                        120
                    )
                ) < 2
                THEN 'Sthalo user'
                ELSE left(
                    coalesce(
                        nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
                        nullif(btrim(u.raw_user_meta_data ->> 'name'), ''),
                        nullif(split_part(coalesce(u.email, ''), '@', 1), ''),
                        'Sthalo user'
                    ),
                    120
                )
            END
        FROM auth.users AS u
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_auth_users_create_profile
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION sthalo.handle_new_auth_user()
        """
    )
    op.execute("REVOKE ALL ON FUNCTION sthalo.handle_new_auth_user() FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
                GRANT EXECUTE ON FUNCTION sthalo.handle_new_auth_user()
                    TO supabase_auth_admin;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_auth_users_create_profile ON auth.users")
    op.execute("DROP FUNCTION IF EXISTS sthalo.handle_new_auth_user()")
    op.execute("DROP TABLE IF EXISTS sthalo.vehicles")
    op.execute("DROP TABLE IF EXISTS sthalo.users")
    op.execute("DROP FUNCTION IF EXISTS sthalo.set_updated_at()")
