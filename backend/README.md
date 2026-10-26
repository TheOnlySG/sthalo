# Sthalo Backend

FastAPI + async SQLAlchemy backend for the Sthalo Phase 1 parking MVP.

The repository is being built in vertical slices. This checkpoint contains the
application foundation plus V1 identity, profile, owner-terms, and vehicle APIs.
Supabase Auth owns credentials; FastAPI verifies access tokens through JWKS and
never handles passwords. Listings, discovery, and reservations arrive in later
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
uvicorn app.main:app --reload --port 8000
```

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

The `/health/live` and `/health/ready` endpoints are unauthenticated. Interactive
docs are at `/docs`.

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
`auth.users`. A Supabase auth-user insert provisions the local profile; deleting
the auth user cascades to the profile and vehicles. Integration tests expect a
mock `auth.users` table in the test database.

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
