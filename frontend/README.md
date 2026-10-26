# Sthalo Frontend

React + Vite + TypeScript SPA for the Sthalo Phase 1 parking MVP.

This is a scaffold. Feature routes, Supabase Auth, maps, and API integration
arrive in later vertical slices.

## Local checks

```bash
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

## Local Supabase

From the repository root, start the stack and copy the frontend environment:

```bash
npx --yes supabase@2.122.0 start
npx --yes supabase@2.122.0 status -o env
cp frontend/.env.example frontend/.env.local
```

Use `ANON_KEY` (legacy JWT) or `PUBLISHABLE_KEY` as
`VITE_SUPABASE_ANON_KEY` in `frontend/.env.local`. Local email confirmation
messages are captured by Mailpit at `http://127.0.0.1:54324`. Never place the
service-role or secret key in the frontend.

## Cloudflare Pages

- Build command: `npm ci && npm run build`
- Output directory: `dist`
- The SPA fallback is in `public/_redirects`.
- Set `VITE_*` variables in the Pages project after the hosted URLs and Supabase
  project actually exist. Do not commit generated hosted URLs to `.env.example`.
