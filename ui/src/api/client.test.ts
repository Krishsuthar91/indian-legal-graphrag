import axios, { type AxiosResponse } from 'axios'
import { toApiError } from './client'

function buildAxiosError(detail: unknown, status = 400): unknown {
  return new axios.AxiosError(
    'Request failed',
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    { status, data: { detail } } as AxiosResponse,
  )
}

describe('toApiError', () => {
  it('extracts a string detail from a FastAPI error', () => {
    const err = toApiError(buildAxiosError('query must not be empty', 422))
    expect(err.message).toBe('query must not be empty')
    expect(err.status).toBe(422)
  })

  it('flattens validation detail arrays', () => {
    const err = toApiError(
      buildAxiosError([
        { msg: 'field required' },
        { msg: 'too long' },
      ]),
    )
    expect(err.message).toBe('field required; too long')
  })

  it('falls back to the axios message', () => {
    const err = toApiError(buildAxiosError(undefined))
    expect(err.message).toBe('Request failed')
  })

  it('handles plain errors and unknowns', () => {
    expect(toApiError(new Error('boom')).message).toBe('boom')
    expect(toApiError('nope').message).toBe('Unknown error')
  })
})
