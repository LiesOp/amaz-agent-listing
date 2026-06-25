<template>
  <section class="panel">
    <p class="eyebrow">流程</p>
    <ol class="step-list">
      <li v-for="step in steps" :key="step.key" :class="{ active: step.key === workflow.currentStep }">
        <span>{{ step.index }}</span>
        <strong>{{ step.label }}</strong>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { useWorkflowStore, type WorkflowStep } from '../stores/workflow'

const workflow = useWorkflowStore()
const steps: Array<{ index: number; key: WorkflowStep; label: string }> = [
  { index: 1, key: 'idle', label: '开始' },
  { index: 2, key: 'collect_brief', label: '填写简报' },
  { index: 3, key: 'import_competitors', label: '导入竞品' },
  { index: 4, key: 'analyze_competitors', label: '分析竞品' },
  { index: 5, key: 'generate_draft', label: '生成文案' },
  { index: 6, key: 'review_audit', label: '审核与改写' },
]
</script>
