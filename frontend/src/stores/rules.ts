import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  createRule as createRuleApi,
  deleteRule as deleteRuleApi,
  listRules,
  type RuleFilters,
  updateRule as updateRuleApi,
  updateRuleStatus as updateRuleStatusApi,
} from '../api/rules'
import type { RuleCreateRequest, RuleItemResponse, RuleUpdateRequest } from '../api/types'

export const useRulesStore = defineStore('rules', () => {
  const rules = ref<RuleItemResponse[]>([])
  const filters = ref<RuleFilters>({
    category: null,
    rule_level: null,
    is_active: true,
    keyword: null,
  })
  const loading = ref(false)
  const saving = ref(false)
  const deleting = ref(false)
  const lastError = ref<string | null>(null)
  const lastSuccess = ref<string | null>(null)

  const categories = computed(() => {
    return Array.from(new Set(rules.value.map((rule) => rule.rule_category))).sort()
  })

  const levels = computed(() => {
    return Array.from(new Set(rules.value.map((rule) => rule.rule_level))).sort()
  })

  const totalCount = computed(() => rules.value.length)
  const activeCount = computed(() => rules.value.filter((rule) => rule.is_active).length)
  const hardCount = computed(() => rules.value.filter((rule) => rule.rule_level === 'hard').length)

  async function fetchRules() {
    loading.value = true
    lastError.value = null
    try {
      const response = await listRules({
        ...filters.value,
        group_by_category: false,
      })
      rules.value = response.items
      return response
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '加载规则失败'
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createRule(payload: RuleCreateRequest) {
    saving.value = true
    lastError.value = null
    lastSuccess.value = null
    try {
      const rule = await createRuleApi(payload)
      lastSuccess.value = '规则已创建'
      await fetchRules()
      return rule
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '创建规则失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function updateRule(ruleId: string, payload: RuleUpdateRequest) {
    saving.value = true
    lastError.value = null
    lastSuccess.value = null
    try {
      const rule = await updateRuleApi(ruleId, payload)
      lastSuccess.value = '规则已更新'
      await fetchRules()
      return rule
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '更新规则失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function setRuleStatus(ruleId: string, isActive: boolean) {
    saving.value = true
    lastError.value = null
    lastSuccess.value = null
    try {
      const rule = await updateRuleStatusApi(ruleId, { is_active: isActive })
      lastSuccess.value = isActive ? '规则已启用' : '规则已停用'
      await fetchRules()
      return rule
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '更新规则状态失败'
      throw error
    } finally {
      saving.value = false
    }
  }

  async function deleteRule(ruleId: string) {
    deleting.value = true
    lastError.value = null
    lastSuccess.value = null
    try {
      await deleteRuleApi(ruleId)
      lastSuccess.value = '规则已删除'
      await fetchRules()
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '删除规则失败'
      throw error
    } finally {
      deleting.value = false
    }
  }

  function setFilters(nextFilters: Partial<RuleFilters>) {
    filters.value = {
      ...filters.value,
      ...nextFilters,
    }
  }

  return {
    rules,
    filters,
    loading,
    saving,
    deleting,
    lastError,
    lastSuccess,
    categories,
    levels,
    totalCount,
    activeCount,
    hardCount,
    fetchRules,
    createRule,
    updateRule,
    setRuleStatus,
    deleteRule,
    setFilters,
  }
})
