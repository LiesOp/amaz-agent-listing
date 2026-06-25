import { apiClient } from './client'
import type { DraftGenerateResponse, DraftRewriteResponse } from './types'

export function generateDraft(briefId: string, customPrompt?: string) {
  return apiClient<DraftGenerateResponse>('/api/v1/drafts/generate', {
    method: 'POST',
    body: JSON.stringify({
      brief_id: briefId,
      custom_prompt: customPrompt?.trim() || null,
    }),
  })
}

export function rewriteDraft(draftId: string, instructions: string) {
  return apiClient<DraftRewriteResponse>(`/api/v1/drafts/${draftId}/rewrite`, {
    method: 'POST',
    body: JSON.stringify({ instructions }),
  })
}
