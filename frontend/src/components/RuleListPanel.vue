<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">规则库</p>
        <h2>人工维护亚马逊通用规则</h2>
      </div>
      <div class="button-group">
        <button type="button" class="secondary-button" :disabled="rules.loading" @click="refresh">
          {{ rules.loading ? '加载中...' : '刷新' }}
        </button>
        <button type="button" @click="openCreateDialog">新增规则</button>
      </div>
    </div>

    <dl class="meta-list compact">
      <div>
        <dt>当前列表</dt>
        <dd>{{ rules.totalCount }}</dd>
      </div>
      <div>
        <dt>启用规则</dt>
        <dd>{{ rules.activeCount }}</dd>
      </div>
      <div>
        <dt>硬性规则</dt>
        <dd>{{ rules.hardCount }}</dd>
      </div>
    </dl>

    <p v-if="rules.lastError" class="error-text">{{ rules.lastError }}</p>
    <p v-if="rules.lastSuccess" class="muted">{{ rules.lastSuccess }}</p>

    <div class="rule-toolbar">
      <div class="filter-grid">
        <label>
          分类
          <select v-model="category" @change="applyFilters">
            <option value="">全部</option>
            <option v-for="item in filterCategories" :key="item" :value="item">{{ displayCategory(item) }}</option>
          </select>
        </label>
        <label>
          等级
          <select v-model="ruleLevel" @change="applyFilters">
            <option value="">全部</option>
            <option v-for="item in filterLevels" :key="item" :value="item">{{ displayRuleLevel(item) }}</option>
          </select>
        </label>
        <label>
          状态
          <select v-model="isActive" @change="applyFilters">
            <option value="true">启用</option>
            <option value="false">停用</option>
            <option value="">全部</option>
          </select>
        </label>
        <label class="span-2">
          关键词
          <input v-model.trim="keyword" @keyup.enter="applyFilters" />
        </label>
        <div class="inline-status">
          <button type="button" class="secondary-button" @click="applyFilters">筛选</button>
        </div>
      </div>
    </div>

    <div v-if="rules.loading" class="empty-panel">正在加载规则...</div>

    <div v-else-if="rules.rules.length" class="data-table">
      <div class="data-table-head rule-grid manual-rule-grid">
        <span>标题</span>
        <span>分类</span>
        <span>等级</span>
        <span>优先级</span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <div v-for="rule in rules.rules" :key="rule.id" class="data-table-row rule-grid manual-rule-grid">
        <strong>{{ rule.rule_title }}</strong>
        <span>{{ displayCategory(rule.rule_category) }}</span>
        <span>{{ displayRuleLevel(rule.rule_level) }}</span>
        <span>{{ rule.priority }}</span>
        <span :class="['status-pill', rule.is_active ? 'status-success' : 'status-muted']">
          {{ rule.is_active ? '启用' : '停用' }}
        </span>
        <div class="row-actions">
          <button type="button" class="secondary-button compact-button" @click="openEditDialog(rule)">编辑</button>
          <button type="button" class="secondary-button compact-button" @click="toggleStatus(rule)">
            {{ rule.is_active ? '停用' : '启用' }}
          </button>
          <button type="button" class="secondary-button compact-button" @click="removeRule(rule)">删除</button>
        </div>
        <p class="row-detail muted">{{ rule.rule_content }}</p>
        <p class="row-detail muted">
          版本：{{ rule.version_no }} · 更新：{{ formatDateTime(rule.updated_at) }}
        </p>
      </div>
    </div>

    <div v-else class="empty-panel">
      <strong>暂无规则。</strong>
      <span>点击“新增规则”录入通用亚马逊规则，生成和审核会读取启用规则。</span>
    </div>

    <div v-if="showRuleDialog" class="modal-overlay" role="presentation" @click.self="closeDialog">
      <section class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="rule-dialog-title">
        <form class="rule-editor" @submit.prevent="submitRule">
          <div class="status-heading">
            <div>
              <p class="eyebrow">{{ editingRuleId ? '编辑' : '新增' }}</p>
              <h3 id="rule-dialog-title">{{ editingRuleId ? '修改规则' : '录入规则' }}</h3>
            </div>
            <button type="button" class="secondary-button compact-button" @click="closeDialog">关闭</button>
          </div>

          <div class="form-grid">
            <label>
              分类
              <select v-model="form.rule_category" required>
                <option v-for="item in categoryOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
            </label>
            <label>
              等级
              <select v-model="form.rule_level" required>
                <option value="hard">硬性规则</option>
                <option value="soft">建议规则</option>
                <option value="guideline">参考规则</option>
              </select>
            </label>
            <label class="span-2">
              标题
              <input v-model.trim="form.rule_title" required maxlength="255" />
            </label>
            <label class="span-2">
              规则内容
              <textarea v-model.trim="form.rule_content" required rows="8" />
            </label>
            <label class="span-2">
              rule_schema JSON
              <textarea v-model.trim="ruleSchemaText" rows="6" />
            </label>
            <label>
              优先级
              <input v-model.number="form.priority" type="number" min="1" />
            </label>
            <label>
              作用范围
              <input v-model.trim="form.rule_scope" />
            </label>
            <label>
              启用
              <select v-model="activeText">
                <option value="true">启用</option>
                <option value="false">停用</option>
              </select>
            </label>
            <label class="span-2">
              来源备注
              <textarea v-model.trim="form.source_note" rows="3" />
            </label>
          </div>

          <div class="inline-status">
            <button type="submit" :disabled="rules.saving">
              {{ rules.saving ? '保存中...' : editingRuleId ? '保存修改' : '创建规则' }}
            </button>
            <button type="button" class="secondary-button" @click="closeDialog">取消</button>
          </div>
        </form>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import type { RuleCreateRequest, RuleItemResponse } from '../api/types'
