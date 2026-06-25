import { apiClient } from './client'
import type {
  CopywritingDraftAuditPageResponse,
  CopywritingRecordListResponse,
} from './types'

export function listCopywritingRecords(page: number, pageSize: number) {
  return apiClient<CopywritingRecordListResponse>('/api/v1/copywriting/records', {
    query: {
      page,
      page_size: pageSize,
    },
  })
}

export function getCopywritingDraftAudits(conversationId: string, page: number) {
  return apiClient<CopywritingDraftAuditPageResponse>(
    `/api/v1/copywriting/records/${conversationId}/draft-audits`,
    {
      query: {
        page,
      },
    },
  )
}
