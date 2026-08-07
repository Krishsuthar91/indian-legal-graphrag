import { motion } from 'framer-motion'
import { useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { toApiError, uploadDocument } from '../api/client'
import { LANGUAGES } from '../hooks/useLocalSettings'
import type { DocumentUploadResponse } from '../types'

const ACCEPTED = '.pdf,.docx,.txt'

function languageLabel(code: string): string {
  const found = LANGUAGES.find((lang) => lang.code === code)
  return (found?.label ?? code) || 'Unknown'
}

export default function Upload() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<DocumentUploadResponse | null>(null)
  const [error, setError] = useState('')

  const pickFile = (next: File | undefined | null) => {
    if (!next) return
    setFile(next)
    setResult(null)
    setError('')
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    pickFile(e.target.files?.[0])
  }

  const handleUpload = async () => {
    if (!file || uploading) return
    setUploading(true)
    setProgress(0)
    setError('')
    try {
      const data = await uploadDocument(file, setProgress)
      setResult(data)
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:pt-16">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl dark:text-white">
          Upload a legal document
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500 dark:text-slate-400">
          Drop a PDF, DOCX, or TXT file. It is parsed into a hierarchy, imported into the
          knowledge graph, and indexed for multilingual retrieval — then ask questions
          about it on the Explain page.
        </p>
      </motion.div>

      <div className="mt-8">
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a legal document"
          onClick={() => document.getElementById('upload-file')?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') document.getElementById('upload-file')?.click()
          }}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-10 text-center transition ${
            dragging
              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
              : 'border-slate-300 bg-white hover:border-indigo-400 dark:border-slate-700 dark:bg-slate-900'
          }`}
        >
          <span className="text-3xl">{file ? '📄' : '⬆'}</span>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            {file ? file.name : 'Drag & drop your document here, or click to browse'}
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500">PDF · DOCX · TXT (max 20 MB)</p>
          <input
            id="upload-file"
            type="file"
            accept={ACCEPTED}
            aria-label="Choose a document file"
            className="hidden"
            onChange={onChange}
          />
        </div>

        {file && !uploading && (
          <button
            type="button"
            onClick={handleUpload}
            className="mt-4 w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500"
          >
            Upload & index {file.name}
          </button>
        )}

        {uploading && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Uploading and indexing…</span>
              <span className="font-mono">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                className="h-full rounded-full bg-indigo-600 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-center text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/5 dark:text-red-300"
          >
            {error}
          </div>
        )}

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 overflow-hidden rounded-2xl border border-green-200 bg-white dark:border-green-500/30 dark:bg-slate-900"
          >
            <div className="border-b border-slate-100 bg-green-50 px-5 py-3 text-sm font-semibold text-green-800 dark:border-slate-800 dark:bg-green-500/10 dark:text-green-300">
              ✓ {result.message}
            </div>
            <dl className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">File</dt>
                <dd className="font-medium text-slate-800 dark:text-slate-100">{result.file_name}</dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">Title</dt>
                <dd className="font-medium text-slate-800 dark:text-slate-100">{result.title}</dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">Language</dt>
                <dd className="font-medium text-slate-800 dark:text-slate-100">
                  {languageLabel(result.language)}
                </dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">Pages</dt>
                <dd className="font-medium text-slate-800 dark:text-slate-100">{result.num_pages}</dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">Nodes indexed</dt>
                <dd className="font-medium text-slate-800 dark:text-slate-100">
                  {result.nodes_indexed}
                </dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-slate-500 dark:text-slate-400">Document ID</dt>
                <dd className="font-mono text-xs text-slate-600 dark:text-slate-300">
                  {result.document_id}
                </dd>
              </div>
            </dl>
            <div className="border-t border-slate-100 px-5 py-4 dark:border-slate-800">
              <Link
                to="/explain"
                className="inline-block w-full rounded-xl bg-indigo-600 px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-indigo-500"
              >
                Ask a question about this document →
              </Link>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
