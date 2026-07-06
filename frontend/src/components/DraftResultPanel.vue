<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">结果</p>
        <h2>文案结果</h2>
      </div>
      <span v-if="draft" class="badge">v{{ draft.version_no }}</span>
    </div>

    <div v-if="draft" class="stack-sm">
      <section>
        <h3>标题</h3>
        <p>{{ draft.title || '未返回标题。' }}</p>
      </section>

      <section>
        <h3>五点描述</h3>
        <ul class="content-list">
          <li v-for="(bullet, index) in draft.bullets || []" :key="index">{{ bullet }}</li>
        </ul>
      </section>

      <section>
        <h3>长描述</h3>
        <p
          v-if="draft.description_fields || draft.description_text"
          class="long-description-text"
          v-text="formatLongDescription(draft)"
        />
        <p v-else>未返回长描述。</p>
      </section>

      <section>
        <h3>搜索词</h3>
        <pre v-if="draft.search_terms?.length" class="line-list-text">{{ formatLines(draft.search_terms) }}</pre>
        <p v-else>未返回搜索词。</p>
      </section>
    </div>

    <p v-else class="muted">生成文案后会在这里展示结果。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { DescriptionFieldsResponse, DraftResponse } from '../api/types'
import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()
const draft = computed(() => workflow.currentDraft)

function formatLongDescription(value: DraftResponse): string {
  if (value.description_fields) {
    return renderDescriptionFields(value.description_fields)
  }
  return formatDescriptionText(value.description_text || '')
}

function renderDescriptionFields(value: DescriptionFieldsResponse): string {
  const specification = value.specification
  const lines = [
    paragraph(value.description_title),
    '<p><b>SPECIFICATION:</b></p>',
    paragraph(specificationLine('Brand', specification.brand)),
    paragraph(specificationLine('Name', specification.name)),
    paragraph(specificationLine('Color', specification.color)),
    paragraph(specificationLine('Material', specification.material)),
  ]
  if (specification.size) {
    lines.push(paragraph(`<b>SIZE: </b>${specification.size}`))
  }
  lines.push(
    paragraph(specificationLine('Applicable', specification.applicable)),
    '<p><b>FEATURES:</b></p>',
    ...value.features.map((feature) => (
      paragraph(`-${feature.replace(/^-+/, '').trim()}`)
    )),
  )
  return lines.filter((line) => line !== '<p></p>').join('\n')
}

function paragraph(value: string): string {
  return `<p>${value}</p>`
}

function specificationLine(label: string, value: string): string {
  return value ? `${label}: ${value}` : `${label}: `
}

function formatDescriptionText(value: string): string {
  return value
    .replace(/\r?\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s*(<p\b[^>]*>|&lt;p(?:\s[^&]*)?&gt;)/gi, '\n$1')
    .replace(/(<\/p>|&lt;\/p&gt;)\s*/gi, '$1\n')
    .trim()
}

function formatLines(value: string[]): string {
  return value
    .flatMap((item) => item.split(/[,，]/))
    .map((item) => item.trim())
    .filter(Boolean)
    .join('\n')
}
</script>
