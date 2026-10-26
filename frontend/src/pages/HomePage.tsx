import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function HomePage() {
  const { session } = useAuth()

  return (
    <section className="hero">
      <p className="eyebrow">Nashik · Phase 1 demo</p>
      <h1>Parking reservations, without the payment layer.</h1>
      <p className="lede">
        Search active private parking on an approximate map, compare distance and price, then open a
        privacy-safe listing. This local demo also covers accounts, vehicles, owner submissions,
        photo moderation, and admin review.
      </p>
      <div className="hero-actions">
        <Link className="button" to="/search">
          Find parking
        </Link>
        {session ? (
          <>
            <Link className="button button-secondary" to="/account/listings">
              Manage parking listings
            </Link>
            <Link className="button button-quiet" to="/account/profile">
              Open your profile
            </Link>
          </>
        ) : (
          <>
            <Link className="button button-secondary" to="/login">
              Sign in
            </Link>
            <Link className="button button-quiet" to="/register">
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
          <h2>Map-first discovery</h2>
          <p>
            Radius and map-area searches use approximate pins, clear distances, and OpenStreetMap
            tiles. Exact addresses stay private until a later reservation flow.
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
