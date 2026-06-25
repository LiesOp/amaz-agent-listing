<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">任务</p>
        <h2>最近任务</h2>
      </div>
      <button type="button" class="secondary-button" @click="tasks.clearCompletedJobs">清理已完成</button>
    </div>

    <div class="manual-job">
      <input v-model="manualJobId" placeholder="任务 ID" />
      <button type="button" :disabled="!manualJobId || lookupLoading" @click="lookup">
        {{ lookupLoading ? '查询中...' : '查询' }}
      </button>
    </div>

    <div v-if="tasks.recentJobIds.length" class="data-table">
      <div class="data-table-head job-grid">
        <span>任务 ID</span>
        <span>类型</span>
        <span>状态</span>
        <span>更新时间</span>
        <span>操作</span>
      </div>
      <div v-for="jobId in tasks.recentJobIds" :key="jobId" class="data-table-row job-grid">
        <strong>{{ jobId }}</strong>
        <span>{{ displayJobType(tasks.jobsById[jobId]?.job_type) }}</span>
        <span :class="['status-pill', statusClass(tasks.jobsById[jobId]?.status)]">
          {{ displayStatus(tasks.jobsById[jobId]?.status) }}
        </span>
        <span>{{ formatDateTime(tasks.jobsById[jobId]?.finished_at || tasks.jobsById[jobId]?.started_at) }}</span>
        <span class="row-actions">
          <button type="button" class="compact-button" @click="refresh(jobId)">刷新</button>
          <button
            type="button"
            class="secondary-button compact-button"
            @click="togglePolling(jobId)"
          >
            {{ tasks.pollingJobIds.includes(jobId) ? '停止' : '轮询' }}
          </button>
        </span>
        <p v-if="tasks.jobsById[jobId]?.error_message" class="error-text row-detail">
          {{ tasks.jobsById[jobId]?.error_message }}
        </p>
        <p v-else-if="tasks.jobsById[jobId]?.result_summary" class="muted row-detail">
          {{ tasks.jobsById[jobId]?.result_summary }}
        </p>
      </div>
    </div>

    <div v-else class="empty-panel">
      <strong>暂无最近任务。</strong>
      <span>竞品分析会进入最近任务列表，也可以在上方输入任务 ID 查询。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import { useTasksStore } from '../stores/tasks'
import { formatDateTime } from '../utils/datetime'

const tasks = useTasksStore()
const manualJobId = ref('')
const lookupLoading = ref(false)

async function lookup() {
  const jobId = manualJobId.value.trim()
  if (!jobId) {
    return
  }
  lookupLoading.value = true
  try {
    await tasks.fetchJob(jobId)
  } finally {
    lookupLoading.value = false
  }
}

function refresh(jobId: string) {
  void tasks.fetchJob(jobId)
}

function togglePolling(jobId: string) {
  if (tasks.pollingJobIds.includes(jobId)) {
    tasks.stopPollingJob(jobId)
  } else {
    tasks.pollJob(jobId)
  }
}

function statusClass(status?: string) {
  if (status === 'completed') {
    return 'status-success'
  }
  if (status === 'failed') {
    return 'status-danger'
  }
  if (status === 'running') {
    return 'status-warning'
  }
  return 'status-muted'
}

function displayStatus(status?: string) {
  const labels: Record<string, string> = {
    queued: '已排队',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    unknown: '未知',
  }
  return labels[status || 'unknown'] ?? status
}

function displayJobType(jobType?: string) {
  const labels: Record<string, string> = {
    competitor_import: '竞品导入',
    competitor_analysis: '竞品分析',
    draft_generation: '文案生成',
    audit: '文案审核',
    rewrite: '文案改写',
  }
  return jobType ? labels[jobType] ?? jobType : '-'
}

onMounted(() => {
  tasks.recentJobIds.forEach((jobId) => {
    void tasks.fetchJob(jobId)
  })
})

onUnmounted(() => {
  tasks.stopAllPolling()
})
</script>
