import { useQuery } from '@tanstack/react-query'
import { postQuery, toApiError } from '../api/client'

export interface QueryParams {
  query: string
  language?: string
  top_k?: number
  temperature?: number
  max_tokens?: number
}

export function useQueryQuestion(params: QueryParams, enabled: boolean) {
  return useQuery({
    queryKey: ['query', params],
    queryFn: () => postQuery(params),
    enabled,
    retry: 1,
    staleTime: 0,
  })
}

export function toErrorMessage(error: unknown): string {
  return toApiError(error).message || 'Request failed. Please try again.'
}
