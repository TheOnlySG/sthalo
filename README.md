# Sthalo

Sthalo is a parking-only, reservation-only MVP for Nashik. Phase 1 is a zero-cost
demo: no payments, no card-backed services, no custom domain, and no production
claims.

## Status

- Foundation: `P1-V0-02` decision lock, `P1-V0-03` scaffold, and `P1-V0-04`
  local Supabase stack are complete.
- `P1-V0-05` CI is green on GitHub
  ([run 40341378459](https://github.com/TheOnlySG/sthalo/actions/runs/40341378459)).
- `P1-V0-06` application factory, configuration, structured logging, request
  IDs, error envelopes, CORS, and health endpoints are complete.
- `P1-V0-07` async SQLAlchemy engine/session, Alembic baseline
  (`20261026_0001`), and `sthalo`/`extensions` schemas are complete.
- `P1-V0-08` local setup and README are complete.
- `G-V0` passed: a fresh clone installed both apps, ran all backend/frontend
  checks, applied migrations up/down/up to a clean database, served `/health/live`
  and `/health/ready` as `200`, and served the built frontend as `200`.
- V1 identity, profiles, and vehicles are implemented locally: Supabase signup,
  Mailpit confirmation, login/logout, password reset, JWT-protected profile and
  owner-terms APIs, and private vehicle CRUD.
- Local `G-V1` checks pass: real signup/login/logout, profile provisioning by the
  auth trigger, profile/vehicle API calls with a Supabase JWT, invalid-token
  `401`, and cross-user vehicle access as `404`. FastAPI contains no password
  handling. Hosted demo login is still pending, so `G-V1` is not fully closed.
- V1 CI is green on GitHub
  ([run 40348810807](https://github.com/TheOnlySG/sthalo/actions/runs/40348810807)).
- V2 owner listings are implemented locally: draft/edit/submit, private
  validated photos, moderation, lifecycle actions, public listing detail, and
  the local admin queue.
- V3 discovery is implemented locally: active-only radius and bounding-box
  search, vehicle/covered/price filters, distance/price sorting, keyset cursor
  pagination, privacy-safe approximate coordinates and distances, and an
  OpenStreetMap/Leaflet search page with map/list selection. Migration
  `20261026_0004` adds the active-location GiST, vehicle-type GIN, and effective
  price indexes.
- V4 availability is implemented locally: owner weekly rules, one-off blocked
  intervals with overlap protection, deterministic 15-minute availability
  windows in the listing timezone, block-vs-booking conflict checks, a public
  availability API, availability-aware search windows, and an owner availability
  editor. Migration `20261026_0005` adds the new tables and an exclusion
  constraint.
- V5 reservations are implemented locally: authoritative 15-minute quotes,
  pricing snapshots, idempotent create/confirm/cancel, 10-minute holds,
  privacy-aware exact-detail reveal, lazy expiry reconciliation, an
  advisory-locked lifecycle sweeper, owner cancellation, and vehicle deletion
  safety. Migration `20261026_0006` adds `sthalo.idempotency_keys` and the
  lifecycle sweep index.
- `G-V5` passed locally: the 20-way booking race, same-key concurrency,
  block-vs-booking race, privacy, expiry/sweeper, and cancellation tests passed
  three consecutive runs.
- V6 customer and owner journeys are implemented locally: quote/hold/confirm/
  cancel UI, hold countdown, customer booking list/detail, owner reservation
  dashboard, exact address/access reveal only after confirmation, empty/loading/
  error states, and a visible no-payment demo banner.
- V7 admin operations are implemented locally: overview counts, read-only
  reservation inspection with audit timeline, audit filtering, moderation, and
  an audited `scripts/make_admin.py` bootstrap path. Non-admin admin requests
  return `403`.
- V8 local hardening is implemented: API security headers, explicit CORS,
  per-client rate limits with `429` envelopes, frontend CSP/security headers,
  secret scanning, dependency audits, OpenAPI snapshot drift checks, admin
  bootstrap, and a tested backup/restore drill. See
  [`docs/security-review.md`](docs/security-review.md).
- Final local checks currently pass: backend `ruff`, format, `mypy`, 117 tests;
  frontend format, lint, typecheck, 14 tests, and production build; and the
  Playwright browser E2E suite (2 tests) covering the customer/owner/admin
  journey, critical axe checks, and a 360 px keyboard/mobile pass.
- Availability-aware search (`P1-V3-03`) is covered. Reverse geocoding
  (`P1-V3-05`) is intentionally unused; the pin remains manual.
- Hosted `G-V1` remains unverified because no hosted provider resources exist.
  V2–V8 proceed as local-only slices under that documented exception.
- Hosted deployment: not started. No Render, Supabase, or Cloudflare Pages
  project has been created; V9 remains a hard gate.
- Payments, EV charging, reviews, disputes, and payouts: deferred.

## Repository layout

```text
backend/    FastAPI + async SQLAlchemy + Alembic API
frontend/   React + Vite + TypeScript application
supabase/   Local Supabase configuration (Mailpit, Auth, Storage)
scripts/    Repository-level secret scan
.github/    CI workflow
```

## Local Supabase

Prerequisites: Docker and Node.js 22+. The Supabase CLI is run through `npx`, so
a global install is not required. A Docker Compose plugin is not required.

```bash
npx --yes supabase@2.122.0 start
npx --yes supabase@2.122.0 status
```

Local endpoints:

| Service    | URL                                                       |
| ---------- | --------------------------------------------------------- |
| API / Auth | `http://127.0.0.1:54321`                                  |
| Database   | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| Studio     | `http://127.0.0.1:54323`                                  |
| Mailpit    | `http://127.0.0.1:54324`                                  |

Local email confirmation is enabled. Signup and password-reset messages are
captured by Mailpit at `http://127.0.0.1:54324`.

Copy the local keys into the ignored environment files:

```bash
npx --yes supabase@2.122.0 status -o env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Use `ANON_KEY` / `SERVICE_ROLE_KEY` (legacy JWT keys) or `PUBLISHABLE_KEY` /
`SECRET_KEY` from that output. Never put the service-role or secret key in the
frontend, and never commit the filled `.env` files.

The local stack binds services to `0.0.0.0` and uses shared development keys.
It is for local development only. Stop it with:

```bash
npx --yes supabase@2.122.0 stop
```

`supabase/config.toml` owns the local stack configuration. The application
schema is owned by Alembic. Baseline `20261026_0001` creates `sthalo` and
`extensions` and installs PostGIS, `btree_gist`, and `pgcrypto`; migration
`20261026_0002` adds `sthalo.users`, `sthalo.vehicles`, and the trigger that
provisions a local profile for each Supabase auth user. Migration
`20261026_0003` adds listings, parking attributes, resources, photos, audit
events, and the reservation schema used by archive safety checks. Migration
`20261026_0004` adds discovery indexes for active public locations, supported
vehicle types, and effective price. Migration `20261026_0005` adds owner
availability rules, blocked intervals, and the block-overlap exclusion
constraint. Migration `20261026_0006` adds reservation idempotency keys and the
lifecycle sweep index. Do not use `supabase db reset` as the application
migration source.

## Quick start

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/setup_local_storage.py
uvicorn app.main:app --reload --port 8000
```

`scripts/setup_local_storage.py` creates the private `listing-photos` bucket.
It is idempotent. Health checks: `GET /health/live` and `GET /health/ready` on
`http://127.0.0.1:8000`. Readiness requires the current Alembic head. API docs are
at `http://127.0.0.1:8000/docs`. Backend checks:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Frontend checks:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run format:check
```

Operational checks:

```bash
# Backend OpenAPI snapshot
cd backend && .venv/bin/python scripts/export_openapi.py --check

# Audits and tracked-secret scan
cd backend && .venv/bin/pip-audit --progress-spinner off
cd frontend && npm audit --omit=dev --audit-level=high
./scripts/check_secrets.sh

# Backup/restore drill (local Supabase)
set -a; source backend/.env; set +a
backend/scripts/backup_restore_check.sh
```

API responses carry `X-Request-ID`, defensive browser headers, and rate-limit
headers. Rate limits return the standard `429 RATE_LIMITED` error envelope with
`Retry-After`. The limits are configured in `backend/.env` and are per process
for the zero-cost single-instance demo.

### Local auth walkthrough

1. Open `/register`, enter a demo name, demo email, and a password of at least
   eight characters with letters and digits.
2. Open Mailpit at `http://127.0.0.1:54324`, find the confirmation message, and
   open its link.
3. Sign in at `/login`. The auth trigger creates the local profile.
4. Edit the profile, accept owner terms, and add/edit/remove up to ten vehicles.
5. Open `/account/listings`, create a parking draft, add pricing and 1–8 photos,
   then submit it for review. Public detail appears only after approval.
6. To review locally, promote a test account with the audited script:
   `backend/.venv/bin/python backend/scripts/make_admin.py --email '<your-email>'`.
   Use `--revoke` to remove access. Open `/admin/listings`, approve/reject/
   suspend/restore, and refresh the owner dashboard to see the result.
7. Open `/search` to see approved listings on the OpenStreetMap view. Try a
   radius search, filters, sorting, marker/list selection, and “Search this map
   area” for a bounding-box search. Distances and pins are approximate.
8. From `/account/listings`, open **Availability** to add weekly windows and
   one-off IST blocks.
9. Add a customer vehicle, open an approved listing, request a quote, and place
   a 10-minute hold. Confirm it from `/account/bookings/:id`; the exact address
   and access details appear only after confirmation.
10. Open `/account/reservations` as the owner to see live bookings, and cancel
    with a reason to release the slot.
11. As admin, inspect `/admin`, `/admin/reservations/:id`, and `/admin/audit`.
    Every listing/reservation mutation has a note and audit event.
12. Sign out from the header. Password reset also uses Mailpit and lands on
    `/reset-password`, where the new password is set.

The backend verifies Supabase access tokens against the local JWKS. Keep the
frontend `VITE_API_BASE_URL` origin in backend `CORS_ORIGINS`. The frontend never
stores or submits passwords to FastAPI; Supabase Auth owns credentials.

The CI workflow runs a tracked-file secret scan, Python/npm dependency audits,
backend lint, format, type checks, OpenAPI snapshot drift, unit tests, migrations
up/down/up, integration tests, and the PostGIS/`btree_gist` probe, plus frontend
lint, typecheck, tests, build, and formatting. V0 and V1 CI are green. V2–V8
local checks cover listings/photos/moderation, public detail, search filters/
privacy, availability, reservation concurrency/idempotency/lifecycle/privacy,
owner/customer UI, admin inspection, security headers/rate limits, and backup/
restore. The committed Playwright/axe suite runs locally against Chrome and the
local Supabase stack; it is not part of CI. See `docs/security-review.md`.

## Hosted demo policy

- Supabase Free is the database/Auth/Storage target.
- Cloudflare Pages Free is the frontend target.
- Render Free is only a candidate backend host. It must not be used until the
  actual signup and deployment flow is verified to require no card and no billing
  activation. Local development remains the fallback.
- Hosted URLs are recorded only after the providers generate them; they are not
  invented in `.env.example`.
