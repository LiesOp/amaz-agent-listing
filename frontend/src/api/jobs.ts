import { apiClient } from './client'
import type { JobResponse } from './types'

export function getJob(jobId: string) {
  return apiClient<JobResponse>(`/api/v1/jobs/${jobId}`)
}
