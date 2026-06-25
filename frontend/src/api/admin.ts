import { apiClient } from './client'
import type {
  ModelConfigCreateRequest,
  ModelConfigListResponse,
  ModelConfigResponse,
  ModelConfigUpdateRequest,
  ModelInvocationLogListResponse,
} from './types'

export function listModelConfigs() {
  return apiClient<ModelConfigListResponse>('/api/v1/admin/models')
}

export function createModelConfig(payload: ModelConfigCreateRequest) {
  return apiClient<ModelConfigResponse>('/api/v1/admin/models', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateModelConfig(modelConfigId: string, payload: ModelConfigUpdateRequest) {
  return apiClient<ModelConfigResponse>(`/api/v1/admin/models/${modelConfigId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function activateModelConfig(modelConfigId: string) {
  return apiClient<ModelConfigResponse>(`/api/v1/admin/models/${modelConfigId}/activate`, {
    method: 'PATCH',
  })
}

export function deleteModelConfig(modelConfigId: string) {
  return apiClient<null>(`/api/v1/admin/models/${modelConfigId}`, {
    method: 'DELETE',
  })
}

export function listModelInvocationLogs(modelConfigId: string, page = 1, pageSize = 20) {
  return apiClient<ModelInvocationLogListResponse>(
    `/api/v1/admin/models/${modelConfigId}/invocations`,
    {
      query: { page, page_size: pageSize },
    },
  )
}
