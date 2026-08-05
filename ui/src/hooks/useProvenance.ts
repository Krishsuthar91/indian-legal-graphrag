import { useQuery } from '@tanstack/react-query'
import { getProvenance } from '../api/client'
import type { QueryResponse } from '../types'

export function useProvenance(id: string) {
  return useQuery({
    queryKey: ['provenance', id],
    queryFn: async (): Promise<QueryResponse> => getProvenance(id),
    enabled: id.trim().length > 0,
    retry: 1,
    staleTime: 30_000,
  })
}
