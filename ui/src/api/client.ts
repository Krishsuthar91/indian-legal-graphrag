import axios from 'axios'
import type { ExplainRequest, ExplanationResponse, QueryRequest, QueryResponse } from '../types'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120_000,
})

export interface ApiError {
  message: string
  status?: number
}

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      return { message: detail, status: error.response?.status }
    }
    if (Array.isArray(detail)) {
      return { message: detail.map((d) => d?.msg ?? '').filter(Boolean).join('; '), status: error.response?.status }
    }
    return { message: error.message, status: error.response?.status }
  }
  if (error instanceof Error) {
    return { message: error.message }
  }
  return { message: 'Unknown error' }
}

export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
  const { data } = await client.post<QueryResponse>('/query', req)
  return data
}

export async function postExplain(req: ExplainRequest): Promise<ExplanationResponse> {
  const { data } = await client.post<ExplanationResponse>('/explain', req)
  return data
}

export async function getProvenance(id: string): Promise<QueryResponse> {
  const { data } = await client.get<QueryResponse>(`/provenance/${encodeURIComponent(id)}`)
  return data
}
