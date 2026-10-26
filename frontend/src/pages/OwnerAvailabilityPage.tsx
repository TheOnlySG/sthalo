import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  createBlockedInterval,
  deleteBlockedInterval,
  errorMessage,
  getAvailabilityRules,
  getOwnerListing,
  listBlockedIntervals,
  replaceAvailabilityRules,
} from '../lib/api'
import type {
  AvailabilityRule,
  AvailabilityRuleInput,
  BlockedInterval,
  OwnerListing,
} from '../types'

const WEEKDAYS = [
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
  { value: 7, label: 'Sunday' },
] as const

const IST = 'Asia/Kolkata'
const IST_OFFSET = '+05:30'

interface RuleRow {
  key: number
  start: string
  end: string
}

type RulesByDay = Record<number, RuleRow[]>

function emptyRules(): RulesByDay {
  return Object.fromEntries(WEEKDAYS.map((day) => [day.value, []]))
}

function hhmm(value: string): string {
  return value.slice(0, 5)
}

function rulesFromApi(rules: AvailabilityRule[]): RulesByDay {
  const result = emptyRules()
  for (const rule of rules) {
    result[rule.weekday].push({
      key: Date.now() + Math.random(),
      start: hhmm(rule.start_time),
      end: hhmm(rule.end_time),
    })
  }
  return result
}

function istLocalToIso(value: string): string {
  return new Date(`${value}:00${IST_OFFSET}`).toISOString()
}

