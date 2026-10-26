import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('App scaffold', () => {
  it('renders the Sthalo demo notice', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Sthalo' })).toBeInTheDocument()
    expect(screen.getByText(/does not collect payments/i)).toBeInTheDocument()
  })
})
