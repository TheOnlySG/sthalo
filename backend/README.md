# Sthalo Backend

FastAPI + async SQLAlchemy backend for the Sthalo Phase 1 parking MVP.

The repository is being built in vertical slices. This checkpoint contains the
application foundation, V1 identity/profile/owner-terms/vehicle APIs, V2 owner
listings with private photos and admin moderation, and V3 public discovery
search. Supabase Auth owns credentials; FastAPI verifies access tokens through
JWKS and never handles passwords. Availability and booking APIs arrive in later
slices.

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill the local values. Get the
Supabase keys from the repository root:

```bash
npx --yes supabase@2.122.0 status -o env
```

Use `ANON_KEY` / `SERVICE_ROLE_KEY` (legacy JWT) or `PUBLISHABLE_KEY` /
`SECRET_KEY`. Keep `SERVICE_ROLE_KEY` / `SECRET_KEY` server-side only.

Required configuration includes `DATABASE_URL`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWKS_URL`,
`SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, and `CORS_ORIGINS`. Optional
controls include
`DEBUG`, `LOG_LEVEL`, `LOG_JSON`, `SWEEPER_ENABLED`,
`ALLOW_SWEEPER_DISABLED`, `SWEEPER_INTERVAL_SECONDS`, `MAX_UPLOAD_BYTES`, and
`GEOCODE_PROVIDER`.

Staging/production startup rejects debug mode, non-HTTPS Supabase/CORS URLs,
local CORS hosts, placeholder or short Supabase keys, and a disabled sweeper
without the explicit override.

## Local development

Start the local Supabase stack from the repository root:

```bash
npx --yes supabase@2.122.0 start
```

Then:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/setup_local_storage.py
uvicorn app.main:app --reload --port 8000
```

The storage setup script creates the private `listing-photos` bucket. Uploads
are re-encoded with Pillow and served through short-lived signed URLs.

Health endpoints:

- `GET http://127.0.0.1:8000/health/live` — process liveness.
- `GET http://127.0.0.1:8000/health/ready` — database + Alembic readiness (`200` or `503`).
- `GET http://127.0.0.1:8000/docs` — OpenAPI UI.

Readiness checks the database and requires a stamped `sthalo.alembic_version`
row. Run the migrations before starting the API.

## API

All feature routes are under `/api/v1` and require a verified Supabase bearer
token except where noted:

- `GET /users/me`, `PATCH /users/me`
- `POST /users/me/accept-owner-terms`
- `GET /vehicles`, `POST /vehicles`
- `PATCH /vehicles/{vehicle_id}`, `DELETE /vehicles/{vehicle_id}`
- `POST /owner/parking-listings`, `GET /owner/parking-listings`
- `GET/PATCH /owner/parking-listings/{listing_id}`
- `POST /owner/parking-listings/{listing_id}/submit|pause|resume|archive`
- `POST/PATCH/DELETE /owner/parking-listings/{listing_id}/photos[/{photo_id}]`
- `GET /parking-listings/{listing_id}` (public, active listings only)
- `GET /parking-listings/{listing_id}/availability?from=&to=` (public, active
  listings only; 31-day maximum, 15-minute boundaries)
- `GET/PUT /owner/parking-listings/{listing_id}/availability-rules`
- `GET/POST /owner/parking-listings/{listing_id}/blocks`
- `DELETE /owner/parking-listings/{listing_id}/blocks/{block_id}`
- `GET /search/parking?lat=&lng=&radius_m=` or
  `GET /search/parking?bbox=min_lng,min_lat,max_lng,max_lat` (public, active
  listings only; also supports `vehicle_type`, `covered`, `max_price_paise`,
  `sort=distance|price`, `limit`, `cursor`, and an optional `start`/`end`
  availability window)
- `GET /admin/listings`, `GET /admin/listings/{listing_id}`
- `POST /admin/listings/{listing_id}/approve|reject|suspend|restore`

Public listing and search responses omit exact addresses, pincodes, and access
instructions. Search pins use the deterministic approximate public location and
return straight-line distance in meters from the search center. Radius must be
100–10,000 m; bounding boxes are capped at 0.5 degrees per side and 0.25 square
degrees. Admin routes require `sthalo.users.is_admin = true`; a Supabase token
role is never trusted for admin access. The `/health/live` and `/health/ready`
endpoints are unauthenticated. Interactive docs are at `/docs`.

## Database migrations

From `backend/` with `DATABASE_URL` configured:

```bash
alembic upgrade head
alembic current
alembic downgrade base
```

Baseline `20261026_0001` creates the `sthalo` and `extensions` schemas and
installs PostGIS, `btree_gist`, and `pgcrypto` in `extensions`. The downgrade
preserves shared schemas/extensions. If PostGIS already exists outside
`extensions`, the migration fails instead of silently using the wrong schema.

Migration `20261026_0002` creates `sthalo.users`, `sthalo.vehicles`, the
`set_updated_at` trigger helper, and `trg_auth_users_create_profile` on
`auth.users`. Migration `20261026_0003` adds `sthalo.listings`,
`parking_listings`, `resources`, `listing_photos`, `reservations`, and
`audit_events`, including reservation overlap protection and deferred photo
position swaps. Migration `20261026_0004` adds a partial GiST index for active
public locations, a GIN index for supported vehicle types, and an expression
index for effective price. Migration `20261026_0005` adds weekly availability
rules and blocked intervals, including a GiST exclusion constraint that prevents
overlapping blocks on a resource. A Supabase auth-user insert provisions the
local profile; deleting the auth user cascades to profile-owned data. Integration
tests expect a mock `auth.users` table in the test database.

## Checks

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

The API returns JSON errors shaped as:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Not Found",
    "details": [],
    "request_id": "..."
  }
}
```

Every response carries `X-Request-ID`; a caller-supplied value is reused only if
it is 1–128 characters of letters, digits, `.`, `_`, or `-`.

## Docker

```bash
docker build -t sthalo-backend .
docker run --rm -p 8000:8000 --env-file .env sthalo-backend
```

The image includes `alembic.ini` and the migration directory. The container
needs the same environment variables as the local process. Do not bake secrets
into the image.
