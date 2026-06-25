<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">文案</p>
        <h2>生成商品文案</h2>
      </div>
      <button type="button" :disabled="!workflow.briefId || workflow.isBusy('generateDraft')" @click="generate">
        {{ workflow.isBusy('generateDraft') ? '生成中...' : '生成' }}
      </button>
    </div>

    <p v-if="!workflow.hasCompletedAnalysis && workflow.briefId" class="muted">
      竞品分析任务完成前，生成上下文中的竞品摘要可能为空。
    </p>
    <p v-if="!workflow.briefId" class="muted">请先保存完整 Brief，再生成文案。</p>
    <p class="muted">生成和审核会使用当前启用的通用亚马逊规则；如果没有启用规则，请先到规则页面录入。</p>

    <label class="draft-custom-prompt">
      自定义提示词
      <textarea
        v-model="customPrompt"
        :disabled="!workflow.briefId || workflow.isBusy('generateDraft')"
        rows="4"
        placeholder="可选：补充你希望模型重点强调的卖点、语气、结构或禁用表达。"
      />
    </label>

    <dl class="meta-list compact draft-context">
      <div>
        <dt>Brief</dt>
        <dd>{{ workflow.briefId || '未就绪' }}</dd>
      </div>
      <div>
        <dt>竞品数量</dt>
        <dd>{{ workflow.competitorInputs.length }}</dd>
      </div>
      <div>
        <dt>输出内容</dt>
        <dd>标题、五点描述、长描述、搜索词</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()
const customPrompt = ref('')

function generate() {
  void workflow.generateDraft(customPrompt.value)
}
</script>
