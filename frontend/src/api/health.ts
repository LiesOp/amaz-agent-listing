import { apiClient } from './client'
import type { HealthResponse } from './types'

export function getHealth() {
  return apiClient<HealthResponse>('/health')
}

export function getVersionedHealth() {
  return apiClient<HealthResponse>('/api/v1/health')
}
