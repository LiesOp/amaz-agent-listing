<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">审核</p>
        <h2>审核结果</h2>
      </div>
      <button type="button" :disabled="!workflow.draftId || workflow.isBusy('runAudit')" @click="audit">
        {{ workflow.isBusy('runAudit') ? '审核中...' : '重新审核' }}
      </button>
    </div>

    <div v-if="auditResult" class="stack-sm">
      <div class="inline-status">
        <span :class="['badge', riskClass]">风险 {{ auditResult.risk_score }}</span>
        <span class="muted">{{ displayAuditStatus(auditResult.status) }}</span>
      </div>

      <section>
        <h3>问题</h3>
        <ul v-if="auditResult.findings?.length" class="content-list">
          <li v-for="(finding, index) in auditResult.findings" :key="index">
            {{ formatFinding(finding) }}
          </li>
        </ul>
        <p v-else class="muted">未发现明显风险。</p>
      </section>

      <section>
        <h3>建议</h3>
        <ul v-if="auditResult.suggestions?.length" class="content-list">
          <li v-for="suggestion in auditResult.suggestions" :key="suggestion">{{ suggestion }}</li>
        </ul>
        <p v-else class="muted">暂无建议。</p>
      </section>

    </div>

    <p v-else class="muted">生成文案后会在这里展示审核结果。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { JsonObject } from '../api/types'
import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()
const auditResult = computed(() => workflow.currentAudit)
const riskClass = computed(() => {
  const score = auditResult.value?.risk_score ?? 0
  if (score >= 70) {
    return 'badge-danger'
  }
  if (score >= 40) {
    return 'badge-warning'
  }
  return 'badge-success'
})

function formatFinding(finding: JsonObject) {
  return Object.entries(finding)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' - ')
}

function audit() {
  void workflow.runAudit()
}

function displayAuditStatus(status: string) {
  const labels: Record<string, string> = {
    pass: '通过',
    passed: '通过',
    warning: '需注意',
    fail: '未通过',
    failed: '未通过',
    completed: '已完成',
    success: '成功',
    error: '错误',
  }
  return labels[status] ?? status
}
</script>
