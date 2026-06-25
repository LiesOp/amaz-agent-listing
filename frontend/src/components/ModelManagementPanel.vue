<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">模型管理</p>
        <h2>启用模型</h2>
      </div>
      <button type="button" :disabled="loading" @click="loadModels">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="success" class="alert alert-success">{{ success }}</div>

    <form class="rule-toolbar" @submit.prevent="saveModel">
      <div class="form-grid">
        <label>
          显示名称
          <input v-model.trim="form.display_name" required placeholder="例如 GPT-4o Mini" />
        </label>
        <label>
          Provider
          <input v-model.trim="form.provider" required placeholder="openai" />
        </label>
        <label>
          模型名称
          <input v-model.trim="form.model_name" required placeholder="gpt-4o-mini" />
        </label>
        <label>
          API Key
          <input
            v-model.trim="form.api_key"
            :required="!editingId"
            type="password"
            autocomplete="new-password"
            :placeholder="editingId ? '留空则不替换' : '输入模型 API Key'"
          />
        </label>
        <label>
          Base URL
          <input v-model.trim="form.base_url" placeholder="可选，例如 https://api.openai.com/v1" />
        </label>
        <label>
          Thinking
          <select v-model="form.thinking_config">
            <option value="disabled">disabled</option>
            <option value="enabled">enabled</option>
          </select>
        </label>
        <label v-if="!editingId" class="checkbox-label span-2">
          <input v-model="form.is_active" type="checkbox" />
          创建后立即启用
        </label>
      </div>
      <div class="inline-status">
        <button type="submit" :disabled="saving">{{ saving ? '保存中...' : editingId ? '保存修改' : '添加模型' }}</button>
        <button v-if="editingId" type="button" class="secondary-button" @click="resetForm">取消编辑</button>
      </div>
    </form>

    <div v-if="models.length" class="data-table">
      <div class="data-table-head model-grid">
        <span>名称</span>
        <span>Provider</span>
        <span>模型</span>
        <span>状态</span>
        <span>更新</span>
        <span>操作</span>
      </div>
      <div v-for="model in models" :key="model.id" class="data-table-row model-grid">
        <strong>{{ model.display_name }}</strong>
        <span>{{ model.provider }}</span>
        <span>{{ model.model_name }}</span>
        <span :class="['status-pill', model.is_active ? 'status-success' : 'status-muted']">
          {{ model.is_active ? '启用中' : '未启用' }}
        </span>
        <span>{{ formatDateTime(model.updated_at) }}</span>
        <div class="row-actions">
          <button type="button" class="compact-button" @click="openDetails(model)">详情</button>
          <button type="button" class="compact-button" @click="startEdit(model)">编辑</button>
          <button
            type="button"
            class="compact-button"
            :disabled="model.is_active || activatingId === model.id"
            @click="activateModel(model.id)"
          >
            {{ activatingId === model.id ? '启用中' : '启用' }}
          </button>
          <button type="button" class="compact-button danger-button" @click="removeModel(model.id)">删除</button>
        </div>
        <p class="row-detail muted">
          {{ model.base_url || '默认 Base URL' }} · API Key {{ model.has_api_key ? '已保存' : '未保存' }} · Thinking {{ model.thinking_config }}
        </p>
      </div>
    </div>

    <div v-else class="empty-panel">
      <strong>暂无模型。</strong>
      <span>添加模型并启用后，生成、改写、审核和竞品分析会使用当前启用模型。</span>
    </div>

    <div v-if="detailModel" class="modal-overlay" @click.self="closeDetails">
      <section class="modal-panel model-detail-modal">
        <div class="panel-header">
          <div>
            <p class="eyebrow">调用详情</p>
            <h2>{{ detailModel.display_name }}</h2>
          </div>
          <button type="button" class="secondary-button compact-button" @click="closeDetails">关闭</button>
        </div>

        <dl class="meta-list compact">
          <div>
            <dt>Provider</dt>
            <dd>{{ detailModel.provider }}</dd>
          </div>
          <div>
            <dt>模型</dt>
            <dd>{{ detailModel.model_name }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ detailModel.is_active ? '启用中' : '未启用' }}</dd>
          </div>
        </dl>

        <div v-if="logsLoading" class="empty-panel">
          <strong>正在加载调用记录...</strong>
        </div>

        <div v-else-if="invocationLogs.length" class="data-table">
          <div class="data-table-head model-log-grid">
            <span>调用时间</span>
            <span>功能</span>
            <span>接口</span>
            <span>输入</span>
            <span>输出</span>
            <span>总计</span>
          </div>
          <div v-for="log in invocationLogs" :key="log.id" class="data-table-row model-log-grid">
            <span>{{ formatDateTime(log.created_at) }}</span>
            <strong>{{ log.feature_name }}</strong>
            <span>{{ log.api_endpoint }}</span>
            <span>{{ log.input_tokens }}</span>
            <span>{{ log.output_tokens }}</span>
            <span>{{ log.total_tokens }}</span>
          </div>
        </div>

        <div v-if="logTotal > 0" class="pagination-bar">
          <span>第 {{ logPage }} 页 / 共 {{ totalLogPages }} 页 · 共 {{ logTotal }} 条</span>
          <div class="button-group">
            <button type="button" class="secondary-button compact-button" :disabled="logsLoading || logPage <= 1" @click="loadLogPage(logPage - 1)">
              上一页
            </button>
            <button type="button" class="secondary-button compact-button" :disabled="logsLoading || logPage >= totalLogPages" @click="loadLogPage(logPage + 1)">
              下一页
            </button>
          </div>
        </div>

        <div v-else class="empty-panel">
          <strong>暂无调用记录。</strong>
          <span>模型被生成、改写、审核或竞品分析调用后会显示 token 用量。</span>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  activateModelConfig,
  createModelConfig,
  deleteModelConfig,
  listModelInvocationLogs,
  listModelConfigs,
  updateModelConfig,
} from '../api/admin'
import { ApiError } from '../api/client'
import type { ModelConfigResponse, ModelInvocationLogResponse } from '../api/types'
import { formatDateTime } from '../utils/datetime'

