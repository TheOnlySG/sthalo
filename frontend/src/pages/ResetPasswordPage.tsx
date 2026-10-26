import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function ResetPasswordPage() {
  const { session, loading, requestPasswordReset, updatePassword } = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordUpdated, setPasswordUpdated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Could not send the email.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      setError('The new passwords do not match.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await updatePassword(newPassword)
      setPasswordUpdated(true)
      setNewPassword('')
      setConfirmPassword('')
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : 'Could not update the password.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <p className="status-message" role="status">
        Checking your session…
      </p>
    )
  }

  return (
    <section className="panel narrow-panel">
      <p className="eyebrow">Account recovery</p>
      <h1>Reset password</h1>

      {session ? (
        passwordUpdated ? (
          <>
            <p className="alert alert-success">Your password has been updated.</p>
            <p className="muted">You can continue using this session or sign in again later.</p>
            <div className="hero-actions">
              <Link className="button" to="/account/profile">
                Open profile
              </Link>
              <Link className="button button-secondary" to="/">
                Back home
              </Link>
            </div>
          </>
        ) : (
          <>
            <p className="muted">
              You arrived from a recovery link or are already signed in. Set a new password for this
              demo account.
            </p>
            <form className="form" onSubmit={handleUpdate}>
              <label className="field">
                <span>New password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
                <small>At least 8 characters with letters and digits.</small>
              </label>
              <label className="field">
                <span>Confirm new password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              {error ? (
                <p className="alert alert-error" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="form-actions">
                <button className="button" type="submit" disabled={submitting}>
                  {submitting ? 'Updating…' : 'Update password'}
                </button>
                <Link className="button button-secondary" to="/account/profile">
                  Cancel
                </Link>
              </div>
            </form>
          </>
        )
      ) : sent ? (
        <>
          <p>
            If an account exists for that email, Supabase sent a reset link. Local messages appear
            in Mailpit.
          </p>
          <p className="muted">
            <a href="http://127.0.0.1:54324" target="_blank" rel="noreferrer">
              Open local Mailpit
            </a>
          </p>
          <Link className="button" to="/login">
            Back to sign in
          </Link>
        </>
      ) : (
        <>
          <p className="muted">Enter your account email to request a Supabase reset link.</p>
          <form className="form" onSubmit={handleRequest}>
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
            {error ? (
              <p className="alert alert-error" role="alert">
                {error}
              </p>
            ) : null}
            <button className="button" type="submit" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
          <p className="auth-links">
            <Link to="/login">Back to sign in</Link>
          </p>
        </>
      )}
    </section>
  )
}
