<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">会话</p>
        <h2>当前会话</h2>
      </div>
      <button type="button" :disabled="workflow.isBusy('createConversation')" @click="create">
        {{ workflow.isBusy('createConversation') ? '创建中...' : '创建会话' }}
      </button>
    </div>

    <dl class="meta-list compact">
      <div>
        <dt>会话 ID</dt>
        <dd>{{ workflow.conversationId || '尚未创建' }}</dd>
      </div>
      <div>
        <dt>当前步骤</dt>
        <dd>{{ displayStep(workflow.currentStep) }}</dd>
      </div>
      <div>
        <dt>市场</dt>
        <dd>{{ workflow.conversation?.marketplace || 'US' }}</dd>
      </div>
      <div>
        <dt>语言</dt>
        <dd>{{ workflow.conversation?.language || 'en-US' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { useWorkflowStore, type WorkflowStep } from '../stores/workflow'

const workflow = useWorkflowStore()

function create() {
  void workflow.createConversation()
}

function displayStep(step: WorkflowStep) {
  const labels: Record<WorkflowStep, string> = {
    idle: '开始',
    collect_brief: '填写简报',
    import_competitors: '导入竞品',
    analyze_competitors: '分析竞品',
    generate_draft: '生成文案',
    review_audit: '审核与改写',
  }
  return labels[step]
}
</script>
