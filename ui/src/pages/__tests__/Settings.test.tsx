import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Settings from '../Settings'

describe('Settings', () => {
  it('renders appearance, defaults, API and about sections', () => {
    render(<Settings dark={false} onToggleDark={vi.fn()} />)
    expect(screen.getByText('Dark mode')).toBeInTheDocument()
    expect(screen.getByText('POST /query')).toBeInTheDocument()
    expect(screen.getByText('GET /provenance/{id}')).toBeInTheDocument()
    expect(screen.getByText(/Module 8 React frontend dashboard/i)).toBeInTheDocument()
  })

  it('toggles dark mode through the parent callback', async () => {
    const user = userEvent.setup()
    const onToggleDark = vi.fn()
    render(<Settings dark={false} onToggleDark={onToggleDark} />)
    await user.click(screen.getByRole('button', { name: 'Toggle dark mode' }))
    expect(onToggleDark).toHaveBeenCalledWith(true)
  })
})
