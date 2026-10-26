import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function HomePage() {
  const { session } = useAuth()

  return (
    <section className="hero">
      <p className="eyebrow">Nashik · Phase 1 demo</p>
      <h1>Parking reservations, without the payment layer.</h1>
      <p className="lede">
        Sthalo will connect drivers with private parking. This local demo now covers accounts,
        vehicles, owner listings with private photos, and admin moderation. Availability and
        reservations arrive in later slices.
      </p>
      <div className="hero-actions">
        {session ? (
          <>
            <Link className="button" to="/account/listings">
              Manage parking listings
            </Link>
            <Link className="button button-secondary" to="/account/profile">
              Open your profile
            </Link>
          </>
        ) : (
          <>
            <Link className="button" to="/login">
              Sign in
            </Link>
            <Link className="button button-secondary" to="/register">
              Create a demo account
            </Link>
          </>
        )}
      </div>

      <div className="feature-grid">
        <article className="card">
          <h2>Owner listings</h2>
          <p>
            Create a parking draft, set fit limits and pricing, then submit it for local moderation.
            Exact addresses stay private.
          </p>
        </article>
        <article className="card">
          <h2>Private photo pipeline</h2>
          <p>
            Listing photos are validated and re-encoded, stored in a private bucket, and served with
            short-lived signed URLs.
          </p>
        </article>
        <article className="card">
          <h2>Admin review</h2>
          <p>
            A local admin queue approves, rejects, suspends, or restores listings with a recorded
            note and audit trail.
          </p>
        </article>
      </div>
    </section>
  )
}
