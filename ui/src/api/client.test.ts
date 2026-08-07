import axios, { type AxiosResponse } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { client, toApiError, uploadDocument } from './client'

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

describe('uploadDocument', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts multipart form data to the upload endpoint', async () => {
    const postSpy = vi
      .spyOn(client, 'post')
      .mockResolvedValue({ data: { document_id: 'abc123' } } as never)

    const file = new File(['hello'], 'sample.txt', { type: 'text/plain' })
    const result = await uploadDocument(file)

    expect(postSpy).toHaveBeenCalledWith(
      '/documents/upload',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } }),
    )
    expect(result.document_id).toBe('abc123')
  })
})
