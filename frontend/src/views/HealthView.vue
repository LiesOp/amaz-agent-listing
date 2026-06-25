<template>
  <section class="stack">
    <div class="panel action-panel">
      <div>
        <p class="eyebrow">可观测</p>
        <h2>健康检查</h2>
        <p class="muted">检查两个健康接口，并显示最近一次请求 ID。</p>
      </div>
      <button type="button" :disabled="loading" @click="loadHealth">
        {{ loading ? '检查中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <dl class="meta-list">
      <div>
        <dt>最近请求 ID</dt>
        <dd>{{ requestStatus.lastRequestId || '暂无' }}</dd>
      </div>
      <div>
        <dt>最近请求状态</dt>
        <dd>{{ requestStatus.loading ? '请求中' : '空闲' }}</dd>
      </div>
      <div>
        <dt>最近错误</dt>
        <dd>{{ requestStatus.lastError || '暂无' }}</dd>
      </div>
    </dl>

    <div class="observability-grid">
      <HealthCard title="根路径 /health" :health="rootHealth" />
      <HealthCard title="版本接口 /api/v1/health" :health="versionedHealth" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { defineComponent, h, onMounted, ref, type PropType } from 'vue'

import { ApiError } from '../api/client'
import { getHealth, getVersionedHealth } from '../api/health'
import type { HealthResponse } from '../api/types'
import { useRequestStatusStore } from '../stores/requestStatus'

const rootHealth = ref<HealthResponse | null>(null)
const versionedHealth = ref<HealthResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const requestStatus = useRequestStatusStore()

const HealthCard = defineComponent({
  props: {
    title: {
      type: String,
      required: true,
    },
    health: {
      type: Object as PropType<HealthResponse | null>,
      default: null,
    },
  },
  setup(props) {
    return () =>
      h('section', { class: 'panel' }, [
        h('div', { class: 'status-heading' }, [
          h('h2', props.title),
          h(
            'span',
            { class: ['badge', props.health?.status === 'ok' ? 'badge-success' : 'badge-warning'] },
            displayStatus(props.health?.status),
          ),
        ]),
        props.health
          ? h('dl', { class: 'meta-list compact' }, [
              meta('服务', props.health.service),
              meta('版本', props.health.version),
              meta('环境', props.health.environment),
              meta('数据库', displayStatus(props.health.database.status)),
              meta('LangChain', props.health.langchain.installed ? '已安装' : '未安装'),
              meta('模型配置', props.health.langchain.provider_configured ? '已配置' : '未配置'),
              meta('模型', props.health.langchain.model),
            ])
          : h('p', { class: 'muted' }, '尚未加载响应。'),
        props.health?.database.error ? h('p', { class: 'error-text' }, props.health.database.error) : null,
      ])
  },
})

function meta(label: string, value: string) {
  return h('div', [h('dt', label), h('dd', value)])
}

async function loadHealth() {
  loading.value = true
  error.value = null

  try {
    const [root, versioned] = await Promise.all([getHealth(), getVersionedHealth()])
    rootHealth.value = root
    versionedHealth.value = versioned
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '健康检查失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadHealth)

function displayStatus(status?: string | null) {
  const labels: Record<string, string> = {
    ok: '正常',
    degraded: '降级',
    error: '错误',
    unknown: '未知',
  }
  return status ? labels[status] ?? status : '未知'
}
</script>
