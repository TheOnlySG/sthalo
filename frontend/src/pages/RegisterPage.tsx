import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function RegisterPage() {
  const { session, loading, signUp } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmationSent, setConfirmationSent] = useState(false)
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { needsConfirmation } = await signUp(email, password, fullName)
      setConfirmationSent(needsConfirmation)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Signup failed.')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmationSent) {
    return (
      <section className="panel narrow-panel">
        <p className="eyebrow">Check your inbox</p>
        <h1>Confirm your email</h1>
        <p>
          Supabase sent a confirmation link to <strong>{email}</strong>. Confirm it before signing
          in. The local Mailpit inbox is at{' '}
          <a href="http://127.0.0.1:54324" target="_blank" rel="noreferrer">
            127.0.0.1:54324
          </a>
          .
        </p>
        <p className="muted">
          The hosted demo may disable confirmation or use admin-created accounts. This is not
          production authentication.
        </p>
        <Link className="button" to="/login">
          Back to sign in
        </Link>
      </section>
    )
  }

  return (
    <section className="auth-layout">
      <div className="panel auth-panel">
        <p className="eyebrow">New account</p>
        <h1>Create account</h1>
        <p className="muted">Use a demo email address. Do not enter real identity documents.</p>
        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Full name</span>
            <input
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              autoComplete="name"
              minLength={2}
              maxLength={120}
              required
            />
          </label>
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
              autoComplete="new-password"
              minLength={8}
              required
            />
            <small>At least 8 characters with letters and digits.</small>
          </label>
          {error ? (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button" type="submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="auth-links">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
      <aside className="panel auth-aside">
        <h2>What happens next</h2>
        <ol className="plain-list">
          <li>Supabase creates the auth user.</li>
          <li>A database trigger provisions your local profile.</li>
          <li>You confirm the email, then sign in.</li>
        </ol>
        <p className="muted">Passwords are handled only by Supabase Auth.</p>
      </aside>
    </section>
  )
}
