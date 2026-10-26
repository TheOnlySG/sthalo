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
- Next: start V1 feature implementation.
- Hosted deployment: not started. No Render, Supabase, or Cloudflare Pages
  project has been created.
- Payments, EV charging, reviews, disputes, and payouts: deferred.

## Repository layout

```text
backend/    FastAPI + async SQLAlchemy scaffold
frontend/   React + Vite + TypeScript scaffold
supabase/   Local Supabase configuration (Mailpit, Auth, Storage)
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

| Service | URL |
|---|---|
| API / Auth | `http://127.0.0.1:54321` |
| Database | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| Studio | `http://127.0.0.1:54323` |
| Mailpit | `http://127.0.0.1:54324` |

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
schema is owned by Alembic; baseline `20261026_0001` creates `sthalo` and
`extensions` and installs PostGIS, `btree_gist`, and `pgcrypto`. Do not use
`supabase db reset` as the application migration source.

## Quick start (foundation)

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Health checks: `GET /health/live` and `GET /health/ready` on
`http://127.0.0.1:8000`. Readiness requires the Alembic baseline. Backend checks:

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
npm run lint
npm run typecheck
npm run test
npm run build
```

The CI workflow runs the backend checks, a clean PostGIS/`btree_gist` probe, and
the frontend checks, including Alembic up/down/up. It is green on GitHub, and the
fresh-clone `G-V0` check passed. Feature routes and auth flows arrive in later
tasks.

## Hosted demo policy

- Supabase Free is the database/Auth/Storage target.
- Cloudflare Pages Free is the frontend target.
- Render Free is only a candidate backend host. It must not be used until the
  actual signup and deployment flow is verified to require no card and no billing
  activation. Local development remains the fallback.
- Hosted URLs are recorded only after the providers generate them; they are not
  invented in `.env.example`.