import { useRulesStore } from '../stores/rules'
import { formatDateTime } from '../utils/datetime'

const rules = useRulesStore()

const categoryOptions = [
  { value: 'title', label: '标题规则' },
  { value: 'bullets', label: '五点描述规则' },
  { value: 'description_text', label: '产品描述规则' },
  { value: 'search_terms', label: '搜索词规则' },
  { value: 'competitor_usage', label: '竞品使用规则' },
  { value: 'output_contract', label: '输出契约规则' },
  { value: 'global', label: '全局规则' },
]

const form = reactive<RuleCreateRequest>({
  rule_category: 'title',
  rule_title: '',
  rule_content: '',
  rule_schema: null,
  rule_scope: 'amazon_listing',
  rule_level: 'hard',
  priority: 100,
  is_active: true,
  source_note: '',
})
const editingRuleId = ref<string | null>(null)
const activeText = ref('true')
const ruleSchemaText = ref('')
const showRuleDialog = ref(false)

const category = ref('')
const ruleLevel = ref('')
const isActive = ref('true')
const keyword = ref('')

const filterCategories = computed(() => {
  return Array.from(new Set([...categoryOptions.map((item) => item.value), ...rules.categories])).sort()
})

const filterLevels = computed(() => {
  return Array.from(new Set(['hard', 'soft', 'guideline', ...rules.levels])).sort()
})

async function submitRule() {
  const ruleSchema = parseRuleSchema()
  if (ruleSchema === undefined) {
    return
  }
  const payload = {
    ...form,
    rule_schema: ruleSchema,
    is_active: activeText.value === 'true',
  }

  if (editingRuleId.value) {
    await rules.updateRule(editingRuleId.value, payload)
  } else {
    await rules.createRule(payload)
  }
  closeDialog()
}

function openCreateDialog() {
  resetForm()
  showRuleDialog.value = true
}

function openEditDialog(rule: RuleItemResponse) {
  editingRuleId.value = rule.id
  form.rule_category = rule.rule_category
  form.rule_title = rule.rule_title
  form.rule_content = rule.rule_content
  form.rule_schema = rule.rule_schema
  form.rule_scope = rule.rule_scope
  form.rule_level = rule.rule_level
  form.priority = rule.priority
  form.is_active = rule.is_active
  form.source_note = rule.source_note ?? ''
  ruleSchemaText.value = formatRuleSchema(rule.rule_schema)
  activeText.value = String(rule.is_active)
  showRuleDialog.value = true
}

function closeDialog() {
  showRuleDialog.value = false
  resetForm()
}

function resetForm() {
  editingRuleId.value = null
  form.rule_category = 'title'
  form.rule_title = ''
  form.rule_content = ''
  form.rule_schema = null
  form.rule_scope = 'amazon_listing'
  form.rule_level = 'hard'
  form.priority = 100
  form.is_active = true
  form.source_note = ''
  ruleSchemaText.value = ''
  activeText.value = 'true'
}

function parseRuleSchema(): Record<string, unknown> | null | undefined {
  const value = ruleSchemaText.value.trim()
  if (!value) {
    return null
  }
  try {
    const parsed = JSON.parse(value)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      rules.lastError = 'rule_schema must be a JSON object.'
      return undefined
    }
    return parsed as Record<string, unknown>
  } catch {
    rules.lastError = 'rule_schema must be valid JSON.'
    return undefined
  }
}

function formatRuleSchema(value: Record<string, unknown> | null) {
  return value ? JSON.stringify(value, null, 2) : ''
}

async function toggleStatus(rule: RuleItemResponse) {
  await rules.setRuleStatus(rule.id, !rule.is_active)
}

async function removeRule(rule: RuleItemResponse) {
  if (!window.confirm(`确认删除规则「${rule.rule_title}」？`)) {
    return
  }
  await rules.deleteRule(rule.id)
  if (editingRuleId.value === rule.id) {
    closeDialog()
  }
}

function applyFilters() {
  rules.setFilters({
    category: category.value || null,
    rule_level: ruleLevel.value || null,
    is_active: isActive.value === '' ? null : isActive.value === 'true',
    keyword: keyword.value || null,
  })
  void rules.fetchRules()
}

async function refresh() {
  await rules.fetchRules()
}

onMounted(refresh)

function displayCategory(categoryValue: string) {
  const labels = new Map(categoryOptions.map((item) => [item.value, item.label]))
  return labels.get(categoryValue) ?? categoryValue
}

function displayRuleLevel(ruleLevelValue: string) {
  const labels: Record<string, string> = {
    hard: '硬性规则',
    soft: '建议规则',
    guideline: '参考规则',
    reference: '参考规则',
  }
  return labels[ruleLevelValue] ?? ruleLevelValue
}
</script>
