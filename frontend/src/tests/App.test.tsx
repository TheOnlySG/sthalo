import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const unsubscribe = vi.fn()

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe } },
      })),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      refreshSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
    },
  },
}))

describe('App routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
  })

  it('renders the landing page and demo notice', async () => {
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: /parking reservations, without/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no payments are collected/i)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Sign in' })).toHaveLength(2)
  })

  it('renders the login route', async () => {
    window.history.pushState({}, '', '/login')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('renders the password reset request route', async () => {
    window.history.pushState({}, '', '/reset-password')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Reset password' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeInTheDocument()
  })
})
