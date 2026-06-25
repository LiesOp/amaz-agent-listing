import { apiClient } from './client'
import type { AuditCreateResponse } from './types'

export function runAudit(draftId: string) {
  return apiClient<AuditCreateResponse>('/api/v1/audits/run', {
    method: 'POST',
    body: JSON.stringify({ draft_id: draftId }),
  })
}
