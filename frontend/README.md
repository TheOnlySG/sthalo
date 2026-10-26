# Sthalo Frontend

React + Vite + TypeScript SPA for the Sthalo Phase 1 parking MVP.

V1 includes Supabase Auth session handling, protected routes, profile and
owner-terms screens, and private vehicle management. Listings, maps,
availability, and reservations arrive in later vertical slices.

## Local checks

```bash
npm install
npm run lint
npm run typecheck
npm run test
npm run build
npm run format:check
```

Routes:

- `/`, `/login`, `/register`, `/verify-email`, `/reset-password`
- `/account/profile`, `/account/vehicles` (authenticated)

## Local Supabase

From the repository root, start the stack and copy the frontend environment:

```bash
npx --yes supabase@2.122.0 start
npx --yes supabase@2.122.0 status -o env
cp frontend/.env.example frontend/.env.local
```

Use `ANON_KEY` (legacy JWT) or `PUBLISHABLE_KEY` as
`VITE_SUPABASE_ANON_KEY` in `frontend/.env.local`. Set `VITE_API_BASE_URL` to the
backend `/api/v1` URL. Local email confirmation and password-reset messages are
captured by Mailpit at `http://127.0.0.1:54324`. Never place the service-role or
secret key in the frontend.

Start the backend on `http://127.0.0.1:8000`, then run `npm run dev`. Create an
account at `/register`, confirm it through Mailpit, sign in, and open the profile
or vehicles page.

## Cloudflare Pages

- Build command: `npm ci && npm run build`
- Output directory: `dist`
- The SPA fallback is in `public/_redirects`.
- Set `VITE_*` variables in the Pages project after the hosted URLs and Supabase
  project actually exist. Do not commit generated hosted URLs to `.env.example`.
