import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { acceptOwnerTerms, errorMessage, getMe, updateMe } from '../lib/api'
import type { UserProfile } from '../types'

const CURRENT_OWNER_TERMS_VERSION = '2026-10-26'

function formatDate(value: string | null): string {
  if (!value) {
    return 'Not accepted'
  }
  return new Date(value).toLocaleString()
}

export function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [acceptingTerms, setAcceptingTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getMe()
      .then((nextProfile) => {
        if (!active) {
          return
        }
        setProfile(nextProfile)
        setFullName(nextProfile.full_name)
        setPhone(nextProfile.phone ?? '')
        setError(null)
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(errorMessage(loadError))
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await updateMe({
        full_name: fullName,
        phone: phone.trim() ? phone.trim() : null,
      })
      setProfile(updated)
      setFullName(updated.full_name)
      setPhone(updated.phone ?? '')
      setNotice('Profile saved.')
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function handleAcceptTerms() {
    setAcceptingTerms(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await acceptOwnerTerms()
      setProfile(updated)
      setNotice('Owner terms accepted.')
    } catch (termsError) {
      setError(errorMessage(termsError))
    } finally {
      setAcceptingTerms(false)
    }
  }

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading your profile…
      </p>
    )
  }

  if (!profile) {
    return (
      <section className="panel narrow-panel">
        <h1>Profile unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error ?? 'Could not load the profile.'}
        </p>
        <Link className="button" to="/">
          Back home
        </Link>
      </section>
    )
  }

  const termsAccepted = profile.owner_terms_version === CURRENT_OWNER_TERMS_VERSION

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Account</p>
          <h1>Your profile</h1>
          <p className="muted">Signed in as {profile.email}</p>
        </div>
        <Link className="button button-secondary" to="/account/vehicles">
          Manage vehicles
        </Link>
      </header>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="alert alert-success" role="status">
          {notice}
        </p>
      ) : null}

      <div className="two-column">
        <section className="panel">
          <h2>Profile details</h2>
          <form className="form" onSubmit={handleSave}>
            <label className="field">
              <span>Full name</span>
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                minLength={2}
                maxLength={120}
                required
              />
            </label>
            <label className="field">
              <span>Phone (optional)</span>
              <input
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                autoComplete="tel"
                placeholder="+919876543210"
              />
              <small>Stored for your account only. Not exposed in public listings.</small>
            </label>
            <button className="button" type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
          </form>
        </section>

        <section className="panel">
          <h2>Owner terms</h2>
          <p>
            Owners must accept the demo owner terms before creating a listing. Listings are not
            available in this slice.
          </p>
          <p className="muted">
            Current version: <strong>{CURRENT_OWNER_TERMS_VERSION}</strong>
          </p>
          <p className="muted">
            Accepted: <strong>{formatDate(profile.owner_terms_accepted_at)}</strong>
          </p>
          {termsAccepted ? (
            <p className="badge">Owner terms accepted</p>
          ) : (
            <button
              className="button"
              type="button"
              onClick={handleAcceptTerms}
              disabled={acceptingTerms}
            >
              {acceptingTerms ? 'Recording acceptance…' : 'Accept owner terms'}
            </button>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>Account status</h2>
        <dl className="definition-list">
          <div>
            <dt>Status</dt>
            <dd>{profile.status}</dd>
          </div>
          <div>
            <dt>Admin</dt>
            <dd>{profile.is_admin ? 'Yes' : 'No'}</dd>
          </div>
          <div>
            <dt>Profile created</dt>
            <dd>{new Date(profile.created_at).toLocaleString()}</dd>
          </div>
        </dl>
      </section>
    </section>
  )
}
