import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function HomePage() {
  const { session } = useAuth()

  return (
    <section className="hero">
      <p className="eyebrow">Nashik · Phase 1 demo</p>
      <h1>Parking reservations, without the payment layer.</h1>
      <p className="lede">
        Sthalo will connect drivers with private parking. This demo currently covers accounts,
        profiles, and vehicles. Listings, availability, and reservations arrive in later slices.
      </p>
      <div className="hero-actions">
        {session ? (
          <>
            <Link className="button" to="/account/profile">
              Open your profile
            </Link>
            <Link className="button button-secondary" to="/account/vehicles">
              Manage vehicles
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
          <h2>Authenticated with Supabase</h2>
          <p>
            Signup, login, refresh, and email verification are handled by Supabase Auth. The API
            verifies every access token; FastAPI never stores passwords.
          </p>
        </article>
        <article className="card">
          <h2>Local profiles</h2>
          <p>
            Each verified account gets a local profile with a display name, optional phone number,
            and owner-terms acceptance.
          </p>
        </article>
        <article className="card">
          <h2>Minimal vehicles</h2>
          <p>
            Add up to ten vehicles with type, optional dimensions, and registration details. Vehicle
            records are private to your account.
          </p>
        </article>
      </div>
    </section>
  )
}
