import { useEffect, useState } from 'react'
import { AdminNav } from '../components/AdminNav'
import { errorMessage, listAdminAudit } from '../lib/api'
import { formatReservationDate } from '../lib/reservationFormat'
import type { AuditEvent } from '../types'

export function AdminAuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [entityType, setEntityType] = useState('')
  const [entityId, setEntityId] = useState('')
  const [fromValue, setFromValue] = useState('')
  const [toValue, setToValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listAdminAudit({ limit: 100 })
      .then((items) => {
        if (active) {
          setEvents(items)
          setError(null)
        }
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

  async function applyFilters() {
    setLoading(true)
    setError(null)
    try {
      setEvents(
        await listAdminAudit({
          entity_type: entityType.trim() || undefined,
          entity_id: entityId.trim() || undefined,
          from: fromValue ? new Date(fromValue).toISOString() : undefined,
          to: toValue ? new Date(toValue).toISOString() : undefined,
          limit: 100,
        }),
      )
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Audit log</h1>
          <p className="muted">Append-only events for listings, reservations, and admin actions.</p>
        </div>
      </header>
      <AdminNav />

      <form
        className="panel audit-filters"
        onSubmit={(event) => {
          event.preventDefault()
          void applyFilters()
        }}
      >
        <label className="field">
          <span>Entity type</span>
          <input
            value={entityType}
            onChange={(event) => setEntityType(event.target.value)}
            placeholder="reservation"
          />
        </label>
        <label className="field">
          <span>Entity ID</span>
          <input
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
            placeholder="UUID"
          />
        </label>
        <label className="field">
          <span>From</span>
          <input
            type="datetime-local"
            value={fromValue}
            onChange={(event) => setFromValue(event.target.value)}
          />
        </label>
        <label className="field">
          <span>To</span>
          <input
            type="datetime-local"
            value={toValue}
            onChange={(event) => setToValue(event.target.value)}
          />
        </label>
        <div className="form-actions">
          <button className="button" type="submit" disabled={loading}>
            Apply filters
          </button>
        </div>
      </form>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="status-message" role="status">
          Loading audit events…
        </p>
      ) : events.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No audit events</h2>
          <p className="muted">Try widening the filters.</p>
        </section>
      ) : (
        <div className="audit-event-list">
          {events.map((event) => (
            <article className="panel audit-event-card" key={event.id}>
              <div className="audit-timeline-heading">
                <div>
                  <strong>{event.action}</strong>
                  <p className="muted">
                    {event.entity_type}
                    {event.entity_id ? ` · ${event.entity_id}` : ''}
                  </p>
                </div>
                <span className="muted">{formatReservationDate(event.created_at)}</span>
              </div>
              <p className="muted">
                {event.actor_name ?? event.actor_type}
                {event.actor_email ? ` · ${event.actor_email}` : ''}
              </p>
              {event.after ? (
                <pre className="audit-json">{JSON.stringify(event.after, null, 2)}</pre>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