const models = ref<ModelConfigResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const activatingId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const detailModel = ref<ModelConfigResponse | null>(null)
const invocationLogs = ref<ModelInvocationLogResponse[]>([])
const logsLoading = ref(false)
const logPage = ref(1)
const logPageSize = 20
const logTotal = ref(0)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const form = reactive({
  display_name: '',
  provider: 'openai',
  model_name: '',
  api_key: '',
  base_url: '',
  thinking_config: 'disabled',
  is_active: true,
})

async function loadModels() {
  loading.value = true
  error.value = null
  try {
    const response = await listModelConfigs()
    models.value = response.items
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '加载模型列表失败'
  } finally {
    loading.value = false
  }
}

async function saveModel() {
  saving.value = true
  error.value = null
  success.value = null
  try {
    if (editingId.value) {
      await updateModelConfig(editingId.value, {
        display_name: form.display_name,
        provider: form.provider,
        model_name: form.model_name,
        api_key: form.api_key || null,
        base_url: form.base_url || null,
        thinking_config: form.thinking_config,
      })
      success.value = '模型已更新'
    } else {
      await createModelConfig({
        display_name: form.display_name,
        provider: form.provider,
        model_name: form.model_name,
        api_key: form.api_key,
        base_url: form.base_url || null,
        thinking_config: form.thinking_config,
        is_active: form.is_active,
      })
      success.value = '模型已添加'
    }
    resetForm()
    await loadModels()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '保存模型失败'
  } finally {
    saving.value = false
  }
}

function startEdit(model: ModelConfigResponse) {
  editingId.value = model.id
  form.display_name = model.display_name
  form.provider = model.provider
  form.model_name = model.model_name
  form.api_key = ''
  form.base_url = model.base_url || ''
  form.thinking_config = model.thinking_config
  form.is_active = model.is_active
  success.value = null
  error.value = null
}

function resetForm() {
  editingId.value = null
  form.display_name = ''
  form.provider = 'openai'
  form.model_name = ''
  form.api_key = ''
  form.base_url = ''
  form.thinking_config = 'disabled'
  form.is_active = true
}

async function activateModel(modelConfigId: string) {
  activatingId.value = modelConfigId
  error.value = null
  success.value = null
  try {
    await activateModelConfig(modelConfigId)
    success.value = '模型已启用'
    await loadModels()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '启用模型失败'
  } finally {
    activatingId.value = null
  }
}

async function removeModel(modelConfigId: string) {
  if (!window.confirm('确定删除这个模型配置？')) {
    return
  }
  error.value = null
  success.value = null
  try {
    await deleteModelConfig(modelConfigId)
    if (editingId.value === modelConfigId) {
      resetForm()
    }
    success.value = '模型已删除'
    await loadModels()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '删除模型失败'
  }
}

async function openDetails(model: ModelConfigResponse) {
  detailModel.value = model
  invocationLogs.value = []
  logPage.value = 1
  logTotal.value = 0
  error.value = null
  await loadLogPage(1)
}

async function loadLogPage(page: number) {
  if (!detailModel.value) {
    return
  }
  logsLoading.value = true
  try {
    const response = await listModelInvocationLogs(detailModel.value.id, page, logPageSize)
    invocationLogs.value = response.items
    logPage.value = response.page
    logTotal.value = response.total
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '加载模型调用详情失败'
  } finally {
    logsLoading.value = false
  }
}

function closeDetails() {
  detailModel.value = null
  invocationLogs.value = []
  logPage.value = 1
  logTotal.value = 0
}

const totalLogPages = computed(() => Math.max(1, Math.ceil(logTotal.value / logPageSize)))

onMounted(loadModels)
</script>
