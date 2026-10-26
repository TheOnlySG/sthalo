"""Add parking listings, photos, moderation, audit, and reservation schema.

Revision ID: 20261026_0003
Revises: 20261026_0002
Create Date: 2026-10-26 15:30:37+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261026_0003"
down_revision: str | None = "20261026_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sthalo.listings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id uuid NOT NULL REFERENCES sthalo.users(id) ON DELETE CASCADE,
            kind text NOT NULL DEFAULT 'parking',
            title text NOT NULL,
            description text NOT NULL,
            location extensions.geography(Point, 4326) NOT NULL,
            public_location extensions.geography(Point, 4326) NOT NULL,
            address_line text NOT NULL,
            locality text NOT NULL,
            city text NOT NULL,
            state text NOT NULL,
            pincode text NOT NULL,
            status text NOT NULL DEFAULT 'draft',
            verification_status text NOT NULL DEFAULT 'unverified',
            timezone text NOT NULL DEFAULT 'Asia/Kolkata',
            submitted_at timestamptz,
            approved_at timestamptz,
            rejected_at timestamptz,
            paused_at timestamptz,
            archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_listings_kind CHECK (kind = 'parking'),
            CONSTRAINT ck_listings_title_length
                CHECK (char_length(title) BETWEEN 5 AND 80),
            CONSTRAINT ck_listings_description_length
                CHECK (char_length(description) <= 2000),
            CONSTRAINT ck_listings_address_length
                CHECK (char_length(address_line) BETWEEN 3 AND 240),
            CONSTRAINT ck_listings_locality_length
                CHECK (char_length(locality) BETWEEN 2 AND 120),
            CONSTRAINT ck_listings_city_length
                CHECK (char_length(city) BETWEEN 2 AND 120),
            CONSTRAINT ck_listings_state_length
                CHECK (char_length(state) BETWEEN 2 AND 120),
            CONSTRAINT ck_listings_pincode CHECK (pincode ~ '^[0-9]{6}$'),
            CONSTRAINT ck_listings_status CHECK (
                status IN (
                    'draft', 'pending_review', 'active', 'rejected',
                    'paused', 'suspended', 'archived'
                )
            ),
            CONSTRAINT ck_listings_verification_status
                CHECK (verification_status IN ('unverified')),
            CONSTRAINT ck_listings_timezone CHECK (timezone = 'Asia/Kolkata')
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_listings_owner_created ON sthalo.listings (owner_id, created_at DESC)"
    )
    op.execute("CREATE INDEX ix_listings_status_kind ON sthalo.listings (status, kind)")
    op.execute("CREATE INDEX ix_listings_location_gist ON sthalo.listings USING gist (location)")
    op.execute(
        "CREATE INDEX ix_listings_public_location_gist "
        "ON sthalo.listings USING gist (public_location)"
    )
    op.execute(
        """
        CREATE TRIGGER trg_listings_updated_at
        BEFORE UPDATE ON sthalo.listings
        FOR EACH ROW EXECUTE FUNCTION sthalo.set_updated_at()
        """
    )

    op.execute(
        """
        CREATE TABLE sthalo.parking_listings (
            listing_id uuid PRIMARY KEY
                REFERENCES sthalo.listings(id) ON DELETE CASCADE,
            parking_type text NOT NULL,
            supported_vehicle_types text[] NOT NULL,
            max_length_mm integer,
            max_width_mm integer,
            max_height_mm integer,
            is_covered boolean NOT NULL DEFAULT false,
            access_method text NOT NULL,
            access_instructions text,
            amenities text[] NOT NULL DEFAULT '{}'::text[],
            restrictions text NOT NULL DEFAULT '',
            pricing_model text NOT NULL,
            price_hourly_paise bigint,
            price_daily_cap_paise bigint,
            min_booking_minutes integer NOT NULL DEFAULT 30,
            max_booking_minutes integer NOT NULL DEFAULT 1440,
            advance_booking_max_days integer NOT NULL DEFAULT 30,
            CONSTRAINT ck_parking_listings_type CHECK (
                parking_type IN (
                    'driveway', 'garage', 'society_slot', 'open_lot',
                    'basement', 'shop_frontage', 'other'
                )
            ),
            CONSTRAINT ck_parking_listings_supported_types CHECK (
                array_length(supported_vehicle_types, 1) >= 1
                AND supported_vehicle_types <@ ARRAY[
                    'two_wheeler', 'hatchback', 'sedan', 'suv', 'large'
                ]::text[]
            ),
            CONSTRAINT ck_parking_listings_max_length
                CHECK (max_length_mm IS NULL OR max_length_mm > 0),
            CONSTRAINT ck_parking_listings_max_width
                CHECK (max_width_mm IS NULL OR max_width_mm > 0),
            CONSTRAINT ck_parking_listings_max_height
                CHECK (max_height_mm IS NULL OR max_height_mm > 0),
            CONSTRAINT ck_parking_listings_access_method CHECK (
                access_method IN (
                    'open', 'guard_checkin', 'code', 'key_handover', 'remote_owner'
                )
            ),
            CONSTRAINT ck_parking_listings_access_instructions
                CHECK (
                    access_instructions IS NULL
                    OR char_length(access_instructions) <= 1000
                ),
            CONSTRAINT ck_parking_listings_amenities
                CHECK (cardinality(amenities) <= 20),
            CONSTRAINT ck_parking_listings_restrictions
                CHECK (char_length(restrictions) <= 1000),
            CONSTRAINT ck_parking_listings_pricing_model CHECK (
                pricing_model IN ('hourly', 'hourly_with_daily_cap', 'flat_daily')
            ),
            CONSTRAINT ck_parking_listings_hourly_price
                CHECK (price_hourly_paise IS NULL OR price_hourly_paise >= 0),
            CONSTRAINT ck_parking_listings_daily_price
                CHECK (price_daily_cap_paise IS NULL OR price_daily_cap_paise >= 0),
            CONSTRAINT ck_parking_listings_pricing_shape CHECK (
                (
                    pricing_model = 'hourly'
                    AND price_hourly_paise IS NOT NULL
                    AND price_daily_cap_paise IS NULL
                )
                OR (
                    pricing_model = 'hourly_with_daily_cap'
                    AND price_hourly_paise IS NOT NULL
                    AND price_daily_cap_paise IS NOT NULL
                    AND price_daily_cap_paise >= price_hourly_paise
                )
                OR (
                    pricing_model = 'flat_daily'
                    AND price_hourly_paise IS NULL
                    AND price_daily_cap_paise IS NOT NULL
                )
            ),
            CONSTRAINT ck_parking_listings_min_booking
                CHECK (min_booking_minutes >= 30),
            CONSTRAINT ck_parking_listings_max_booking
                CHECK (
                    max_booking_minutes >= min_booking_minutes
                    AND max_booking_minutes <= 10080
                ),
            CONSTRAINT ck_parking_listings_advance_days
                CHECK (advance_booking_max_days BETWEEN 1 AND 90)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE sthalo.resources (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            listing_id uuid NOT NULL
                REFERENCES sthalo.listings(id) ON DELETE CASCADE,
            label text NOT NULL DEFAULT 'Main bay',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_resources_label CHECK (char_length(label) BETWEEN 1 AND 80)
        )
        """
    )
    op.execute("CREATE INDEX ix_resources_listing_id ON sthalo.resources (listing_id)")
    op.execute(
        "CREATE UNIQUE INDEX ux_resources_listing_main_bay "
        "ON sthalo.resources (listing_id) WHERE label = 'Main bay'"
    )

    op.execute(
        """
        CREATE TABLE sthalo.listing_photos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            listing_id uuid NOT NULL
                REFERENCES sthalo.listings(id) ON DELETE CASCADE,
            storage_key text NOT NULL UNIQUE,
            mime_type text NOT NULL,
            size_bytes integer NOT NULL,
            width integer NOT NULL,
            height integer NOT NULL,
            position smallint NOT NULL,
            is_cover boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_listing_photos_mime_type
                CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),
            CONSTRAINT ck_listing_photos_size
                CHECK (size_bytes > 0 AND size_bytes <= 5242880),
            CONSTRAINT ck_listing_photos_dimensions
                CHECK (width > 0 AND height > 0),
            CONSTRAINT ck_listing_photos_position
                CHECK (position BETWEEN 0 AND 7),
            CONSTRAINT uq_listing_photos_position
                UNIQUE (listing_id, position)
                DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_listing_photos_listing_position "
        "ON sthalo.listing_photos (listing_id, position)"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_listing_photos_listing_cover "
        "ON sthalo.listing_photos (listing_id) WHERE is_cover"
    )

    op.execute(
        """
        CREATE TABLE sthalo.reservations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            reference text NOT NULL UNIQUE,
            customer_id uuid NOT NULL
                REFERENCES sthalo.users(id) ON DELETE CASCADE,
            owner_id uuid NOT NULL
                REFERENCES sthalo.users(id) ON DELETE CASCADE,
            listing_id uuid NOT NULL
                REFERENCES sthalo.listings(id) ON DELETE CASCADE,
            resource_id uuid NOT NULL
                REFERENCES sthalo.resources(id) ON DELETE CASCADE,
            vehicle_id uuid NOT NULL
                REFERENCES sthalo.vehicles(id) ON DELETE CASCADE,
            time_range tstzrange NOT NULL,
            status text NOT NULL,
            hold_expires_at timestamptz,
            currency text NOT NULL DEFAULT 'INR',
            base_amount_paise bigint NOT NULL,
            total_paise bigint NOT NULL,
            price_snapshot jsonb NOT NULL,
            policy_version text NOT NULL DEFAULT 'phase1-demo-v1',
            cancelled_by uuid REFERENCES sthalo.users(id) ON DELETE SET NULL,
            cancel_reason text,
            confirmed_at timestamptz,
            started_at timestamptz,
            completed_at timestamptz,
            cancelled_at timestamptz,
            expired_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_reservations_status CHECK (
                status IN (
                    'pending_confirmation', 'confirmed', 'active',
                    'completed', 'cancelled', 'expired'
                )
            ),
            CONSTRAINT ck_reservations_time_range
                CHECK (lower(time_range) < upper(time_range)),
            CONSTRAINT ck_reservations_hold_expiry CHECK (
                status <> 'pending_confirmation' OR hold_expires_at IS NOT NULL
            ),
            CONSTRAINT ck_reservations_currency CHECK (currency = 'INR'),
            CONSTRAINT ck_reservations_amounts CHECK (
                base_amount_paise >= 0 AND total_paise >= 0
            ),
            CONSTRAINT ck_reservations_cancel_reason
                CHECK (cancel_reason IS NULL OR char_length(cancel_reason) <= 500)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE sthalo.reservations
        ADD CONSTRAINT reservations_no_overlap
        EXCLUDE USING gist (
            resource_id WITH =,
            time_range WITH &&
        ) WHERE (status IN ('pending_confirmation', 'confirmed', 'active'))
        """
    )
    op.execute(
        "CREATE INDEX ix_reservations_hold_expiry "
        "ON sthalo.reservations (hold_expires_at) "
        "WHERE status = 'pending_confirmation'"
    )
    op.execute(
        "CREATE INDEX ix_reservations_customer_created "
        "ON sthalo.reservations (customer_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_reservations_owner_created "
        "ON sthalo.reservations (owner_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_reservations_listing_status ON sthalo.reservations (listing_id, status)"
    )
    op.execute(
        "CREATE INDEX ix_reservations_resource_status ON sthalo.reservations (resource_id, status)"
    )
    op.execute(
        "CREATE INDEX ix_reservations_status_start "
        "ON sthalo.reservations (status, lower(time_range))"
    )
    op.execute(
        """
        CREATE TRIGGER trg_reservations_updated_at
        BEFORE UPDATE ON sthalo.reservations
        FOR EACH ROW EXECUTE FUNCTION sthalo.set_updated_at()
        """
    )

    op.execute(
        """
        CREATE TABLE sthalo.audit_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id uuid REFERENCES sthalo.users(id) ON DELETE SET NULL,
            actor_type text NOT NULL,
            action text NOT NULL,
            entity_type text NOT NULL,
            entity_id uuid,
            before jsonb,
            after jsonb,
            ip inet,
            request_id text,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_audit_events_actor_type
                CHECK (actor_type IN ('user', 'admin', 'system')),
            CONSTRAINT ck_audit_events_action CHECK (char_length(action) <= 80),
            CONSTRAINT ck_audit_events_entity_type
                CHECK (char_length(entity_type) <= 80),
            CONSTRAINT ck_audit_events_request_id
                CHECK (request_id IS NULL OR char_length(request_id) <= 128)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_events_entity ON sthalo.audit_events (entity_type, entity_id)"
    )
    op.execute("CREATE INDEX ix_audit_events_actor ON sthalo.audit_events (actor_id)")
    op.execute("CREATE INDEX ix_audit_events_created ON sthalo.audit_events (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sthalo.audit_events")
    op.execute("DROP TABLE IF EXISTS sthalo.reservations")
    op.execute("DROP TABLE IF EXISTS sthalo.listing_photos")
    op.execute("DROP TABLE IF EXISTS sthalo.resources")
    op.execute("DROP TABLE IF EXISTS sthalo.parking_listings")
    op.execute("DROP TABLE IF EXISTS sthalo.listings")
