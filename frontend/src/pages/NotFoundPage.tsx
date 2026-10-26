import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="panel narrow-panel">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p className="muted">That route does not exist in this demo.</p>
      <Link className="button" to="/">
        Back home
      </Link>
    </section>
  )
}
