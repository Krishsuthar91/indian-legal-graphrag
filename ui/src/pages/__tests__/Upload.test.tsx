import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { uploadDocument } from '../../api/client'
import Upload from '../Upload'

vi.mock('../../api/client', () => ({
  uploadDocument: vi.fn(),
  toApiError: () => ({ message: 'Unknown error' }),
}))

const mockedUpload = vi.mocked(uploadDocument)

function renderUpload() {
  return render(
    <MemoryRouter>
      <Upload />
    </MemoryRouter>,
  )
}

describe('Upload', () => {
  beforeEach(() => {
    mockedUpload.mockReset()
  })

  it('renders the dropzone', () => {
    renderUpload()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/upload a legal document/i)
    expect(screen.getByLabelText(/upload a legal document/i)).toBeInTheDocument()
  })

  it('uploads a file and shows the indexed result', async () => {
    mockedUpload.mockResolvedValue({
      document_id: 'abc123',
      title: 'Sample Act',
      language: 'en',
      num_pages: 1,
      file_name: 'sample.txt',
      nodes_indexed: 3,
      collections: { sections: 2, documents: 1 },
      message: 'Document indexed',
    })

    const file = new File(['content'], 'sample.txt', { type: 'text/plain' })
    renderUpload()
    fireEvent.change(screen.getByLabelText(/choose a document file/i), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: /upload & index sample\.txt/i }))

    expect(await screen.findByText(/abc123/)).toBeInTheDocument()
    expect(screen.getByText(/Document indexed/)).toBeInTheDocument()
    expect(screen.getByText(/ask a question about this document/i)).toBeInTheDocument()
    expect(mockedUpload).toHaveBeenCalledOnce()
  })

  it('shows an error when the upload fails', async () => {
    mockedUpload.mockRejectedValue(new Error('Upload failed'))
    const file = new File(['content'], 'sample.txt', { type: 'text/plain' })
    renderUpload()
    fireEvent.change(screen.getByLabelText(/choose a document file/i), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: /upload & index sample\.txt/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/unknown error/i)
  })
})
