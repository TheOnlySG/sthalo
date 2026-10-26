import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { getMe } from '../lib/api'
import type { UserProfile } from '../types'

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'nav-link nav-link-active' : 'nav-link'

export function AppShell() {
  const { session, signOut } = useAuth()
  const navigate = useNavigate()
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)

  useEffect(() => {
    let active = true
    if (!session) {
      return
    }
    getMe()
      .then((nextProfile) => {
        if (active) {
          setProfile(nextProfile)
        }
      })
      .catch(() => {
        if (active) {
          setProfile(null)
        }
      })
    return () => {
      active = false
    }
  }, [session])

  async function handleSignOut() {
    setSigningOut(true)
    setSignOutError(null)
    try {
      await signOut()
      navigate('/')
    } catch (error) {
      setSignOutError(error instanceof Error ? error.message : 'Could not sign out.')
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <div className="app-shell">
      <div className="demo-banner">
        Demo only — no payments are collected. Parking reservations are for Nashik.
      </div>
      <header className="site-header">
        <Link className="brand" to="/">
          <span className="brand-mark">S</span>
          <span>Sthalo</span>
        </Link>
        <nav className="site-nav" aria-label="Main navigation">
          <NavLink className={navClassName} to="/" end>
            Home
          </NavLink>
          <NavLink className={navClassName} to="/search">
            Find parking
          </NavLink>
          {session ? (
            <>
              <NavLink className={navClassName} to="/account/profile">
                Profile
              </NavLink>
              <NavLink className={navClassName} to="/account/vehicles">
                Vehicles
              </NavLink>
              <NavLink className={navClassName} to="/account/listings">
                Listings
              </NavLink>
              {profile?.is_admin ? (
                <NavLink className={navClassName} to="/admin/listings">
                  Admin
                </NavLink>
              ) : null}
              <button
                className="button button-quiet"
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
              >
                {signingOut ? 'Signing out…' : 'Sign out'}
              </button>
            </>
          ) : (
            <>
              <NavLink className={navClassName} to="/login">
                Sign in
              </NavLink>
              <NavLink className="button button-small" to="/register">
                Create account
              </NavLink>
            </>
          )}
        </nav>
      </header>
      {signOutError ? (
        <p className="alert alert-error" role="alert">
          {signOutError}
        </p>
      ) : null}
      <main className="page">
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>Phase 1 demo · Supabase Auth · No card-backed services</p>
        {session?.user.email ? <p className="muted">Signed in as {session.user.email}</p> : null}
      </footer>
    </div>
  )
}
