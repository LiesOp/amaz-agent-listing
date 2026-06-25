<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">任务</p>
        <h2>最近任务状态</h2>
      </div>
    </div>

    <div class="manual-job">
      <input v-model="manualJobId" placeholder="任务 ID" />
      <button type="button" :disabled="!manualJobId" @click="refresh(manualJobId)">刷新</button>
    </div>

    <div v-if="tasks.recentJobIds.length" class="table-list">
      <div v-for="jobId in tasks.recentJobIds" :key="jobId" class="table-row">
        <div>
          <strong>{{ jobId }}</strong>
          <span class="muted">{{ displayStatus(tasks.jobsById[jobId]?.status) }}</span>
          <span v-if="tasks.jobsById[jobId]?.error_message" class="error-text">
            {{ tasks.jobsById[jobId]?.error_message }}
          </span>
        </div>
        <button type="button" @click="refresh(jobId)">刷新</button>
      </div>
    </div>

    <p v-else class="muted">导入或分析竞品后，任务会显示在这里。</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { useTasksStore } from '../stores/tasks'

const tasks = useTasksStore()
const manualJobId = ref('')

function refresh(jobId: string) {
  void tasks.fetchJob(jobId)
}

function displayStatus(status?: string) {
  const labels: Record<string, string> = {
    queued: '已排队',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    'not loaded': '未加载',
  }
  return labels[status || 'not loaded'] ?? status
}
</script>
