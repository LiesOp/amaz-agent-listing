<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">产品简报</p>
        <h2>产品简报</h2>
      </div>
      <button type="button" :disabled="!workflow.conversationId || workflow.isBusy('saveBrief')" @click="submit">
        {{ workflow.isBusy('saveBrief') ? '保存中...' : '保存简报' }}
      </button>
    </div>

    <div v-if="validationErrors.length" class="alert alert-warning">
      {{ validationErrors.join(' ') }}
    </div>

    <div class="form-grid">
      <label>
        产品名称
        <input v-model="form.product_name" :disabled="!workflow.conversationId" />
      </label>
      <label>
        品牌
        <input v-model="form.brand" :disabled="!workflow.conversationId" />
      </label>
      <label>
        类目
        <input v-model="form.category" :disabled="!workflow.conversationId" />
      </label>
      <label>
        颜色
        <input v-model="form.color" :disabled="!workflow.conversationId" />
      </label>
      <label>
        数量
        <input v-model="form.quantity" :disabled="!workflow.conversationId" />
      </label>
      <label>
        尺寸信息
        <input v-model="form.size_info" :disabled="!workflow.conversationId" />
      </label>
      <label class="span-2">
        核心卖点
        <textarea v-model="coreFeaturesText" :disabled="!workflow.conversationId" rows="3" />
      </label>
      <label>
        材质
        <textarea v-model="materialsText" :disabled="!workflow.conversationId" rows="3" />
      </label>
      <label>
        关键词
        <textarea v-model="keywordsText" :disabled="!workflow.conversationId" rows="3" />
      </label>
      <label class="span-2">
        目标人群
        <input v-model="form.target_audience" :disabled="!workflow.conversationId" />
      </label>
    </div>

    <div v-if="workflow.brief" class="inline-status">
      <span :class="['badge', workflow.brief.is_ready_for_generation ? 'badge-success' : 'badge-warning']">
        {{ workflow.brief.completeness_score }}%
      </span>
      <span v-if="workflow.brief.missing_required_fields.length" class="muted">
        缺失字段：{{ workflow.brief.missing_required_fields.join(', ') }}
      </span>
      <span v-else class="muted">已可导入竞品。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()
const form = reactive({
  product_name: '',
  brand: '',
  category: '',
  color: '',
  quantity: '',
  size_info: '',
  target_audience: '',
})
const coreFeaturesText = ref('')
const materialsText = ref('')
const keywordsText = ref('')

watch(
  () => workflow.brief,
  (brief) => {
    if (!brief) {
      return
    }
    form.product_name = brief.product_name ?? ''
    form.brand = brief.brand ?? ''
    form.category = brief.category ?? ''
    form.color = brief.color ?? ''
    form.quantity = brief.quantity ?? ''
    form.size_info = brief.size_info ?? ''
    form.target_audience = brief.target_audience ?? ''
    coreFeaturesText.value = (brief.core_features ?? []).join('\n')
    materialsText.value = (brief.materials ?? []).join('\n')
    keywordsText.value = (brief.keywords_seed ?? []).join('\n')
  },
)

function toList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function submit() {
  validationErrors.value = validateBrief()
  if (validationErrors.value.length) {
    return
  }

  void workflow.saveBrief({
    ...form,
    core_features: toList(coreFeaturesText.value),
    materials: toList(materialsText.value),
    keywords_seed: toList(keywordsText.value),
  })
}

const validationErrors = ref<string[]>([])

function validateBrief() {
  const errors: string[] = []
  if (!form.product_name.trim()) {
    errors.push('产品名称为必填项。')
  }
  if (!toList(coreFeaturesText.value).length) {
    errors.push('至少需要填写一个核心卖点。')
  }
  return errors
}
</script>
