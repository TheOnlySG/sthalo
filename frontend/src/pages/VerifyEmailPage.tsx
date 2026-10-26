import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function VerifyEmailPage() {
  const { session } = useAuth()

  return (
    <section className="panel narrow-panel">
      <p className="eyebrow">Email verification</p>
      <h1>{session ? 'Email verified' : 'Check your email'}</h1>
      <p>
        {session
          ? 'Your session is active. You can continue to your profile.'
          : 'Open the confirmation link from Supabase. In local development, the message is in Mailpit.'}
      </p>
      <p className="muted">
        Local Mailpit:{' '}
        <a href="http://127.0.0.1:54324" target="_blank" rel="noreferrer">
          127.0.0.1:54324
        </a>
      </p>
      <div className="hero-actions">
        <Link className="button" to={session ? '/account/profile' : '/login'}>
          {session ? 'Open profile' : 'Back to sign in'}
        </Link>
      </div>
    </section>
  )
}
