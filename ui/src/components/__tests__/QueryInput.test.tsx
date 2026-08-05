import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import QueryInput from '../QueryInput'

describe('QueryInput', () => {
  it('calls onSubmit with query, language and topK', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QueryInput onSubmit={onSubmit} />)

    const textarea = screen.getByPlaceholderText(/Ask about any Indian legal provision/i)
    await user.type(textarea, 'What is the punishment for murder?')
    await user.click(screen.getByRole('button', { name: /ask question/i }))

    expect(onSubmit).toHaveBeenCalledWith({
      query: 'What is the punishment for murder?',
      language: '',
      topK: 5,
    })
  })

  it('keeps the submit button disabled while empty', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QueryInput onSubmit={onSubmit} />)

    expect(screen.getByRole('button', { name: /ask question/i })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: /ask question/i }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits on Enter and shows a busy label while working', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const { rerender } = render(<QueryInput onSubmit={onSubmit} />)

    await user.type(screen.getByPlaceholderText(/Ask about any Indian legal provision/i), 'a legal query')
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)

    rerender(<QueryInput onSubmit={onSubmit} busy />)
    expect(screen.getByRole('button', { name: /working/i })).toBeDisabled()
  })

  it('honours initial values', () => {
    render(
      <QueryInput
        initialQuery="initial question"
        initialLanguage="hi"
        initialTopK={8}
        onSubmit={vi.fn()}
      />,
    )
    expect(screen.getByPlaceholderText(/Ask about any Indian legal provision/i)).toHaveValue(
      'initial question',
    )
    expect(screen.getByLabelText('Document language')).toHaveValue('hi')
    expect(screen.getByLabelText('Top K evidence')).toHaveValue('8')
  })
})
