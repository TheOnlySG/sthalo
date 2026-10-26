import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { session, loading, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) {
    return (
      <p className="status-message" role="status">
        Checking your session…
      </p>
    )
  }

  if (session) {
    return <Navigate to="/account/profile" replace />
  }

  const from = (location.state as { from?: string } | null)?.from ?? '/account/profile'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await signIn(email, password)
      navigate(from, { replace: true })
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Sign in failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="auth-layout">
      <div className="panel auth-panel">
        <p className="eyebrow">Welcome back</p>
        <h1>Sign in</h1>
        <p className="muted">
          Use your Supabase account. Local signups require email confirmation through Mailpit.
        </p>
        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              minLength={8}
              required
            />
          </label>
          {error ? (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <div className="auth-links">
          <Link to="/reset-password">Forgot password?</Link>
          <Link to="/register">Create an account</Link>
        </div>
      </div>
      <aside className="panel auth-aside">
        <h2>Demo authentication</h2>
        <p>
          This is a local demo, not production authentication. Hosted email delivery is limited by
          the Supabase Free plan.
        </p>
        <p className="muted">
          Local confirmation emails appear in Mailpit at{' '}
          <a href="http://127.0.0.1:54324" target="_blank" rel="noreferrer">
            127.0.0.1:54324
          </a>
          .
        </p>
      </aside>
    </section>
  )
}