function istInputValue(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: IST,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(iso))
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`
}

function formatIst(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: IST,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(iso))
}

function defaultBlockStart(): string {
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000)
  return istInputValue(tomorrow.toISOString()).slice(0, 11) + '09:00'
}

function defaultBlockEnd(): string {
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000)
  return istInputValue(tomorrow.toISOString()).slice(0, 11) + '10:00'
}

function payloadFromRules(rules: RulesByDay): AvailabilityRuleInput[] {
  return WEEKDAYS.flatMap((day) =>
    rules[day.value].map((row) => ({
      weekday: day.value,
      start_time: `${row.start}:00`,
      end_time: `${row.end}:00`,
      valid_from: null,
      valid_to: null,
    })),
  )
}

function validateRows(rules: RulesByDay): string | null {
  for (const day of WEEKDAYS) {
    for (const row of rules[day.value]) {
      if (!row.start || !row.end) {
        return `${day.label}: every window needs a start and end time.`
      }
      const midnightEnd = row.end === '00:00'
      if (!midnightEnd && row.end <= row.start) {
        return `${day.label}: end time must be after start time, or 00:00 for midnight.`
      }
      if (row.start === '00:00' && midnightEnd) {
        return `${day.label}: a window must have a non-zero duration.`
      }
    }
  }
  return null
}

export function OwnerAvailabilityPage() {
  const { listingId } = useParams()
  const [listing, setListing] = useState<OwnerListing | null>(null)
  const [rules, setRules] = useState<RulesByDay>(emptyRules)
  const [blocks, setBlocks] = useState<BlockedInterval[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [blockStart, setBlockStart] = useState(defaultBlockStart)
  const [blockEnd, setBlockEnd] = useState(defaultBlockEnd)
  const [blockReason, setBlockReason] = useState('')
  const [blockSaving, setBlockSaving] = useState(false)
  const [blockError, setBlockError] = useState<string | null>(null)

  useEffect(() => {
    if (!listingId) {
      return
    }
    let active = true
    Promise.all([
      getOwnerListing(listingId),
      getAvailabilityRules(listingId),
      listBlockedIntervals(listingId),
    ])
      .then(([nextListing, nextRules, nextBlocks]) => {
        if (!active) {
          return
        }
        setListing(nextListing)
        setRules(rulesFromApi(nextRules))
        setBlocks(nextBlocks)
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
  }, [listingId])

  function addRow(weekday: number) {
    setRules((current) => ({
      ...current,
      [weekday]: [
        ...current[weekday],
        { key: Date.now() + Math.random(), start: '09:00', end: '18:00' },
      ],
    }))
  }

  function updateRow(weekday: number, key: number, field: 'start' | 'end', value: string) {
    setRules((current) => ({
      ...current,
      [weekday]: current[weekday].map((row) =>
        row.key === key ? { ...row, [field]: value } : row,
      ),
    }))
  }

  function removeRow(weekday: number, key: number) {
    setRules((current) => ({
      ...current,
      [weekday]: current[weekday].filter((row) => row.key !== key),
    }))
  }

  async function handleSaveRules(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!listingId) {
      return
    }
    const validationError = validateRows(rules)
    if (validationError) {
      setError(validationError)
      setNotice(null)
      return
    }
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const saved = await replaceAvailabilityRules(listingId, payloadFromRules(rules))
      setRules(rulesFromApi(saved))
      setNotice('Weekly availability saved.')
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function handleCreateBlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!listingId) {
      return
    }
    if (!blockStart || !blockEnd) {
      setBlockError('Choose a start and end time for the block.')
      return
    }
    setBlockSaving(true)
    setBlockError(null)
    try {
      const created = await createBlockedInterval(listingId, {
        start: istLocalToIso(blockStart),
        end: istLocalToIso(blockEnd),
        reason: blockReason.trim() || null,
      })
      setBlocks((current) => [...current, created].sort((a, b) => a.start.localeCompare(b.start)))
      setBlockReason('')
      setNotice('Blocked interval added.')
    } catch (createError) {
      setBlockError(errorMessage(createError))
    } finally {
      setBlockSaving(false)
    }
  }

  async function handleDeleteBlock(blockId: string) {
    if (!listingId) {
      return
    }
    setBlockError(null)
    try {
      await deleteBlockedInterval(listingId, blockId)
      setBlocks((current) => current.filter((block) => block.id !== blockId))
      setNotice('Blocked interval removed.')
    } catch (deleteError) {
      setBlockError(errorMessage(deleteError))
    }
  }

  if (loading) {
    return (
      <p className="status-message" role="status">
        Loading availability…
      </p>
    )
  }

  if (error && !listing) {
    return (
      <section className="panel narrow-panel">
        <h1>Availability unavailable</h1>
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      </section>
    )
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Owner availability</p>
          <h1>{listing?.title}</h1>
          <p className="muted">
            Weekly windows use India Standard Time. Use 00:00 as an end time to reach midnight;
            blocks are one-off exceptions.
          </p>
        </div>
        <Link className="button button-secondary" to={`/account/listings/${listingId ?? ''}/edit`}>
          Back to listing
        </Link>
      </header>

      {notice ? (
        <p className="alert alert-success" role="status">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <form className="panel" onSubmit={handleSaveRules}>
        <div className="section-heading">
          <div>
            <h2>Weekly rules</h2>
            <p className="muted">
              Add one or more windows per day. Windows may use 15-minute boundaries.
            </p>
          </div>
          <button className="button" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save weekly rules'}
          </button>
        </div>

        <div className="availability-day-list">
          {WEEKDAYS.map((day) => (
            <section className="availability-day" key={day.value}>
              <div className="availability-day-heading">
                <h3>{day.label}</h3>
                <button
                  className="button button-small button-quiet"
                  type="button"
                  onClick={() => addRow(day.value)}
                >
                  Add window
                </button>
              </div>
              {rules[day.value].length === 0 ? (
                <p className="muted">Unavailable</p>
              ) : (
                <div className="availability-rule-list">
                  {rules[day.value].map((row) => (
                    <div className="availability-rule" key={row.key}>
                      <label className="field">
                        From
                        <input
                          type="time"
                          step="900"
                          value={row.start}
                          onChange={(event) =>
                            updateRow(day.value, row.key, 'start', event.target.value)
                          }
                        />
                      </label>
                      <label className="field">
                        Until
                        <input
                          type="time"
                          step="900"
                          value={row.end}
                          onChange={(event) =>
                            updateRow(day.value, row.key, 'end', event.target.value)
                          }
                        />
                      </label>
                      <button
                        className="button button-small button-quiet"
                        type="button"
                        onClick={() => removeRow(day.value, row.key)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      </form>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Blocked intervals</h2>
            <p className="muted">
              Blocks remove availability and cannot overlap an existing booking.
            </p>
          </div>
        </div>

        <form className="availability-block-form" onSubmit={handleCreateBlock}>
          <label className="field">
            Start (IST)
            <input
              type="datetime-local"
              step="900"
              value={blockStart}
              onChange={(event) => setBlockStart(event.target.value)}
            />
          </label>
          <label className="field">
            End (IST)
            <input
              type="datetime-local"
              step="900"
              value={blockEnd}
              onChange={(event) => setBlockEnd(event.target.value)}
            />
          </label>
          <label className="field">
            Reason (optional)
            <input
              type="text"
              maxLength={500}
              value={blockReason}
              onChange={(event) => setBlockReason(event.target.value)}
            />
          </label>
          <button className="button" type="submit" disabled={blockSaving}>
            {blockSaving ? 'Adding…' : 'Add block'}
          </button>
        </form>

        {blockError ? (
          <p className="alert alert-error" role="alert">
            {blockError}
          </p>
        ) : null}

        {blocks.length === 0 ? (
          <p className="muted">No blocked intervals.</p>
        ) : (
          <div className="availability-block-list">
            {blocks.map((block) => (
              <article className="availability-block" key={block.id}>
                <div>
                  <strong>{formatIst(block.start)}</strong>
                  <span className="muted"> to {formatIst(block.end)}</span>
                  {block.reason ? <p className="muted">{block.reason}</p> : null}
                </div>
                <button
                  className="button button-small button-secondary"
                  type="button"
                  onClick={() => void handleDeleteBlock(block.id)}
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  )
}
