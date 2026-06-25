<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">改写</p>
        <h2>改写文案</h2>
      </div>
      <button type="button" :disabled="!workflow.draftId || workflow.isBusy('rewriteDraft')" @click="rewrite">
        {{ workflow.isBusy('rewriteDraft') ? '改写中...' : '改写' }}
      </button>
    </div>

    <textarea
      v-model="workflow.rewriteInstructions"
      :disabled="!workflow.draftId"
      rows="4"
      placeholder="例如：标题缩短一点，并去掉绝对化表达。"
    />
    <p v-if="!workflow.draftId" class="muted">请先生成文案，再进行改写。</p>
    <p v-else-if="!workflow.rewriteInstructions.trim()" class="muted">请输入改写要求。</p>

    <dl v-if="workflow.currentDraft" class="meta-list compact">
      <div>
        <dt>当前文案</dt>
        <dd>{{ workflow.currentDraft.id }}</dd>
      </div>
      <div>
        <dt>版本</dt>
        <dd>{{ workflow.currentDraft.version_no }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()

function rewrite() {
  void workflow.rewriteDraft()
}
</script>
