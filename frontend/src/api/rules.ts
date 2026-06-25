import { apiClient, type QueryParams } from './client'
import type {
  RuleCreateRequest,
  RuleGroupedResponse,
  RuleItemResponse,
  RuleListResponse,
  RuleStatusUpdateRequest,
  RuleUpdateRequest,
} from './types'

export interface RuleFilters extends QueryParams {
  category?: string | null
  rule_level?: string | null
  is_active?: boolean | null
  keyword?: string | null
  group_by_category?: boolean
}

export function listRules(filters: RuleFilters & { group_by_category: true }): Promise<RuleGroupedResponse>
export function listRules(filters?: RuleFilters): Promise<RuleListResponse>
export function listRules(filters: RuleFilters = {}) {
  return apiClient<RuleListResponse | RuleGroupedResponse>('/api/v1/rules', {
    query: filters,
  })
}

export function getRule(ruleId: string) {
  return apiClient<RuleItemResponse>(`/api/v1/rules/${ruleId}`)
}

export function createRule(payload: RuleCreateRequest) {
  return apiClient<RuleItemResponse>('/api/v1/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateRule(ruleId: string, payload: RuleUpdateRequest) {
  return apiClient<RuleItemResponse>(`/api/v1/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function updateRuleStatus(ruleId: string, payload: RuleStatusUpdateRequest) {
  return apiClient<RuleItemResponse>(`/api/v1/rules/${ruleId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteRule(ruleId: string) {
  return apiClient<void>(`/api/v1/rules/${ruleId}`, {
    method: 'DELETE',
  })
}
