# Sthalo Frontend

React + Vite + TypeScript SPA for the Sthalo Phase 1 parking MVP.

V1 includes Supabase Auth session handling, protected routes, profile and
owner-terms screens, and private vehicle management. V2 adds the owner listing
wizard, private photo management, public listing detail, and the local admin
moderation queue. V3 adds the public map/list discovery page with radius and
bounding-box search, filters, sorting, approximate pins, and cursor pagination.
Availability and reservations arrive in later vertical slices.

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
- `/account/listings`, `/account/listings/new`,
  `/account/listings/:listingId/edit` (authenticated owners)
- `/admin/listings` (authenticated local admin)
- `/search` (public map/list discovery; only active listings)
- `/parking/:listingId` (public active listing)

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

The search page uses Leaflet with OpenStreetMap raster tiles. `VITE_TILE_URL`
defaults to the standard `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
endpoint and `VITE_TILE_ATTRIBUTION` supplies the visible attribution. Keep usage
light, do not prefetch or bulk-download tiles, and keep OSM attribution visible.
The browser may call the tile host directly; the backend is not a tile proxy.

Start the backend on `http://127.0.0.1:8000` and run the backend storage setup
script, then run `npm run dev`. Create an account at `/register`, confirm it
through Mailpit, sign in, accept owner terms, and create a listing from
`/account/listings`. Promote a local test account with
`UPDATE sthalo.users SET is_admin = true WHERE email = '<your-email>';` to use
`/admin/listings`.

## Cloudflare Pages

- Build command: `npm ci && npm run build`
- Output directory: `dist`
- The SPA fallback is in `public/_redirects`.
- Set `VITE_*` variables in the Pages project after the hosted URLs and Supabase
  project actually exist. Do not commit generated hosted URLs to `.env.example`.
