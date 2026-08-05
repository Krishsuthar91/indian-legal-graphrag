import { useQuery } from '@tanstack/react-query'
import { postExplain } from '../api/client'
import type { ExplainRequest, ExplanationResponse } from '../types'

export function useExplain(request: ExplainRequest, enabled: boolean) {
  return useQuery({
    queryKey: ['explain', request],
    queryFn: async (): Promise<ExplanationResponse> => postExplain(request),
    enabled,
    retry: 1,
    staleTime: 0,
  })
}
