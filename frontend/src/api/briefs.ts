import { apiClient } from './client'
import type { BriefResponse } from './types'

export interface BriefUpsertPayload {
  conversation_id?: string | null
  product_name?: string | null
  brand?: string | null
  category?: string | null
  marketplace?: string
  language?: string
  core_features?: string[] | null
  materials?: string[] | null
  color?: string | null
  quantity?: string | null
  size_info?: string | null
  target_audience?: string | null
  keywords_seed?: string[] | null
}

function normalizeBriefPayload(payload: BriefUpsertPayload) {
  return {
    marketplace: 'US',
    language: 'en-US',
    ...payload,
  }
}

export function createBrief(payload: BriefUpsertPayload) {
  return apiClient<BriefResponse>('/api/v1/briefs', {
    method: 'POST',
    body: JSON.stringify(normalizeBriefPayload(payload)),
  })
}

export function updateBrief(briefId: string, payload: BriefUpsertPayload) {
  return apiClient<BriefResponse>(`/api/v1/briefs/${briefId}`, {
    method: 'PUT',
    body: JSON.stringify(normalizeBriefPayload(payload)),
  })
}

export function getBrief(briefId: string) {
  return apiClient<BriefResponse>(`/api/v1/briefs/${briefId}`)
}
